from typing import Literal, Optional

from pydantic import BaseModel


class LabValueOut(BaseModel):
    key: str
    label: str
    category: str
    # Plain-English "what this measures" line, shown regardless of status —
    # the actual jargon-translation the report analyzer exists to provide,
    # not just a re-statement of the number/range already on the report.
    # See PARAMETER_DESCRIPTIONS in lab_report_analysis.py.
    description: str = ""
    value: float
    unit: str
    reference_low: float
    reference_high: float
    status: Literal["low", "normal", "high"]


class QualitativeResultOut(BaseModel):
    """A screening test reported as Reactive/Non-Reactive or Positive/
    Negative rather than a number (e.g. HIV, Hepatitis B, Syphilis) — see
    app/ai/inference/lab_report_analysis.py's QUALITATIVE_TESTS table."""
    key: str
    label: str
    category: str
    description: str = ""
    status: Literal["normal", "abnormal"]


class ReportAnalysisOut(BaseModel):
    values: list[LabValueOut]
    qualitative_results: list[QualitativeResultOut] = []
    summary: str
    # Plain-language explanation from the LLM enhancement layer. None when
    # GEMINI_API_KEY isn't configured or the call failed — the rule-based
    # `summary` above is always present regardless (see
    # app/ai/inference/report_explanation.py).
    llm_explanation: Optional[str] = None
    questions_to_ask: list[str]
    disclaimer: str
    analyzer_version: str
