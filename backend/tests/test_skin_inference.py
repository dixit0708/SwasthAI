"""
Regression tests for the skin-disease detection pipeline
(backend/app/ai/models/skin_model.py + image_processing.preprocess_for_skin).

These are structural/architectural correctness checks, not accuracy checks —
no labeled DermNet validation data is available in this environment (the
dataset is gitignored and was never downloaded here), so these tests
cannot and do not assert "image X should predict class Y". Instead they
guard against the exact bug classes this audit checked for: a checkpoint
that fails to load, a class-mapping length mismatch, a wrong output shape,
an out-of-range prediction index, and a broken API contract for valid vs.
invalid input.

No Playwright. No browser automation.
"""
import io
from pathlib import Path

import numpy as np
import pytest
import torch
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.ai.inference.image_processing import preprocess_for_skin
from app.ai.models.skin_model import build_skin_model, load_skin_model, predict_skin
from app.main import app

CKPT_PATH = Path(__file__).parent.parent / "app" / "ai" / "models" / "skin_cnn.pt"
CKPT_AVAILABLE = CKPT_PATH.exists()

pytestmark = pytest.mark.skipif(
    not CKPT_AVAILABLE,
    reason="skin_cnn.pt checkpoint not present (Git LFS object not pulled in this environment)",
)


@pytest.fixture(scope="module")
def loaded_model():
    return load_skin_model(str(CKPT_PATH))


def make_synthetic_image(seed: int = 0) -> np.ndarray:
    """A deterministic, non-trivial 400x400x3 BGR array — stands in for a
    decoded upload without needing a real file on disk."""
    rng = np.random.RandomState(seed)
    return rng.randint(0, 255, (400, 400, 3), dtype=np.uint8)


def test_model_loads_successfully(loaded_model):
    model, idx_to_class = loaded_model
    assert model is not None
    assert isinstance(idx_to_class, dict)
    assert len(idx_to_class) > 0


def test_checkpoint_missing_raises_filenotfounderror():
    with pytest.raises(FileNotFoundError):
        load_skin_model("this/path/does/not/exist.pt")


def test_class_mapping_matches_model_output_classes(loaded_model):
    model, idx_to_class = loaded_model
    num_classes_in_mapping = len(idx_to_class)
    # fc is the final linear layer; out_features must equal the number of
    # classes the checkpoint's class_to_idx declares. If someone edits the
    # checkpoint's mapping without matching the trained weights, this fails.
    num_classes_in_model = model.fc.out_features
    assert num_classes_in_mapping == num_classes_in_model


def test_class_mapping_is_dense_and_unique(loaded_model):
    """Indices must be exactly 0..N-1 with no gaps or duplicates — a
    reordering/off-by-one bug would surface as a missing or duplicate index."""
    _, idx_to_class = loaded_model
    indices = sorted(idx_to_class.keys())
    assert indices == list(range(len(idx_to_class)))
    assert len(set(idx_to_class.values())) == len(idx_to_class)  # no duplicate class names


def test_model_is_in_eval_mode(loaded_model):
    model, _ = loaded_model
    assert model.training is False


def test_preprocessing_output_shape_and_dtype():
    raw = make_synthetic_image()
    preprocessed = preprocess_for_skin(raw)
    assert preprocessed.shape == (1, 224, 224, 3)
    assert preprocessed.dtype == np.float32
    # Normalized to [0, 1], not left as raw 0-255 pixel values
    assert preprocessed.min() >= 0.0
    assert preprocessed.max() <= 1.0


def test_preprocessing_converts_bgr_to_rgb():
    """A pixel that is pure red when read in OpenCV's native BGR channel
    order (index 2 = R = 255, indices 0/1 = 0) must land in the RGB
    tensor's first channel — catches an accidental missing/duplicated
    color-channel swap. (BGR->RGB reorders channels; it does not change
    which color a pixel represents.)"""
    raw = np.zeros((300, 300, 3), dtype=np.uint8)
    raw[:, :] = (0, 0, 255)  # BGR order: B=0, G=0, R=255 -> this pixel is red
    preprocessed = preprocess_for_skin(raw)
    r, g, b = preprocessed[0, 112, 112]
    assert r > 0.9 and g < 0.1 and b < 0.1


def test_prediction_index_within_valid_range(loaded_model):
    model, idx_to_class = loaded_model
    raw = make_synthetic_image(seed=1)
    preprocessed = preprocess_for_skin(raw)
    image_transposed = np.transpose(preprocessed, (0, 3, 1, 2))
    tensor_img = torch.tensor(image_transposed, dtype=torch.float32)
    with torch.no_grad():
        outputs = model(tensor_img)
    assert outputs.shape == (1, len(idx_to_class))
    pred_idx = int(torch.argmax(outputs, dim=1)[0])
    assert 0 <= pred_idx < len(idx_to_class)


def test_predict_skin_returns_valid_label_or_ood(loaded_model):
    model, idx_to_class = loaded_model
    raw = make_synthetic_image(seed=2)
    preprocessed = preprocess_for_skin(raw)
    result = predict_skin(model, idx_to_class, preprocessed)
    if result.get("prediction") == "OOD":
        assert "message" in result
    else:
        assert result["label"] in idx_to_class.values()
        assert 0.0 <= result["confidence"] <= 1.0


def test_predict_skin_is_deterministic(loaded_model):
    """Same input, same output every time — model.eval() must have actually
    disabled dropout/batchnorm-update randomness."""
    model, idx_to_class = loaded_model
    raw = make_synthetic_image(seed=3)
    preprocessed = preprocess_for_skin(raw)
    results = [predict_skin(model, idx_to_class, preprocessed) for _ in range(3)]
    assert results[0] == results[1] == results[2]


def test_build_skin_model_respects_num_classes():
    model = build_skin_model(num_classes=7)
    assert model.fc.out_features == 7


# ---------------------------------------------------------------------------
# API-level tests. The skin endpoint requires no auth (mirrors /predict/pneumonia).
# app.state.skin_model/skin_idx_to_class are set directly here rather than
# relying on the app's lifespan startup, matching this project's existing
# pattern (see test_predictions.py's module docstring) — but using the real
# loaded checkpoint, since it's actually present in this environment.
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(seed: int = 0) -> bytes:
    rng = np.random.RandomState(seed)
    arr = rng.randint(0, 255, (300, 300, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def skin_model_on_app_state(loaded_model):
    model, idx_to_class = loaded_model
    app.state.skin_model = model
    app.state.skin_idx_to_class = idx_to_class
    yield
    app.state.skin_model = None
    app.state.skin_idx_to_class = None


@pytest.mark.asyncio
async def test_skin_endpoint_valid_image_returns_label_or_ood(skin_model_on_app_state):
    """The route converts an OOD result into a 400 with the guidance message
    in `detail` (see predict.py: `if result.get("prediction") == "OOD":
    raise ValueError(...)`) — a genuine classification returns 200 with
    `label`/`confidence`. Both are valid, well-formed outcomes for a random
    synthetic image; this test accepts either rather than assuming one."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.jpg", _make_jpeg_bytes(), "image/jpeg")}
        response = await ac.post("/api/v1/predict/skin", files=files)
    if response.status_code == 200:
        body = response.json()
        assert "label" in body and "confidence" in body
    else:
        assert response.status_code == 400
        assert "detail" in response.json()


@pytest.mark.asyncio
async def test_skin_endpoint_rejects_non_image_file(skin_model_on_app_state):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/api/v1/predict/skin", files=files)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_skin_endpoint_returns_503_when_model_unavailable():
    previous_model = getattr(app.state, "skin_model", None)
    previous_idx = getattr(app.state, "skin_idx_to_class", None)
    app.state.skin_model = None
    app.state.skin_idx_to_class = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            files = {"file": ("test.jpg", _make_jpeg_bytes(), "image/jpeg")}
            response = await ac.post("/api/v1/predict/skin", files=files)
        assert response.status_code == 503
    finally:
        app.state.skin_model = previous_model
        app.state.skin_idx_to_class = previous_idx
