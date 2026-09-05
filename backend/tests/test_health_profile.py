import pytest

from conftest import unique_email

VALID_PASSWORD = "correct-horse-battery-staple"


async def _register_and_get_token(client, email=None, name="Test User") -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email or unique_email(), "password": VALID_PASSWORD},
    )
    assert res.status_code == 201
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_profile_requires_auth(client):
    assert (await client.get("/api/v1/health-profile/me")).status_code == 401
    assert (await client.put("/api/v1/health-profile/me", json={})).status_code == 401
    assert (await client.post("/api/v1/health-profile/me/conditions", json={"label": "x"})).status_code == 401
    assert (await client.delete("/api/v1/health-profile/me/conditions/abc")).status_code == 401


# ---------------------------------------------------------------------------
# Core behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_new_user_gets_empty_default_profile(client):
    token = await _register_and_get_token(client)
    res = await client.get("/api/v1/health-profile/me", headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert body == {"date_of_birth": None, "blood_group": None, "conditions": []}


@pytest.mark.asyncio
async def test_update_basic_info_persists(client):
    token = await _register_and_get_token(client)

    res = await client.put(
        "/api/v1/health-profile/me",
        json={"date_of_birth": "1995-06-15", "blood_group": "O+"},
        headers=_auth(token),
    )
    assert res.status_code == 200
    assert res.json()["date_of_birth"] == "1995-06-15"
    assert res.json()["blood_group"] == "O+"

    # Re-fetch to confirm it was actually saved, not just echoed back.
    res2 = await client.get("/api/v1/health-profile/me", headers=_auth(token))
    assert res2.json()["date_of_birth"] == "1995-06-15"
    assert res2.json()["blood_group"] == "O+"


@pytest.mark.asyncio
async def test_add_and_remove_condition(client):
    token = await _register_and_get_token(client)

    add_res = await client.post(
        "/api/v1/health-profile/me/conditions",
        json={"label": "Peanut Allergy"},
        headers=_auth(token),
    )
    assert add_res.status_code == 201
    conditions = add_res.json()["conditions"]
    assert len(conditions) == 1
    assert conditions[0]["label"] == "Peanut Allergy"
    condition_id = conditions[0]["id"]

    del_res = await client.delete(f"/api/v1/health-profile/me/conditions/{condition_id}", headers=_auth(token))
    assert del_res.status_code == 200
    assert del_res.json()["conditions"] == []


# ---------------------------------------------------------------------------
# User isolation — the same acceptance criterion as the auth audit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_profiles_are_isolated_between_users(client):
    token_a = await _register_and_get_token(client, name="User A")
    token_b = await _register_and_get_token(client, name="User B")

    await client.put(
        "/api/v1/health-profile/me",
        json={"date_of_birth": "1980-01-01", "blood_group": "A+"},
        headers=_auth(token_a),
    )
    await client.post(
        "/api/v1/health-profile/me/conditions",
        json={"label": "User A's private condition"},
        headers=_auth(token_a),
    )

    # User B must see their own empty profile, never User A's data.
    profile_b = (await client.get("/api/v1/health-profile/me", headers=_auth(token_b))).json()
    assert profile_b == {"date_of_birth": None, "blood_group": None, "conditions": []}

    # User A must still see only their own data.
    profile_a = (await client.get("/api/v1/health-profile/me", headers=_auth(token_a))).json()
    assert profile_a["date_of_birth"] == "1980-01-01"
    assert profile_a["blood_group"] == "A+"
    assert len(profile_a["conditions"]) == 1

    # User B adding their own condition must never affect User A's list.
    await client.post(
        "/api/v1/health-profile/me/conditions",
        json={"label": "User B's condition"},
        headers=_auth(token_b),
    )
    profile_a_again = (await client.get("/api/v1/health-profile/me", headers=_auth(token_a))).json()
    assert len(profile_a_again["conditions"]) == 1
    assert profile_a_again["conditions"][0]["label"] == "User A's private condition"
