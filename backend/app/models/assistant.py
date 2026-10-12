from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User's query or message for the AI Health Assistant")


class AssistantChatResponse(BaseModel):
    response: str = Field(..., description="AI health assistant reply")
    disclaimer: str = Field(..., description="Medical safety disclaimer")
    context_used: Dict[str, Any] = Field(default_factory=dict, description="Summary of user health profile and risk scores used")


class DietRecommendationItem(BaseModel):
    category: str = Field(..., description="Health category or area of focus")
    diet: str = Field(..., description="Recommended dietary pattern")
    reason: str = Field(..., description="Clinical reason or triggered rule")
    rules: List[str] = Field(..., description="Actionable dietary rules")


class EvaluatedMetrics(BaseModel):
    bmi: Optional[float] = None
    heart_risk: Optional[float] = None
    high_bp: bool = False
    fasting_glucose: Optional[float] = None
    conditions: List[str] = Field(default_factory=list)


class DietRecommendationsResponse(BaseModel):
    user_id: str
    diet_types: List[str]
    metrics_evaluated: EvaluatedMetrics
    recommendations: List[DietRecommendationItem]
    lifestyle_guidance: List[str]
    disclaimer: str
