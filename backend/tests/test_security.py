"""
Authentication & authorization security tests.

Covers the full flow the app actually implements today (register, login,
/auth/me) and, critically, verifies that two independently registered
users can never see or be identified as each other — the core acceptance
criterion for this audit.
"""
import jwt
import pytest
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from conftest import unique_email

VALID_PASSWORD = "correct-horse-battery-staple"


async def _register(client, email=None, name="Test User", password=VALID_PASSWORD):
    return await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email or unique_email(), "password": password},
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_isolated_user(client):
    email = unique_email()
    res = await _register(client, email=email, name="Alice Example")
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == email
    assert body["user"]["name"] == "Alice Example"
    assert body["access_token"]
    assert body["user"]["id"]


@pytest.mark.asyncio
async def test_duplicate_registration_rejected(client):
    email = unique_email()
    first = await _register(client, email=email)
    assert first.status_code == 201

    second = await _register(client, email=email)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_registration_rejects_short_password(client):
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Short Pw", "email": unique_email(), "password": "short"},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success(client):
    email = unique_email()
    await _register(client, email=email)

    res = await client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == email
    assert body["access_token"]


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    email = unique_email()
    await _register(client, email=email)

    res = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email(), "password": VALID_PASSWORD},
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Current-user identification (/auth/me) — token, not client input, is truth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_requires_token(client):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_garbage_token(client):
    res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_expired_token(client):
    email = unique_email()
    register_res = await _register(client, email=email)
    user_id = register_res.json()["user"]["id"]

    expired_payload = {"sub": user_id, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_own_identity(client):
    email = unique_email()
    register_res = await _register(client, email=email, name="Own Identity")
    token = register_res.json()["access_token"]

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == email
    assert body["name"] == "Own Identity"
    assert body["id"] == register_res.json()["user"]["id"]


# ---------------------------------------------------------------------------
# Critical user-isolation test — two concurrent users, neither sees the other
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_users_are_never_cross_identified(client):
    email_a, email_b = unique_email(), unique_email()

    register_a = await _register(client, email=email_a, name="User A")
    register_b = await _register(client, email=email_b, name="User B")
    assert register_a.status_code == 201
    assert register_b.status_code == 201

    token_a = register_a.json()["access_token"]
    token_b = register_b.json()["access_token"]
    id_a = register_a.json()["user"]["id"]
    id_b = register_b.json()["user"]["id"]
    assert id_a != id_b

    me_a = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    me_b = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert me_a.status_code == 200
    assert me_b.status_code == 200

    body_a, body_b = me_a.json(), me_b.json()

    # Each token must resolve to its own account only.
    assert body_a["id"] == id_a
    assert body_a["email"] == email_a
    assert body_b["id"] == id_b
    assert body_b["email"] == email_b

    # Neither user's token may ever resolve to the other's identity.
    assert body_a["id"] != id_b
    assert body_a["email"] != email_b
    assert body_b["id"] != id_a
    assert body_b["email"] != email_a


@pytest.mark.asyncio
async def test_login_returns_correct_account_when_multiple_users_exist(client):
    """
    Regression test for the reported "registration opens another user's
    account" symptom: with several accounts already in the database,
    logging in as one specific user must never return a different user's
    token or profile.
    """
    accounts = [(unique_email(), f"Multi User {i}") for i in range(3)]
    for email, name in accounts:
        res = await _register(client, email=email, name=name)
        assert res.status_code == 201

    target_email, target_name = accounts[1]
    res = await client.post("/api/v1/auth/login", json={"email": target_email, "password": VALID_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == target_email
    assert body["user"]["name"] == target_name

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == target_email
