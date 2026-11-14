"""
AI Health Assistant Service (Module 2).

Integrates Google Gemini API using the exact configuration and API key setup
from the report analyzer (app/ai/inference/report_explanation.py and image_ocr.py).
Injects authenticated user's HealthProfile and latest prediction risk scores into
Gemini's system prompt to provide personalized, clinically safe health guidance.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from starlette.concurrency import run_in_threadpool

from app.ai.safety.emergency_detection import detect_emergency, emergency_response
from app.core.config import settings
from app.db.collections import (
    ai_conversation_repo,
    health_profile_repo,
    prediction_repo,
)

logger = logging.getLogger(__name__)

# Reusing exact Gemini model name from existing report analyzer
# Primary model; fallbacks are tried in order if 503/429 is returned.
MODEL_NAME = "gemini-3.5-flash-lite"
_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash-latest"]
# Hard ceiling on a single Gemini call, in milliseconds. Without it a stalled
# upstream request held the chat open for minutes; on timeout the assistant
# falls back to the "temporarily unavailable" reply below.
GEMINI_TIMEOUT_MS = 20_000

ASSISTANT_DISCLAIMER = (
    "SwasthAI Health Assistant is an AI-powered health information and decision-support tool. "
    "It does not provide definitive medical diagnoses, prescriptions, or replace clinical consultation "
    "with a licensed physician or healthcare specialist. If you are experiencing severe or acute "
    "symptoms, please seek immediate medical care."
)


async def get_user_health_context(user_id: str) -> Dict[str, Any]:
    """
    Fetches the authenticated user's current HealthProfile and latest prediction
    risk scores to build a contextual summary for the AI assistant.
    """
    # 1. Fetch Health Profile
    profile_doc = await health_profile_repo.collection.find_one({"user_id": user_id})
    conditions: List[str] = []
    blood_group: Optional[str] = None
    date_of_birth: Optional[str] = None

    if profile_doc:
        blood_group = profile_doc.get("blood_group")
        date_of_birth = profile_doc.get("date_of_birth")
        raw_conditions = profile_doc.get("conditions", [])
        conditions = [
            c.get("label", "") for c in raw_conditions if isinstance(c, dict) and c.get("label")
        ]

    # 2. Fetch Latest Predictions
    cursor = prediction_repo.collection.find({"user_id": user_id}).sort("created_at", -1)
    predictions = await cursor.to_list(length=30)

    extracted_bmi: Optional[float] = None
    heart_risk_prob: Optional[float] = None
    heart_risk_level: Optional[str] = None
    diabetes_risk_prob: Optional[float] = None
    diabetes_risk_level: Optional[str] = None
    liver_risk_prob: Optional[float] = None
    liver_risk_level: Optional[str] = None
    blood_pressure: Optional[str] = None
    fasting_glucose: Optional[float] = None

    for pred in predictions:
        snapshot = pred.get("input_snapshot") or {}
        result = pred.get("result") or {}
        condition_name = pred.get("condition", "")

        # Extract BMI from snapshots
        if extracted_bmi is None:
            bmi_val = snapshot.get("bmi") or snapshot.get("BMI") or snapshot.get("BMXBMI")
            if bmi_val is not None:
                try:
                    extracted_bmi = round(float(bmi_val), 1)
                except (ValueError, TypeError):
                    pass

        # Extract Heart Risk
        if heart_risk_prob is None and "heart" in condition_name:
            prob = result.get("risk_probability")
            if prob is not None:
                try:
                    heart_risk_prob = float(prob)
                    heart_risk_level = result.get("risk_level", "screening_elevated" if prob >= 0.50 else "screening_negative")
                except (ValueError, TypeError):
                    pass

        # Extract Diabetes Risk
        if diabetes_risk_prob is None and "diabetes" in condition_name:
            prob = result.get("risk_probability")
            if prob is not None:
                try:
                    diabetes_risk_prob = float(prob)
                    diabetes_risk_level = result.get("risk_level", "screening_elevated" if prob >= 0.50 else "screening_negative")
                except (ValueError, TypeError):
                    pass

        # Extract Liver Risk
        if liver_risk_prob is None and "liver" in condition_name:
            prob = result.get("risk_probability")
            if prob is not None:
                try:
                    liver_risk_prob = float(prob)
                    liver_risk_level = result.get("risk_level", "screening_elevated" if prob >= 0.50 else "screening_negative")
                except (ValueError, TypeError):
                    pass

        # Extract Blood Pressure & Glucose readings
        if blood_pressure is None:
            sys_val = snapshot.get("BPXSY1") or snapshot.get("systolic_bp")
            dia_val = snapshot.get("BPXDI1") or snapshot.get("diastolic_bp") or snapshot.get("BloodPressure")
            if sys_val and dia_val:
                blood_pressure = f"{sys_val}/{dia_val} mmHg"
            elif snapshot.get("HighBP") == 1 or snapshot.get("high_bp") == 1:
                blood_pressure = "Elevated (Survey reported)"

        if fasting_glucose is None:
            gluc = snapshot.get("LBXGLU") or snapshot.get("fasting_glucose") or snapshot.get("Glucose")
            if gluc is not None:
                try:
                    fasting_glucose = round(float(gluc), 1)
                except (ValueError, TypeError):
                    pass

    return {
        "bmi": extracted_bmi,
        "heart_risk": heart_risk_prob,
        "heart_risk_level": heart_risk_level,
        "diabetes_risk": diabetes_risk_prob,
        "diabetes_risk_level": diabetes_risk_level,
        "liver_risk": liver_risk_prob,
        "liver_risk_level": liver_risk_level,
        "blood_pressure": blood_pressure,
        "fasting_glucose": fasting_glucose,
        "conditions": conditions,
        "blood_group": blood_group,
        "date_of_birth": date_of_birth,
    }


def _build_system_instruction(context: Dict[str, Any]) -> str:
    """
    Constructs the system prompt injecting user metrics and medical safety rules.
    """
    bmi_str = f"{context['bmi']}" if context.get("bmi") is not None else "Not recorded"
    
    heart_str = (
        f"{round(context['heart_risk'] * 100, 1)}% ({context.get('heart_risk_level')})"
        if context.get("heart_risk") is not None
        else "Not recorded"
    )
    diabetes_str = (
        f"{round(context['diabetes_risk'] * 100, 1)}% ({context.get('diabetes_risk_level')})"
        if context.get("diabetes_risk") is not None
        else "Not recorded"
    )
    liver_str = (
        f"{round(context['liver_risk'] * 100, 1)}% ({context.get('liver_risk_level')})"
        if context.get("liver_risk") is not None
        else "Not recorded"
    )
    conditions_str = ", ".join(context.get("conditions") or []) or "None reported"
    bp_str = context.get("blood_pressure") or "Not recorded"
    glucose_str = f"{context['fasting_glucose']} mg/dL" if context.get("fasting_glucose") is not None else "Not recorded"

    return f"""You are SwasthAI, an intelligent, empathetic, and evidence-informed AI Health Assistant.

The authenticated user's current health context from their SwasthAI records:
- Body Mass Index (BMI): {bmi_str}
- Latest Heart Disease Risk: {heart_str}
- Latest Diabetes Risk: {diabetes_str}
- Latest Liver Disease Risk: {liver_str}
- Known Medical Conditions: {conditions_str}
- Blood Pressure: {bp_str}
- Fasting Glucose: {glucose_str}
- Blood Group: {context.get('blood_group') or 'Not recorded'}

Strict Clinical Safety & Communication Rules (AGENTS.md Section 11):
1. Provide personalized, constructive, and empathetic health guidance directly addressing the user's question, grounding insights in their health parameters.
2. NON-DIAGNOSTIC MANDATE: Never state or imply a definitive medical diagnosis (avoid 'you have X' or 'you are diagnosed with X'). Use cautious, supportive terminology such as 'risk assessment', 'AI screening indicator', 'potential consideration', or 'discussion point with your doctor'.
3. NO PRESCRIPTIONS: Never prescribe medications or suggest altering prescription drug dosages.
4. Always advise the user to consult a licensed physician or specialist for diagnostic confirmation, clinical evaluations, or acute symptoms.
5. If the user presents red-flag emergency symptoms (such as acute chest pain, sudden numbness/weakness, severe shortness of breath, heavy bleeding), instruct them to seek emergency medical attention immediately.
6. Keep your response clear, structured, compassionate, and informative."""


def _call_gemini_api(system_instruction: str, user_message: str) -> Optional[str]:
    """
    Synchronous call to Google Gemini API using google-genai SDK, exactly matching
    app/ai/inference/report_explanation.py and image_ocr.py.
    """
    if not settings.GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai is not installed; skipping Gemini assistant call.")
        return None

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Try client.models.generate_content first
        if hasattr(client, "models") and hasattr(client.models, "generate_content"):
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                    max_output_tokens=1200,
                    http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
                ),
            )
            text = (response.text or "").strip()
            if text:
                return text

        # Alternative: client.interactions.create (as used in report_explanation.py)
        if hasattr(client, "interactions") and hasattr(client.interactions, "create"):
            interaction = client.interactions.create(
                model=MODEL_NAME,
                system_instruction=system_instruction,
                input=user_message,
                generation_config={"temperature": 0.3, "max_output_tokens": 1200},
            )
            text = (interaction.output_text or "").strip()
            if text:
                return text

    except Exception as e:
        logger.error(f"Gemini AI Assistant call failed: {e}")
        return None

    return None


async def chat_with_assistant(user_id: str, message: str) -> Dict[str, Any]:
    """
    Main orchestrator for Module 2 AI Health Assistant.
    1. Fetches user health profile and prediction records.
    2. Builds system prompt with personalized context.
    3. Calls Gemini API off the event loop via threadpool.
    4. Records conversation in database.
    5. Returns response with medical safety disclaimer.
    """
    # 0. Emergency check, in code, before anything else (AGENTS.md Section 47).
    #    No LLM call, no health-context lookup, and the message text itself is
    #    not stored: only the fact that an emergency pattern was flagged.
    emergency = detect_emergency(message)
    if emergency:
        try:
            await ai_conversation_repo.create({
                "user_id": user_id,
                "emergency_flag": emergency,
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.warning(f"Failed to record emergency flag: {e}")
        return {
            "response": emergency_response(emergency),
            "disclaimer": ASSISTANT_DISCLAIMER,
            "context_used": {},
            "emergency": True,
        }

    # 1. Fetch user context
    context = await get_user_health_context(user_id)

    # 2. Build system instruction
    system_instruction = _build_system_instruction(context)

    # 3. Call Gemini via run_in_threadpool
    gemini_reply = await run_in_threadpool(_call_gemini_api, system_instruction, message)

    ai_available = bool(gemini_reply)
    if not gemini_reply:
        # Gemini is not configured, timed out, or failed. Say so plainly and
        # point to what still works, rather than inventing an answer.
        gemini_reply = (
            "I'm SwasthAI, your health assistant. I can't answer questions right now "
            "because the assistant service is temporarily unavailable. Please try again "
            "in a few minutes.\n\n"
            "In the meantime, your Diet & Lifestyle plan and your saved risk assessments "
            "are still available, and for anything that worries you, your doctor is the "
            "best person to ask."
        )

    # 4. Save conversation metadata only. The free-text messages are not
    #    stored: they can hold sensitive health details and nothing reads
    #    them back.
    try:
        await ai_conversation_repo.create({
            "user_id": user_id,
            "message_chars": len(message),
            "ai_available": ai_available,
            "emergency_flag": None,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning(f"Failed to persist assistant conversation metadata: {e}")

    # 5. Return structured response
    return {
        "response": gemini_reply,
        "disclaimer": ASSISTANT_DISCLAIMER,
        "context_used": context,
        "emergency": False,
    }
