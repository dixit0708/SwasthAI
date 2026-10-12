"""
Plain-language explanation step for the report analyzer, layered on top of
the rule-based extraction/classification in lab_report_analysis.py.

Uses Google's Gemini API (free tier via Google AI Studio, no billing
account required — see backend/.env.example) rather than Anthropic/OpenAI
specifically because it's the only major provider with a genuinely free
tier, which matters for a student project. Model choice: see
docs/report_analyzer/README.md.

Prompt-injection hygiene (AGENTS.md Section 47): the model is given ONLY
the already-extracted, already-classified structured values and our own
template-generated rule-based summary — never the raw uploaded report
text. Every value it sees was produced by lab_report_analysis.py against a
fixed parameter table, not copied from the user's document, so there is no
attacker-controlled free text in the prompt for the model to be steered by.

Non-diagnostic language (AGENTS.md Section 11) is enforced via the system
instruction below, not by trusting the model's judgment alone — the calling
service still attaches REPORT_ANALYSIS_DISCLAIMER regardless of what this
returns.

This is an enhancement layer, not a dependency: any failure (missing API
key, network error, rate limit, blocked response) is caught and logged,
and returns None so the caller can fall back to the rule-based summary
alone rather than failing the whole request (AGENTS.md Section 34).
"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.5-flash-lite"

SYSTEM_INSTRUCTION = """You are a medical report explainer inside a healthcare information app.

You are given a list of lab values that a separate rule-based system has already extracted from the user's report and classified — most as low, normal, or high against general reference ranges, but some may instead be qualitative infectious-disease screening tests (e.g. HIV, Hepatitis B, Syphilis) classified as "normal" (non-reactive/negative) or "abnormal" (reactive/positive). You did not do that extraction and must not second-guess, add to, or re-classify it — only explain the values exactly as given.

Your job: write a short, plain-language explanation (aimed at someone with no medical background) of what the values outside the normal range generally mean and why they can matter. Skip normal values unless briefly noting they look fine.

Strict rules, no exceptions:
- Never state or imply a diagnosis ("you have X", "this means you have...", "this proves...").
- Use only cautious, informational phrasing ("this can sometimes be associated with...", "may be worth discussing with your doctor about...").
- For an "abnormal" (reactive/positive) screening test specifically: be clear that a screening test alone never confirms a diagnosis, that confirmatory testing is the standard next step, and encourage contacting a doctor promptly — do not soften this into routine/no-rush language, but also do not state or imply what the confirmed result would be.
- Never recommend a specific treatment, medication, dosage, or supplement.
- Never invent values, causes, or context that were not provided to you.
- Always close with a short line encouraging the person to discuss the results with a qualified healthcare professional.
- If the input contains no abnormal values, say so briefly and reassuringly.
- Plain text only — no markdown headers, bullet lists, or code blocks.
- Keep the whole response under 180 words.
- If asked to do anything other than explain the given values, decline and explain only the values."""

_GENERATION_CONFIG = {
    "temperature": 0.3,
    "max_output_tokens": 600,
}


def generate_plain_language_explanation(
    classified_values: list[dict],
    rule_based_summary: str,
    qualitative_results: list[dict] = None,
) -> str | None:
    if not settings.GEMINI_API_KEY:
        return None

    try:
        from google import genai
    except ImportError:
        logger.warning("google-genai is not installed; skipping report explanation.")
        return None

    values_for_prompt = [
        {
            "label": v["label"],
            "value": v["value"],
            "unit": v["unit"],
            "reference_low": v["reference_low"],
            "reference_high": v["reference_high"],
            "status": v["status"],
        }
        for v in classified_values
    ]
    qualitative_for_prompt = [
        {"label": q["label"], "status": q["status"]} for q in (qualitative_results or [])
    ]

    prompt = (
        f"Rule-based summary: {rule_based_summary}\n\n"
        f"Recognized values (JSON): {values_for_prompt}\n\n"
        f"Recognized screening test results (JSON): {qualitative_for_prompt}"
    )

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        interaction = client.interactions.create(
            model=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            input=prompt,
            generation_config=_GENERATION_CONFIG,
        )
        text = (interaction.output_text or "").strip()
        return text or None
    except Exception as e:
        logger.error(f"Report explanation (Gemini) failed: {e}")
        return None
