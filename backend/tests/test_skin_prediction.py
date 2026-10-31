import os
import cv2
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.ai.inference.image_processing import (
    apply_color_constancy,
    preprocess_for_skin,
    validate_skin_guardrail,
)

@pytest.fixture(autouse=True)
def ensure_skin_model_loaded():
    if getattr(app.state, "skin_model", None) is None:
        skin_ckpt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "ai", "models", "skin_cnn.pt")
        if os.path.exists(skin_ckpt):
            try:
                from app.ai.models.skin_model import load_skin_model
                app.state.skin_model, app.state.skin_idx_to_class = load_skin_model(skin_ckpt)
            except Exception:
                app.state.skin_model = None
                app.state.skin_idx_to_class = None

def test_color_constancy():
    # Create synthetic image with a strong blue color cast
    bgr_img = np.zeros((100, 100, 3), dtype=np.uint8)
    bgr_img[:, :, 0] = 220  # Blue
    bgr_img[:, :, 1] = 60   # Green
    bgr_img[:, :, 2] = 40   # Red
    
    balanced = apply_color_constancy(bgr_img)
    assert balanced.shape == (100, 100, 3)
    # The blue dominance should be reduced and balanced closer to the average
    mean_b = np.mean(balanced[:, :, 0])
    mean_r = np.mean(balanced[:, :, 2])
    assert abs(mean_b - mean_r) < 30

def test_preprocess_for_skin():
    test_img = np.ones((300, 400, 3), dtype=np.uint8) * 128
    preprocessed = preprocess_for_skin(test_img, target_size=(224, 224))
    
    assert preprocessed.shape == (4, 224, 224, 3)
    assert preprocessed.dtype == np.float32
    assert 0.0 <= preprocessed.min() <= preprocessed.max() <= 1.0

def test_skin_guardrails():
    # 1. Genuine skin tone patch -> ACCEPT
    skin_img = np.zeros((200, 200, 3), dtype=np.uint8)
    skin_img[:, :, 0] = np.clip(140 + np.random.randint(-15, 15, (200, 200)), 0, 255)
    skin_img[:, :, 1] = np.clip(180 + np.random.randint(-15, 15, (200, 200)), 0, 255)
    skin_img[:, :, 2] = np.clip(220 + np.random.randint(-15, 15, (200, 200)), 0, 255)
    is_valid, msg, meta = validate_skin_guardrail(skin_img)
    assert is_valid is True
    assert meta["skin_coverage"] > 80.0

    # 2. Monochromatic X-ray / Grayscale scan -> REJECT
    xray_base = np.random.randint(40, 200, (200, 200), dtype=np.uint8)
    xray_img = cv2.merge([xray_base, xray_base, xray_base])
    is_valid, msg, meta = validate_skin_guardrail(xray_img)
    assert is_valid is False
    assert meta["rejection_type"] == "RADIOGRAPHIC_XRAY"

    # 3. Dark / Empty photo -> REJECT
    dark_img = np.zeros((200, 200, 3), dtype=np.uint8)
    is_valid, msg, meta = validate_skin_guardrail(dark_img)
    assert is_valid is False
    assert meta["rejection_type"] == "DARK_OR_BLANK"

    # 4. White document / paper -> REJECT
    doc_img = np.ones((200, 200, 3), dtype=np.uint8) * 240
    is_valid, msg, meta = validate_skin_guardrail(doc_img)
    assert is_valid is False

@pytest.mark.asyncio
async def test_skin_prediction_endpoint():
    # Encode synthetic skin patch
    skin_img = np.zeros((200, 200, 3), dtype=np.uint8)
    skin_img[:, :, 0] = np.clip(140 + np.random.randint(-15, 15, (200, 200)), 0, 255)
    skin_img[:, :, 1] = np.clip(180 + np.random.randint(-15, 15, (200, 200)), 0, 255)
    skin_img[:, :, 2] = np.clip(220 + np.random.randint(-15, 15, (200, 200)), 0, 255)
    _, encoded = cv2.imencode('.jpg', skin_img)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {'file': ('skin.jpg', encoded.tobytes(), 'image/jpeg')}
        response = await ac.post("/api/v1/predict/skin", files=files)
        
        assert response.status_code in (200, 400, 503)
        if response.status_code == 200:
            data = response.json()
            assert "label" in data
            assert "confidence" in data
            assert "differential_diagnosis" in data
            assert isinstance(data["differential_diagnosis"], list)
            assert len(data["differential_diagnosis"]) == 3
            for item in data["differential_diagnosis"]:
                assert "label" in item
                assert "confidence" in item
                assert "percentage" in item

@pytest.mark.asyncio
async def test_skin_prediction_endpoint_rejects_xray():
    # Encode monochromatic X-ray
    xray_base = np.random.randint(40, 200, (200, 200), dtype=np.uint8)
    xray_img = cv2.merge([xray_base, xray_base, xray_base])
    _, encoded = cv2.imencode('.jpg', xray_img)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {'file': ('xray.jpg', encoded.tobytes(), 'image/jpeg')}
        response = await ac.post("/api/v1/predict/skin", files=files)
        if response.status_code == 503:
            pytest.skip("Skin model not loaded (Git LFS weights not pulled)")
        assert response.status_code == 400
        assert "radiographic scan" in response.json().get("detail", "").lower()

def test_skin_guardrail_rejects_animal():
    import os
    lion_path = r'c:\Users\dhruv\Pictures\pexels-pixabay-33045.jpg'
    if os.path.exists(lion_path):
        lion_img = cv2.imread(lion_path)
        is_valid, msg, meta = validate_skin_guardrail(lion_img)
        assert is_valid is False
        assert meta["rejection_type"] == "ANIMAL"


@pytest.mark.asyncio
async def test_skin_save_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "label": "Acne and Rosacea",
            "confidence": 0.85,
            "confidence_level": "High",
            "differential_diagnosis": [
                {"label": "Acne and Rosacea", "confidence": 0.85, "percentage": 85.0}
            ]
        }
        res = await ac.post("/api/v1/predict/skin/save", json=payload)
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_family_profiles_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/predict/family-profiles")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_save_and_family_profiles(client):
    from app.api.v1.deps import get_current_user
    from app.models.user import UserOut

    fake_user = UserOut(
        id="mock_user_12345",
        email="test_user@example.com",
        name="Test Patient",
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        # 1. Test family profiles returns personal profile
        prof_res = await client.get("/api/v1/predict/family-profiles")
        assert prof_res.status_code == 200
        profiles = prof_res.json().get("profiles", [])
        assert len(profiles) >= 1
        assert profiles[0]["id"] == "self"

        # 2. Test saving skin prediction to health records (self)
        payload = {
            "label": "Eczema Photos",
            "confidence": 0.78,
            "confidence_level": "High",
            "differential_diagnosis": [
                {"label": "Eczema Photos", "confidence": 0.78, "percentage": 78.0},
                {"label": "Atopic Dermatitis Photos", "confidence": 0.15, "percentage": 15.0},
                {"label": "Contact Dermatitis", "confidence": 0.07, "percentage": 7.0}
            ],
            "family_member_id": "self"
        }
        save_res = await client.post("/api/v1/predict/skin/save", json=payload)
        assert save_res.status_code == 200
        assert save_res.json().get("status") == "saved"
        assert "id" in save_res.json()

        # 3. Test saving with unauthorized / non-belonging family_member_id returns 403
        unauthorized_payload = dict(payload)
        unauthorized_payload["family_member_id"] = "507f1f77bcf86cd799439011"  # valid ObjectId, but not user's
        unauth_res = await client.post("/api/v1/predict/skin/save", json=unauthorized_payload)
        assert unauth_res.status_code == 403
        assert "Forbidden" in unauth_res.json().get("detail", "")

        # 4. Test saving with invalid family_member_id format returns 403
        invalid_payload = dict(payload)
        invalid_payload["family_member_id"] = "invalid_id_format"
        invalid_res = await client.post("/api/v1/predict/skin/save", json=invalid_payload)
        assert invalid_res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)






