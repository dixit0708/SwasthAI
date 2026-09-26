"""
Shared disclaimer text for AI-generated health output. Centralized so
every model/endpoint uses identical, reviewed wording (AGENTS.md Section 11).
"""

RISK_ASSESSMENT_DISCLAIMER = (
    "This is an AI-generated risk indicator based on the values you entered, "
    "not a medical diagnosis. Please consult a qualified healthcare "
    "professional to discuss these results and any next steps."
)

REPORT_ANALYSIS_DISCLAIMER = (
    "This summary is AI-generated from values automatically recognized in your "
    "report and may miss values, misread numbers, or use general reference ranges "
    "that differ from the ones printed on your own report. It is not a diagnosis. "
    "Always review the original report with a qualified healthcare professional, "
    "and contact one promptly if you have new or worsening symptoms."
)
