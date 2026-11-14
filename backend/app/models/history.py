"""Response models for the user's saved results (risk assessments and
analysed lab reports). These deliberately leave out the raw inputs the
user typed in: a history list only needs the outcome."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.report_analysis import ReportAnalysisOut


class PredictionHistoryItem(BaseModel):
    id: str
    # Stable key for the kind of assessment, e.g. "heart_disease".
    condition: str
    # Patient-friendly name, e.g. "Heart Disease Risk Assessment".
    condition_label: str
    # Which assessment page produced it, e.g. "heart" -> prediction-heart.html.
    assessment: str
    created_at: Optional[datetime] = None
    # Structured-data assessments
    risk_level: Optional[str] = None
    risk_probability: Optional[float] = None
    is_elevated: Optional[bool] = None
    message: Optional[str] = None
    # Image assessments (skin)
    label: Optional[str] = None
    confidence_level: Optional[str] = None
    # Set when the result was saved for a family member.
    family_member_id: Optional[str] = None
    family_member_name: Optional[str] = None


class PredictionHistoryResponse(BaseModel):
    items: List[PredictionHistoryItem]
    total: int
    page: int
    page_size: int


class ReportHistoryItem(BaseModel):
    id: str
    filename: str
    created_at: Optional[datetime] = None
    summary: str
    values_count: int
    # Numeric values outside their reference range plus reactive/positive
    # screening results.
    flagged_count: int


class ReportHistoryResponse(BaseModel):
    items: List[ReportHistoryItem]
    total: int
    page: int
    page_size: int


class ReportDetailOut(ReportAnalysisOut):
    id: str
    filename: str
    created_at: Optional[datetime] = None
