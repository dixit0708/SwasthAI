"""
Turns a raw model probability into a non-diagnostic, patient-friendly risk
response. Every structured-data risk model (diabetes, and future heart/liver
models) should route its output through this before it reaches the API
response — this is the single place that enforces AGENTS.md Section 11
("never present AI output as a definitive diagnosis").
"""
from app.ai.safety.medical_disclaimer import RISK_ASSESSMENT_DISCLAIMER

ELEVATED_THRESHOLD = 0.66
MODERATE_THRESHOLD = 0.33


def build_risk_response(condition_label: str, risk_probability: float, model_version: str) -> dict:
    if risk_probability >= ELEVATED_THRESHOLD:
        risk_level = "elevated"
        message = (
            f"Your inputs show several elevated risk indicators for {condition_label}. "
            f"This is not a diagnosis — please discuss these results with a qualified "
            f"healthcare professional."
        )
    elif risk_probability >= MODERATE_THRESHOLD:
        risk_level = "moderate"
        message = (
            f"Your inputs show some moderate risk indicators for {condition_label}. "
            f"Consider discussing these results with a healthcare professional, "
            f"especially alongside any other risk factors you may have."
        )
    else:
        risk_level = "low"
        message = (
            f"Your inputs show low risk indicators for {condition_label} based on this "
            f"assessment. Continue maintaining healthy habits and routine checkups."
        )

    return {
        "risk_level": risk_level,
        "risk_probability": round(float(risk_probability), 4),
        "message": message,
        "model_version": model_version,
        "disclaimer": RISK_ASSESSMENT_DISCLAIMER,
    }
