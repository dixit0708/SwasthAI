from datetime import timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_access_token_claims
from app.db.collections import user_repo
from app.models.user import UserOut

bearer_scheme = HTTPBearer(auto_error=False)


def _issued_before_password_change(claims: dict, user: dict) -> bool:
    """True when the token predates the user's last password change, so a
    reset or change signs out every older session (AGENTS.md Section 55)."""
    changed_at = user.get("password_changed_at")
    if not changed_at:
        return False
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    issued_at = claims.get("iat")
    if issued_at is None:
        return True
    # Mongo stores datetimes to the millisecond; round "iat" the same way so a
    # token minted right after the change (change-password) stays valid.
    return round(float(issued_at), 3) < round(changed_at.timestamp(), 3)


async def _resolve_user(credentials: HTTPAuthorizationCredentials | None) -> tuple[UserOut | None, str]:
    """Returns (user, "") on success, or (None, reason) when not authenticated."""
    if credentials is None:
        return None, "Not authenticated"

    claims = decode_access_token_claims(credentials.credentials)
    user_id = claims.get("sub") if claims else None
    if not user_id:
        return None, "Invalid or expired token"

    user = await user_repo.get_by_id(user_id)
    if not user:
        return None, "User not found"

    if _issued_before_password_change(claims, user):
        return None, "Your password was changed. Please sign in again."

    return UserOut(id=str(user["_id"]), name=user["name"], email=user["email"]), ""


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserOut:
    user, reason = await _resolve_user(credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)
    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserOut | None:
    user, _ = await _resolve_user(credentials)
    return user
