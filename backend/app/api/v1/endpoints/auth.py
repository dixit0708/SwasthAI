from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import UserCreate, UserLogin, Token, UserOut
from app.core.security import hash_password, verify_password, create_access_token
from app.db.collections import user_repo
from app.api.v1.deps import get_current_user

router = APIRouter()


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
