import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # "iat" lets a password change invalidate every earlier token. It keeps
    # sub-second precision (RFC 7519 allows a non-integer NumericDate), so a
    # token issued moments before a password change is still caught.
    payload = {"sub": subject, "exp": expire, "iat": now.timestamp()}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def decode_access_token_claims(token: str) -> Optional[dict]:
    """Like decode_access_token, but returns all verified claims."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
