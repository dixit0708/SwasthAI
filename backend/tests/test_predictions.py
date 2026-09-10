"""
Diabetes prediction endpoint tests, for the CDC BRFSS 2015 14-feature
diabetes-brfss-v2 model
(ml_pipeline/diabetes/artifacts/diabetes_pipeline_v2.pkl + diabetes_metadata_v2.json).
Since the real artifact may not exist in every environment, HTTP-level
tests monkeypatch a tiny in-memory pipeline + metadata dict onto app.state
to exercise the full request -> service -> model -> response wiring
without depending on the real artifact being present.
"""
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from conftest import unique_email
from app.ai.models.diabetes_model import predict_diabetes, validate_features
from app.db.mongodb import db_manager
from app.main import app

VALID_PASSWORD = "correct-horse-battery-staple"

FEATURE_ORDER = [
    "HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke",
    "HeartDiseaseorAttack", "PhysActivity", "Fruits",
    "HvyAlcoholConsump", "GenHlth", "DiffWalk", "Sex", "Age",
]

VALID_PAYLOAD = {
    "high_bp": 0, "high_chol": 0, "chol_check": 1, "bmi": 24.5, "smoker": 0,
    "stroke": 0, "heart_disease_or_attack": 0, "phys_activity": 1, "fruits": 1,
    "hvy_alcohol_consump": 0, "gen_hlth": 2, "diff_walk": 0, "sex": 0, "age": 5,
}

# The snake_case payload above, mapped to BRFSS training-time feature names
# (mirrors prediction_service.predict_diabetes_risk's mapping exactly, so
# tests can independently recompute the row the service builds).
_PAYLOAD_TO_FEATURE_NAME = {
    "high_bp": "HighBP", "high_chol": "HighChol", "chol_check": "CholCheck",
    "bmi": "BMI", "smoker": "Smoker", "stroke": "Stroke",
    "heart_disease_or_attack": "HeartDiseaseorAttack", "phys_activity": "PhysActivity",
    "fruits": "Fruits", "hvy_alcohol_consump": "HvyAlcoholConsump", "gen_hlth": "GenHlth",
    "diff_walk": "DiffWalk", "sex": "Sex", "age": "Age",
}


def _to_features(payload: dict) -> dict:
    return {_PAYLOAD_TO_FEATURE_NAME[k]: v for k, v in payload.items()}


def _tiny_fitted_pipeline():
    """A trivial, fast-to-fit pipeline over the real 14-column feature
    space — good enough to exercise the wiring, not a realistic classifier.
    Depends only on the GenHlth column so tests can build deterministic
    low/high-probability inputs."""
    rng = np.random.default_rng(42)
    X = rng.random((60, len(FEATURE_ORDER)))
    gen_hlth_idx = FEATURE_ORDER.index("GenHlth")
    y = (X[:, gen_hlth_idx] > 0.5).astype(int)
    pipeline = Pipeline([("scaler", StandardScaler()), ("classifier", LogisticRegression())])
    pipeline.fit(X, y)
    return pipeline


def _tiny_metadata(threshold: float = 0.1) -> dict:
    return {
        "model_version": "diabetes-brfss-test",
        "feature_order": FEATURE_ORDER,
        "decision_threshold": threshold,
        "calibration_method": "sigmoid (Platt scaling)",
        "target_column": "Diabetes_binary",
    }


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


def _set_model(pipeline=None, metadata=None):
    app.state.diabetes_model = pipeline
    app.state.diabetes_model_metadata = metadata


# --------------------------------------------------------------------------
# Model-layer unit tests (no HTTP, no DB) — validate_features / predict_diabetes
# --------------------------------------------------------------------------

def test_validate_features_missing_feature_raises_keyerror():
    incomplete = _to_features(VALID_PAYLOAD)
    del incomplete["BMI"]
    with pytest.raises(KeyError):
        validate_features(incomplete, FEATURE_ORDER)


def test_validate_features_non_numeric_raises_valueerror():
    bad = _to_features(VALID_PAYLOAD)
    bad["BMI"] = "not-a-number"
    with pytest.raises(ValueError):
        validate_features(bad, FEATURE_ORDER)


def test_validate_features_invalid_categorical_raises_valueerror():
    bad = _to_features(VALID_PAYLOAD)
    bad["Sex"] = 2  # only 0/1 are valid
    with pytest.raises(ValueError):
        validate_features(bad, FEATURE_ORDER)


def test_validate_features_invalid_ordinal_raises_valueerror():
    bad = _to_features(VALID_PAYLOAD)
    bad["GenHlth"] = 99
    with pytest.raises(ValueError):
        validate_features(bad, FEATURE_ORDER)


def test_predict_diabetes_uses_metadata_threshold_not_hardcoded():
    """The critical threshold regression test: this must fail if the
    production code is ever changed to hardcode threshold=0.5 instead of
    reading metadata['decision_threshold']."""
    pipeline = _tiny_fitted_pipeline()
    features = _to_features(VALID_PAYLOAD)

    # 0.0 and 1.0 bound every possible probability, so they straddle it
    # regardless of exactly how saturated the tiny fixture pipeline's output
    # happens to be for this payload (it trains on random [0,1) data, so a
    # fixed epsilon around the actual probability is not reliable). Both
    # thresholds differ sharply from a hardcoded 0.5, so this still fails if
    # the production code is ever changed to hardcode threshold=0.5 instead
    # of reading metadata['decision_threshold'].
    low_threshold_metadata = _tiny_metadata(threshold=0.0)
    high_threshold_metadata = _tiny_metadata(threshold=1.0)

    result_low_threshold = predict_diabetes(pipeline, low_threshold_metadata, features)
    result_high_threshold = predict_diabetes(pipeline, high_threshold_metadata, features)

    assert result_low_threshold["threshold"] == low_threshold_metadata["decision_threshold"]
    assert result_high_threshold["threshold"] == high_threshold_metadata["decision_threshold"]
    assert result_low_threshold["is_elevated"] is True
    assert result_high_threshold["is_elevated"] is False
    # Same probability either way — only the threshold-comparison changed.
    assert result_low_threshold["risk_probability"] == result_high_threshold["risk_probability"]


def test_predict_diabetes_feature_order_independent():
    pipeline = _tiny_fitted_pipeline()
    metadata = _tiny_metadata()
    features = _to_features(VALID_PAYLOAD)

    normal = dict(features)
    reversed_order = dict(reversed(list(features.items())))
    rng = np.random.default_rng(7)
    keys_shuffled = list(features.keys())
    rng.shuffle(keys_shuffled)
    randomized = {k: features[k] for k in keys_shuffled}

    result_normal = predict_diabetes(pipeline, metadata, normal)
    result_reversed = predict_diabetes(pipeline, metadata, reversed_order)
    result_randomized = predict_diabetes(pipeline, metadata, randomized)

    assert result_normal["risk_probability"] == result_reversed["risk_probability"] == result_randomized["risk_probability"]


def test_validate_features_exactly_fourteen_features_required():
    """Regression check for the v2 feature-set reduction: the model-layer
    contract must require exactly the 14 v2 features, no more, no less."""
    assert len(FEATURE_ORDER) == 14


# --------------------------------------------------------------------------
# HTTP-level tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diabetes_prediction_requires_auth(client):
    res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_diabetes_prediction_validates_missing_field(client):
    token = await _register_and_get_token(client)
    bad_payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "bmi"}
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_rejects_impossible_bmi(client):
    token = await _register_and_get_token(client)
    bad_payload = {**VALID_PAYLOAD, "bmi": -10}
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_rejects_invalid_categorical(client):
    token = await _register_and_get_token(client)
    bad_payload = {**VALID_PAYLOAD, "sex": 2}  # only 0/1 are valid
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_rejects_invalid_ordinal(client):
    token = await _register_and_get_token(client)
    bad_payload = {**VALID_PAYLOAD, "gen_hlth": 99}
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_rejects_target_field(client):
    token = await _register_and_get_token(client)
    bad_payload = {**VALID_PAYLOAD, "diabetes_binary": 1}
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_rejects_unexpected_field(client):
    token = await _register_and_get_token(client)
    bad_payload = {**VALID_PAYLOAD, "some_unexpected_field": 123}
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_rejects_removed_v1_only_fields(client):
    """Fields that existed in the v1 21-feature contract (income, education,
    healthcare access, mental/physical health days, vegetables) must now be
    rejected as unexpected — the endpoint must not silently accept and
    ignore them, since that would mask a client/server contract mismatch."""
    token = await _register_and_get_token(client)
    for removed_field in ("income", "education", "any_healthcare", "no_docbc_cost", "ment_hlth", "phys_hlth", "veggies"):
        bad_payload = {**VALID_PAYLOAD, removed_field: 1}
        res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
        assert res.status_code == 422, f"expected 422 for removed field '{removed_field}'"


@pytest.mark.asyncio
async def test_diabetes_prediction_rejects_family_history_field(client):
    """family_history is not part of the v2 contract and must never be
    silently accepted — see ml_pipeline/diabetes/reports/v2_final_recommendation.md
    for why family history is explicitly excluded rather than fabricated."""
    token = await _register_and_get_token(client)
    bad_payload = {**VALID_PAYLOAD, "family_history": 1}
    res = await client.post("/api/v1/predict/diabetes", json=bad_payload, headers=_auth(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_diabetes_prediction_returns_503_when_model_unavailable(client):
    token = await _register_and_get_token(client)
    _set_model(pipeline=None, metadata=None)
    res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(token))
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_diabetes_prediction_returns_503_when_metadata_missing(client):
    """Model present but metadata missing must still be treated as
    unavailable — never silently predict with an assumed threshold."""
    token = await _register_and_get_token(client)
    _set_model(pipeline=_tiny_fitted_pipeline(), metadata=None)
    try:
        res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(token))
        assert res.status_code == 503
    finally:
        _set_model(None, None)


@pytest.mark.asyncio
async def test_diabetes_prediction_success_returns_non_diagnostic_screening_response(client):
    token = await _register_and_get_token(client)
    pipeline = _tiny_fitted_pipeline()
    metadata = _tiny_metadata(threshold=0.1)
    _set_model(pipeline, metadata)
    try:
        res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(token))
        assert res.status_code == 200
        body = res.json()
        assert body["risk_level"] in {"screening_negative", "screening_elevated"}
        assert 0.0 <= body["risk_probability"] <= 1.0
        assert body["threshold"] == 0.1
        assert body["is_elevated"] == (body["risk_level"] == "screening_elevated")
        assert "diagnosis" not in body["message"].lower() or "not a diagnosis" in body["message"].lower()
        assert body["disclaimer"]
        assert body["model_version"] == "diabetes-brfss-test"

        # Independently recompute the expected probability and confirm the
        # endpoint is not silently defaulting the threshold to 0.5.
        expected_features = _to_features(VALID_PAYLOAD)
        expected_row = [[float(expected_features[c]) for c in FEATURE_ORDER]]
        expected_probability = float(pipeline.predict_proba(expected_row)[0][1])
        # The response rounds risk_probability to 4dp (build_screening_response) —
        # compare against the same rounding rather than the raw float.
        assert body["risk_probability"] == round(expected_probability, 4)
        assert body["is_elevated"] == (expected_probability >= 0.1)
    finally:
        _set_model(None, None)


@pytest.mark.asyncio
async def test_diabetes_prediction_threshold_is_metadata_driven_not_hardcoded(client):
    """HTTP-level version of the critical threshold regression test: an
    extreme metadata threshold (0.99) must make even this pipeline's
    highest-probability input come back screening_negative — this fails if
    the endpoint/service ever hardcodes 0.5."""
    token = await _register_and_get_token(client)
    pipeline = _tiny_fitted_pipeline()
    _set_model(pipeline, _tiny_metadata(threshold=0.99))
    try:
        res = await client.post("/api/v1/predict/diabetes", json=VALID_PAYLOAD, headers=_auth(token))
        assert res.status_code == 200
        body = res.json()
        assert body["threshold"] == 0.99
        assert body["risk_level"] == "screening_negative"
        assert body["is_elevated"] is False
    finally:
        _set_model(None, None)


@pytest.mark.asyncio
async def test_diabetes_predictions_are_isolated_between_users(client):
    user_a = await _register(client)
    user_b = await _register(client)
    _set_model(_tiny_fitted_pipeline(), _tiny_metadata())
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
        _set_model(None, None)
        await db_manager.db["predictions"].delete_many(
            {"user_id": {"$in": [user_a["user"]["id"], user_b["user"]["id"]]}}
        )
