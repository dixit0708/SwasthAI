"""
Diabetes prediction endpoint tests. Since the real trained model artifact
(ml_pipeline/diabetes/models/diabetes_model.joblib) is provided by a
teammate and may not exist in every environment, these tests cover the
request-validation and auth boundaries unconditionally, and monkeypatch
a tiny in-memory model onto app.state to exercise the full success path
without depending on the real artifact being present.
"""
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from conftest import unique_email
from app.db.mongodb import db_manager
from app.main import app

VALID_PASSWORD = "correct-horse-battery-staple"

VALID_PAYLOAD = {
    "pregnancies": 2,
    "glucose": 120,
    "blood_pressure": 70,
    "skin_thickness": 20,
    "insulin": 80,
    "bmi": 24.5,
    "diabetes_pedigree_function": 0.3,
    "age": 30,
}


def _tiny_fitted_model():
    """A trivial, fast-to-fit pipeline — good enough to exercise the
    request -> service -> model -> response wiring in a test, not meant
    to be a realistic diabetes classifier."""
    rng = np.random.default_rng(42)
    X = rng.random((40, 8))
    y = (X[:, 1] > 0.5).astype(int)  # depends only on the "glucose" column
    pipeline = Pipeline([("scaler", StandardScaler()), ("classifier", LogisticRegression())])
    pipeline.fit(X, y)
    return pipeline


async def _register_and_get_token(client) -> str:
    return (await _register(client))["access_token"]


async def _register(client) -> dict:
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": unique_email(), "password": VALID_PASSWORD},
    )
    assert res.status_code == 201
    return res.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_diabetes_prediction_requires_auth(client):
    res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_diabetes_prediction_validates_input(client):
    token = await _register_and_get_token(client)
    bad_payload = {**VALID_PAYLOAD, "glucose": -5}  # glucose must be > 0
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_returns_503_when_model_unavailable(client):
    token = await _register_and_get_token(client)
    app.state.diabetes_model = None
    res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(token))
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_diabetes_prediction_success_returns_non_diagnostic_response(client):
    token = await _register_and_get_token(client)
    app.state.diabetes_model = _tiny_fitted_model()
    try:
        res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(token))
        assert res.status_code == 200
        body = res.json()
        assert body["risk_level"] in {"low", "moderate", "elevated"}
        assert 0.0 <= body["risk_probability"] <= 1.0
        assert "diagnosis" not in body["message"].lower() or "not a" in body["message"].lower()
        assert body["disclaimer"]
        assert body["model_version"] == "diabetes-v1"
    finally:
        app.state.diabetes_model = None


@pytest.mark.asyncio
async def test_diabetes_predictions_are_isolated_between_users(client):
    user_a = await _register(client)
    user_b = await _register(client)
    app.state.diabetes_model = _tiny_fitted_model()
    try:
        res_a = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(user_a["access_token"]))
        res_b = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(user_b["access_token"]))
        assert res_a.status_code == 200
        assert res_b.status_code == 200

        # The persisted prediction record must be tagged with the request's
        # own user id — never the other user's, and never absent.
        record_a = await db_manager.db["predictions"].find_one(
            {"user_id": user_a["user"]["id"]}, sort=[("created_at", -1)]
        )
        record_b = await db_manager.db["predictions"].find_one(
            {"user_id": user_b["user"]["id"]}, sort=[("created_at", -1)]
        )
        assert record_a is not None
        assert record_b is not None
        assert record_a["user_id"] == user_a["user"]["id"]
        assert record_b["user_id"] == user_b["user"]["id"]
        assert record_a["user_id"] != record_b["user_id"]
    finally:
        app.state.diabetes_model = None
        await db_manager.db["predictions"].delete_many(
            {"user_id": {"$in": [user_a["user"]["id"], user_b["user"]["id"]]}}
        )
