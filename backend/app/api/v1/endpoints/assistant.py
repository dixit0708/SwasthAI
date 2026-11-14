import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_user
from app.core.rate_limit import SlidingWindowRateLimiter
from app.models.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    DietRecommendationsResponse,
)
from app.models.user import UserOut
from app.services import assistant_service, diet_service

logger = logging.getLogger(__name__)

router = APIRouter()

# The chat calls a quota-limited LLM and is the most misuse-prone route, so
# it gets its own per-user limit (AGENTS.md Section 47).
chat_rate_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60)


@router.post(
    "/chat",
    summary="Chat with AI Health Assistant",
    response_model=AssistantChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat_with_assistant_endpoint(
    payload: AssistantChatRequest,
    current_user: UserOut = Depends(get_current_user),
):
    """
    Submits a message to SwasthAI's AI Health Assistant.
    Retrieves the authenticated user's HealthProfile and latest prediction
    risk scores, injects them into Google Gemini's system prompt, and returns
    personalized guidance accompanied by a medical safety disclaimer.
    """
    if not chat_rate_limiter.allow(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You're sending messages very quickly. Please wait a minute and try again.",
        )
    try:
        return await assistant_service.chat_with_assistant(
            user_id=current_user.id,
            message=payload.message,
        )
    except Exception as e:
        logger.error(f"Assistant chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health assistant service error. Please try again later.",
        )


@router.get(
    "/diet",
    summary="Get Rule-Based Diet Recommendations for Current User",
    response_model=DietRecommendationsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_user_diet_guidance_endpoint(
    current_user: UserOut = Depends(get_current_user),
):
    """
    Evaluates the authenticated user's saved records (BMI, heart risk, blood pressure,
    fasting glucose, and existing conditions) using the strictly rule-based diet engine.
    """
    try:
        return await diet_service.get_diet_and_lifestyle_guidance(user_id=current_user.id)
    except Exception as e:
        logger.error(f"Diet guidance retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate dietary recommendations. Please try again later.",
        )
