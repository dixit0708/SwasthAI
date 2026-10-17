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
        
        assert response.status_code in (200, 503)
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



