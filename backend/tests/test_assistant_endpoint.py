from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
import pytest

from app.core.config import settings
from app.db.collections import AIConversationRepository, HealthProfileRepository, PredictionRepository
from conftest import unique_email

VALID_PASSWORD = "Correct-Horse9-Battery"


async def _register_and_get_token(client, email=None, name="Test User") -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email or unique_email(), "password": VALID_PASSWORD},
    )
    assert res.status_code == 201
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_assistant_chat_requires_auth(client):
    res = await client.post("/api/v1/assistant/chat", json={"message": "Hello"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_assistant_diet_requires_auth(client):
    res = await client.get("/api/v1/assistant/diet")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_diet_recommendations_route_requires_auth(client):
    res = await client.get("/api/v1/diet/recommendations")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_assistant_chat_with_mocked_gemini(client):
    token = await _register_and_get_token(client)

    # Seed health profile & prediction in test DB
    await client.put(
        "/api/v1/health-profile/me",
        headers=_auth(token),
        json={"blood_group": "O+", "date_of_birth": "1990-05-15"},
    )
    await client.post(
        "/api/v1/health-profile/me/conditions",
        headers=_auth(token),
        json={"label": "Hypertension"},
    )

    mock_gemini_reply = (
        "Based on your profile, managing blood pressure and staying active is key. "
        "Here are evidence-based recommendations..."
    )

    original_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "mock-api-key"

    try:
        mock_response = MagicMock(text=mock_gemini_reply)
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client) as mock_client_cls:
            res = await client.post(
                "/api/v1/assistant/chat",
                headers=_auth(token),
                json={"message": "What should I eat to stay healthy?"},
            )

            assert res.status_code == 200
            data = res.json()
            assert data["response"] == mock_gemini_reply
            assert "disclaimer" in data
            assert data["context_used"]["blood_group"] == "O+"
            assert "Hypertension" in data["context_used"]["conditions"]

            # Verify Gemini client called with key
            mock_client_cls.assert_called_once_with(api_key="mock-api-key")
            _, kwargs = mock_client.models.generate_content.call_args
            config = kwargs["config"]
            assert "SwasthAI" in config.system_instruction
            assert "Hypertension" in config.system_instruction

    finally:
        settings.GEMINI_API_KEY = original_key


@pytest.mark.asyncio
async def test_assistant_chat_fallback_when_api_key_missing(client):
    token = await _register_and_get_token(client)

    original_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = ""

    try:
        res = await client.post(
            "/api/v1/assistant/chat",
            headers=_auth(token),
            json={"message": "How do I lower my blood sugar?"},
        )

        assert res.status_code == 200
        data = res.json()
        assert "SwasthAI" in data["response"]
        assert "disclaimer" in data
    finally:
        settings.GEMINI_API_KEY = original_key


@pytest.mark.asyncio
async def test_diet_endpoint_returns_structured_recommendations_for_user(client):
    token = await _register_and_get_token(client)

    # 1. Test via /api/v1/diet/recommendations
    res = await client.get("/api/v1/diet/recommendations", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert "diet_types" in data
    assert "recommendations" in data
    assert "lifestyle_guidance" in data
    assert "disclaimer" in data
    assert "user_id" in data

    # 2. Test via /api/v1/assistant/diet
    res2 = await client.get("/api/v1/assistant/diet", headers=_auth(token))
    assert res2.status_code == 200
    assert res2.json()["diet_types"] == data["diet_types"]
