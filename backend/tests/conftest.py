import os

# Tests must never run against the real dev/prod database. Override
# DATABASE_NAME before app.core.config.settings is instantiated (env vars
# take priority over .env in pydantic-settings) so test data lands in an
# isolated database on the same MongoDB deployment.
os.environ.setdefault("DATABASE_NAME", "swasthai_test_db")

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.mongodb import close_mongo_connection, connect_to_mongo, db_manager
from app.main import app


@pytest.fixture
async def client():
    await connect_to_mongo()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await db_manager.db["users"].delete_many({"email": {"$regex": "^swasthai-test-"}})
    await db_manager.db["health_profiles"].delete_many({})
    await db_manager.db["predictions"].delete_many({})
    await close_mongo_connection()


def unique_email() -> str:
    # NOTE: pydantic's EmailStr rejects RFC 2606 reserved TLDs (.test,
    # .invalid, .localhost) as "special-use", so we use example.com here —
    # it never resolves in these tests since no deliverability/DNS check
    # is performed, only syntax validation.
    return f"swasthai-test-{uuid.uuid4().hex}@example.com"
