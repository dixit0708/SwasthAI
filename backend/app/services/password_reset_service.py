"""Password reset by emailed link.

- The emailed token is random and single-use, and expires after
  RESET_TOKEN_MINUTES. Only its SHA-256 hash is stored.
- Requesting a reset never reveals whether an email has an account.
- Completing a reset stamps `password_changed_at` on the user, which
  invalidates every access token issued before it (see api/v1/deps.py).
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from starlette.concurrency import run_in_threadpool

from app.core import email as email_sender
from app.core.config import settings
from app.core.security import hash_password
from app.db.collections import user_repo
from app.db.mongodb import db_manager

logger = logging.getLogger(__name__)

RESET_TOKEN_MINUTES = 30
COLLECTION = "password_resets"


class ResetUnavailable(Exception):
    """Email delivery is not configured on this deployment."""


class InvalidResetToken(Exception):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _collection():
    return db_manager.db[COLLECTION]


async def request_reset(email: str) -> None:
    """Emails a reset link if the address has an account. Returns normally
    either way, so the response cannot be used to probe for accounts."""
    if not email_sender.is_configured():
        raise ResetUnavailable("Password reset by email is not available right now.")

    user = await user_repo.collection.find_one({"email": email.lower()})
    if not user:
        return

    user_id = str(user["_id"])
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    # One live link per account: a new request replaces any earlier one.
    await _collection().delete_many({"user_id": user_id})
    await _collection().insert_one({
        "user_id": user_id,
        "token_hash": _hash_token(token),
        "expires_at": now + timedelta(minutes=RESET_TOKEN_MINUTES),
        "created_at": now,
    })

    link = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password.html?token={quote(token)}"
    body = (
        f"Hello {user.get('name', '')},\n\n"
        "We received a request to reset your SwasthAI password. Use the link below to choose "
        f"a new one. It works once and expires in {RESET_TOKEN_MINUTES} minutes.\n\n"
        f"{link}\n\n"
        "If you did not ask for this, you can ignore this email and your password will stay "
        "the same.\n\n"
        "SwasthAI"
    )
    try:
        await run_in_threadpool(email_sender.send_email, user["email"], "Reset your SwasthAI password", body)
    except Exception as e:
        # Never log the token or the link.
        logger.error(f"Password reset email could not be sent: {type(e).__name__}")
        await _collection().delete_many({"user_id": user_id})
        raise ResetUnavailable("We couldn't send the reset email right now. Please try again later.")


async def reset_password(token: str, new_password: str) -> None:
    record = await _collection().find_one({"token_hash": _hash_token(token)})
    now = datetime.now(timezone.utc)
    if not record:
        raise InvalidResetToken("This reset link is invalid or has already been used.")

    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        await _collection().delete_one({"_id": record["_id"]})
        raise InvalidResetToken("This reset link has expired. Please request a new one.")

    updated = await user_repo.update(
        record["user_id"],
        {"hashed_password": hash_password(new_password), "password_changed_at": now},
    )
    # Single use, whatever happened above.
    await _collection().delete_many({"user_id": record["user_id"]})
    if not updated:
        raise InvalidResetToken("This reset link is invalid or has already been used.")
