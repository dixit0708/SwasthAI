from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from app.models.user import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
)
from app.core.rate_limit import SlidingWindowRateLimiter
from app.services import password_reset_service
from app.services.password_reset_service import InvalidResetToken, ResetUnavailable
from app.core.security import hash_password, verify_password, create_access_token
from app.db.collections import user_repo
from app.api.v1.deps import get_current_user

router = APIRouter()

# At most 5 reset emails per address per hour.
forgot_password_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=3600)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate):
    email = payload.email.lower()
    existing = await user_repo.collection.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user_doc = {
        "name": payload.name.strip(),
        "email": email,
        "hashed_password": hash_password(payload.password),
    }
    user_id = await user_repo.create(user_doc)

    token = create_access_token(user_id)
    return Token(access_token=token, user=UserOut(id=user_id, name=user_doc["name"], email=email))


@router.post("/login", response_model=Token)
async def login(payload: UserLogin):
    email = payload.email.lower()
    user = await user_repo.collection.find_one({"email": email})
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(str(user["_id"]))
    return Token(access_token=token, user=UserOut(id=str(user["_id"]), name=user["name"], email=user["email"]))


@router.get("/me", response_model=UserOut)
async def me(current_user: UserOut = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(payload: ForgotPasswordRequest):
    """Emails a single-use reset link. The response is the same whether or
    not the address has an account."""
    email = payload.email.lower()
    if not forgot_password_limiter.allow(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset requests. Please try again in an hour.",
        )
    try:
        await password_reset_service.request_reset(email)
    except ResetUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return {"message": "If an account exists for that email, a reset link is on its way."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(payload: ResetPasswordRequest):
    try:
        await password_reset_service.reset_password(payload.token, payload.new_password)
    except InvalidResetToken as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Your password has been updated. Please sign in with your new password."}


@router.post("/change-password", response_model=Token)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: UserOut = Depends(get_current_user),
):
    """Changes the signed-in user's password. Every other session is signed
    out; a fresh token is returned for this one."""
    user = await user_repo.get_by_id(current_user.id)
    if not user or not verify_password(payload.current_password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your current password is incorrect")

    await user_repo.update(
        current_user.id,
        {
            "hashed_password": hash_password(payload.new_password),
            "password_changed_at": datetime.now(timezone.utc),
        },
    )
    return Token(access_token=create_access_token(current_user.id), user=current_user)
