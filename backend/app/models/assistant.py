from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User's query or message for the AI Health Assistant")


class AssistantChatResponse(BaseModel):
    response: str = Field(..., description="AI health assistant reply")
    disclaimer: str = Field(..., description="Medical safety disclaimer")
    context_used: Dict[str, Any] = Field(default_factory=dict, description="Summary of user health profile and risk scores used")
    emergency: bool = Field(default=False, description="True when the message matched an emergency pattern and the fixed emergency response was returned")


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
    diabetes_risk_elevated: bool = False
    liver_risk_elevated: bool = False
    heart_risk_elevated: bool = False
    high_cholesterol: bool = False
    two_hour_glucose: Optional[float] = None
    age: Optional[int] = None
    activity_level: Optional[str] = None
    diet_preference: Optional[str] = None
    smoking_status: Optional[str] = None
    alcohol_use: Optional[str] = None
    sleep_hours: Optional[float] = None
    occupation_type: Optional[str] = None
    cuisine_region: Optional[str] = None


class ExerciseSession(BaseModel):
    day: str
    activity: str
    duration_minutes: int
    intensity: str = Field(..., description="rest, light, moderate or vigorous")


class ExercisePlan(BaseModel):
    level: str
    weekly_target: str
    timing_tip: Optional[str] = Field(default=None, description="When to exercise, for the user's daily routine")
    sessions: List[ExerciseSession]
    cautions: List[str] = Field(default_factory=list)
    personalised: bool = Field(
        default=False,
        description="False when the user's activity level is unknown and the gentlest plan was used",
    )


class MedicationScheduleItem(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    instructions: Optional[str] = None
    member_name: Optional[str] = None


class MedicationGuidance(BaseModel):
    medications: List[MedicationScheduleItem] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)


class Meal(BaseModel):
    slot: str = Field(..., description="e.g. Breakfast, Before your shift")
    time: str = Field(..., description="Suggested clock time, e.g. 8:00 am")
    items: List[str]
    tip: Optional[str] = None


class PlanFor(BaseModel):
    occupation: Optional[str] = None
    diet: Optional[str] = None
    region: Optional[str] = None


class MealPlan(BaseModel):
    plan_for: PlanFor
    schedule_note: Optional[str] = None
    meals: List[Meal]
    swaps: List[str] = Field(default_factory=list, description="Health-specific food swaps")


class AssessmentUsed(BaseModel):
    """The latest result of one risk assessment and how it shaped the plan."""
    assessment: str = Field(..., description="diabetes, heart or liver")
    label: str
    assessed_at: Optional[datetime] = None
    is_elevated: bool
    plan_effect: str


class DietRecommendationsResponse(BaseModel):
    user_id: str
    diet_types: List[str]
    metrics_evaluated: EvaluatedMetrics
    recommendations: List[DietRecommendationItem]
    lifestyle_guidance: List[str]
    routine_tips: List[str] = Field(default_factory=list, description="Tips for the user's daily routine (student, night shift, ...)")
    preference_notes: List[str] = Field(default_factory=list)
    meal_plan: MealPlan
    exercise_plan: ExercisePlan
    medication_guidance: MedicationGuidance
    assessments_used: List[AssessmentUsed] = Field(
        default_factory=list,
        description="Latest result of each diabetes, heart and liver assessment the plan used",
    )
    missing_inputs: List[str] = Field(
        default_factory=list,
        description="What the user could add for more personal guidance: height_weight, lifestyle, risk_assessment",
    )
    disclaimer: str
