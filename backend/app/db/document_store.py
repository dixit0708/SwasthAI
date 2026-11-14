"""Durable storage for uploaded medical documents, in MongoDB GridFS.

The app server's local disk is wiped on every redeploy of the hosted
backend, so files written there are lost. GridFS keeps the bytes in the
same MongoDB deployment as the records that own them, which needs no
extra service or billing account.

Access control lives in the callers: a file id is only ever read from a
medical_records document that was itself fetched with the owner's
user_id (AGENTS.md Sections 14 and 48). Nothing here is served by path.
"""
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from app.db.mongodb import db_manager

BUCKET_NAME = "documents"

# Leading bytes each allowed type must start with, so a renamed file
# (e.g. an executable called report.pdf) is rejected.
_SIGNATURES = {
    ".pdf": (b"%PDF",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


def matches_signature(extension: str, data: bytes) -> bool:
    signatures = _SIGNATURES.get(extension.lower())
    if not signatures:
        return False
    return any(data.startswith(sig) for sig in signatures)


def _bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db_manager.db, bucket_name=BUCKET_NAME)


async def save_document(data: bytes, filename: str, user_id: str, content_type: Optional[str]) -> str:
    file_id = await _bucket().upload_from_stream(
        filename,
        data,
        metadata={"user_id": user_id, "content_type": content_type},
    )
    return str(file_id)


async def read_document(file_id: str) -> Optional[bytes]:
    if not ObjectId.is_valid(file_id):
        return None
    try:
        stream = await _bucket().open_download_stream(ObjectId(file_id))
        return await stream.read()
    except Exception:
        # gridfs.errors.NoFile and friends: treat as "document not available".
        return None


async def delete_document(file_id: str) -> None:
    if not ObjectId.is_valid(file_id):
        return
    try:
        await _bucket().delete(ObjectId(file_id))
    except Exception:
        # Already gone: nothing left to remove.
        pass
