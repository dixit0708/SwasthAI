import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_user
from app.models.assistant import DietRecommendationsResponse
from app.models.user import UserOut
from app.services import diet_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/recommendations",
    summary="Get Rule-Based Diet Recommendations",
    response_model=DietRecommendationsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_diet_recommendations_endpoint(
    current_user: UserOut = Depends(get_current_user),
):
    """
    Evaluates the authenticated user's database records to produce structured,
    rule-based diet and lifestyle recommendations.
    """
    try:
        return await diet_service.get_diet_and_lifestyle_guidance(user_id=current_user.id)
    except Exception as e:
        logger.error(f"Error fetching diet recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate dietary recommendations. Please try again later.",
        )
