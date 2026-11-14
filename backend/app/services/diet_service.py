"""
Rule-Based Diet & Lifestyle Guidance Engine (Module 3).

STRICTLY rule-based, written for Indian users and Indian food. Evaluates the
user's health profile, questionnaire answers (daily routine, food preference,
regional cuisine, activity and habits), risk-assessment results, analysed lab reports and medication
list from MongoDB. Does NOT use LLMs/Gemini, so the guidance is
deterministic, reproducible and reviewable.

Workflow (synopsis Module 3):
    Health Profile / Health Records -> Lifestyle Information ->
    Health-Risk Context -> Recommendation Logic -> Diet & Lifestyle Guidance
"""
import logging
from typing import Any, Dict, List, Optional

from app.db.collections import (
    health_profile_repo,
    medical_report_repo,
    medication_repo,
    prediction_repo,
)
from app.services.health_profile_service import calculate_age, calculate_bmi
from app.services.indian_meal_plan import build_daily_meal_plan, exercise_timing, routine_tips
from app.services.prediction_history_service import CONDITION_INFO

logger = logging.getLogger(__name__)

DIET_DISCLAIMER = (
    "These dietary and lifestyle recommendations are generated using evidence-based "
    "clinical screening guidelines for general wellness and educational purposes only. "
    "They do not constitute medical nutrition therapy, individual diagnosis, or a prescription. "
    "Always consult a registered dietitian, physician, or qualified healthcare professional "
    "before initiating any major dietary changes or exercise program."
)

_PREFERENCE_NOTES = {
    "vegetarian": (
        "Vegetarian: get protein at every meal from dal, chana, rajma, sprouts, soya chunks, "
        "paneer, curd and milk. Where a suggestion mentions fish or chicken, use these instead."
    ),
    "eggetarian": (
        "Vegetarian with eggs: eggs are an easy protein. Add 1 to 2 boiled eggs or an egg "
        "bhurji with little oil to breakfast, alongside dal, paneer and curd."
    ),
    "vegan": (
        "Vegan: use dal, chana, rajma, soya chunks, tofu, peanuts and til for protein in place "
        "of dairy, eggs or fish. Vitamin B12 is hard to get from plant foods alone, so ask your "
        "doctor whether a supplement is right for you."
    ),
    "jain": (
        "Jain: the plan leaves out onion, garlic, potato and other root vegetables. Get protein "
        "from moong and toor dal, chana, paneer, curd and milk, and follow your family's practice "
        "where it differs."
    ),
    "non_vegetarian": (
        "Non-vegetarian: prefer fish (rohu, bangda, mathi, pomfret) and skinless chicken in curry, "
        "tandoori or grilled form over fried dishes, and keep mutton and processed meat occasional."
    ),
}

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# (activity, minutes, intensity) per day, Monday to Sunday.
_EXERCISE_TEMPLATES = {
    "sedentary": {
        "level": "Getting started",
        "weekly_target": "Build up to about 100 minutes of gentle activity this week, then add 10 minutes each week.",
        "sessions": [
            ("Easy walk in a park, on the terrace or in the corridor", 15, "light"),
            ("Easy walk and gentle stretching", 20, "light"),
            ("Rest or light household activity", 0, "rest"),
            ("Easy walk", 20, "light"),
            ("Chair squats, wall push-ups and stretching at home", 15, "light"),
            ("Easy walk at a comfortable pace", 25, "light"),
            ("Rest", 0, "rest"),
        ],
    },
    "light": {
        "level": "Building up",
        "weekly_target": "Aim for about 150 minutes of moderate activity this week, with 2 strength sessions.",
        "sessions": [
            ("Brisk walk", 30, "moderate"),
            ("Bodyweight strength: squats, push-ups, planks", 20, "moderate"),
            ("Brisk walk or cycling", 30, "moderate"),
            ("Rest, or gentle yoga such as tadasana and stretching", 0, "rest"),
            ("Brisk walk", 30, "moderate"),
            ("Bodyweight strength + stretching", 25, "moderate"),
            ("Evening walk with family or friends", 30, "light"),
        ],
    },
    "moderate": {
        "level": "Maintaining",
        "weekly_target": "Keep up 150 to 300 minutes of moderate activity this week, with 2 strength sessions.",
        "sessions": [
            ("Brisk walk, jog, cycling or skipping", 40, "moderate"),
            ("Strength training: legs and core", 30, "moderate"),
            ("Brisk walk, swimming or cycling", 40, "moderate"),
            ("Yoga: surya namaskar and stretching", 30, "light"),
            ("Brisk walk or jog", 40, "moderate"),
            ("Strength training: upper body and core", 30, "moderate"),
            ("Rest or a relaxed walk", 0, "rest"),
        ],
    },
    "active": {
        "level": "Staying strong",
        "weekly_target": "Maintain 300 minutes of moderate activity (or 150 vigorous) this week, with 2 to 3 strength sessions.",
        "sessions": [
            ("Run, cycling, or a sport such as badminton or cricket", 45, "vigorous"),
            ("Strength training: legs and core", 40, "moderate"),
            ("Brisk walk, swimming or cycling", 45, "moderate"),
            ("Strength training: upper body", 40, "moderate"),
            ("Run, cycling or a sport you enjoy", 45, "vigorous"),
            ("Yoga: surya namaskar and stretching", 30, "light"),
            ("Rest or a relaxed walk", 0, "rest"),
        ],
    },
}


def build_exercise_plan(
    activity_level: Optional[str] = None,
    bmi: Optional[float] = None,
    age: Optional[int] = None,
    cardiac_caution: bool = False,
    glucose_caution: bool = False,
    occupation_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Builds a one-week activity plan from the user's current activity level,
    then adds cautions for age, weight and heart-related risk.

    When the activity level is unknown, the gentlest plan is used and
    `personalised` is False so the UI can ask the user to complete their
    lifestyle details.
    """
    template = _EXERCISE_TEMPLATES.get(activity_level or "", _EXERCISE_TEMPLATES["sedentary"])
    low_impact = (bmi is not None and bmi >= 30) or (age is not None and age >= 60) or cardiac_caution

    sessions = []
    for day, (activity, minutes, intensity) in zip(_DAYS, template["sessions"]):
        if low_impact and intensity == "vigorous":
            # Swap high-impact work for a joint- and heart-friendlier option.
            activity, intensity = "Brisk walk, cycling or swimming", "moderate"
        sessions.append({
            "day": day,
            "activity": activity,
            "duration_minutes": minutes,
            "intensity": intensity,
        })

    cautions: List[str] = []
    if cardiac_caution:
        cautions.append(
            "Because of your heart or blood-pressure risk indicators, start gently and speak to "
            "your doctor before taking up vigorous exercise. Stop and seek medical help if you feel "
            "chest pain, dizziness or unusual breathlessness."
        )
    if bmi is not None and bmi >= 30:
        cautions.append(
            "Choose low-impact activities such as walking, cycling or swimming to protect your "
            "knees and ankles while you build fitness."
        )
    if age is not None and age >= 60:
        cautions.append(
            "Add balance practice (for example, standing on one leg near a support) on most days, "
            "and increase duration slowly."
        )
    if glucose_caution:
        cautions.append(
            "If you take medicines for diabetes, ask your doctor how to exercise safely and keep a "
            "quick source of sugar with you."
        )
    cautions.append("Warm up for 5 minutes before and cool down for 5 minutes after each session.")
    cautions.append("In summer, exercise in the early morning or evening and carry water.")

    return {
        "level": template["level"],
        "weekly_target": template["weekly_target"],
        "timing_tip": exercise_timing(occupation_type),
        "sessions": sessions,
        "cautions": cautions,
        "personalised": activity_level in _EXERCISE_TEMPLATES,
    }


def build_medication_guidance(
    medications: Optional[List[Dict[str, Any]]] = None,
    alcohol_use: Optional[str] = None,
) -> Dict[str, Any]:
    """General adherence guidance for the user's recorded active medicines.

    Never suggests a medicine, a dose, or a change to either: it only lists
    what the user has recorded and gives general safe-use habits.
    """
    meds = medications or []
    if not meds:
        return {"medications": [], "tips": []}

    tips = [
        "Take each medicine exactly as prescribed, at the same times every day. A phone alarm or a pill organiser helps.",
        "Do not stop, skip or change the dose of a prescribed medicine on your own, even if you feel better. Speak to your doctor first.",
        "Ask your doctor or pharmacist whether each medicine should be taken with food or on an empty stomach, and whether any foods should be avoided with it.",
        "If you miss a dose, follow the instructions you were given or ask your pharmacist. Do not take a double dose to catch up.",
        "Tell your doctor about every medicine, supplement and herbal product you take before starting anything new.",
        "Carry an up-to-date list of your medicines to every appointment. Your SwasthAI medication list can serve as that record.",
    ]
    if alcohol_use in ("occasional", "regular"):
        tips.append(
            "Alcohol can interact with many medicines. Ask your doctor or pharmacist whether it is safe with yours."
        )

    return {
        "medications": [
            {
                "name": m.get("name", ""),
                "dosage": m.get("dosage"),
                "frequency": m.get("frequency"),
                "instructions": m.get("instructions"),
                "member_name": m.get("member_name"),
            }
            for m in meds
        ],
        "tips": tips,
    }


def evaluate_diet_rules(
    bmi: Optional[float] = None,
    heart_risk: Optional[float] = None,
    high_bp: bool = False,
    fasting_glucose: Optional[float] = None,
    conditions: Optional[List[str]] = None,
    *,
    diabetes_risk_elevated: bool = False,
    liver_risk_elevated: bool = False,
    heart_risk_elevated: bool = False,
    high_cholesterol: bool = False,
    two_hour_glucose: Optional[float] = None,
    activity_level: Optional[str] = None,
    diet_preference: Optional[str] = None,
    smoking_status: Optional[str] = None,
    alcohol_use: Optional[str] = None,
    sleep_hours: Optional[float] = None,
    age: Optional[int] = None,
    allergies: Optional[List[str]] = None,
    medications: Optional[List[Dict[str, Any]]] = None,
    occupation_type: Optional[str] = None,
    cuisine_region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates health metrics against dietary rules.
    STRICTLY deterministic logic:
    - If BMI > 25: Weight-loss rules.
    - If Heart Risk > 50% or High BP: "DASH Diet" and "Low Sodium" rules.
    - If Fasting Glucose is high (>= 100 mg/dL), diabetes history, or an
      elevated diabetes risk assessment: "Diabetic low-GI diet" rules.
    - If liver risk assessment is elevated or a liver condition is recorded:
      "Liver-Friendly Diet" rules.
    - Otherwise: Balanced Indian thali baseline.
    Lifestyle inputs (activity, diet preference, smoking, alcohol, sleep)
    then tailor the lifestyle guidance, exercise plan and food notes.
    """
    recommendations: List[Dict[str, Any]] = []
    diet_types: List[str] = []
    lifestyle_guidance: List[str] = []

    active_conditions = [c.lower() for c in (conditions or [])]

    # -------------------------------------------------------------
    # Rule 1: BMI Evaluation (BMI > 25 -> Weight-Loss Guidance)
    # -------------------------------------------------------------
    if bmi is not None and bmi > 25.0:
        diet_types.append("Weight Management & Caloric Balance")
        recommendations.append({
            "category": "Weight Management",
            "diet": "Portion-Controlled, High-Fiber Indian Diet",
            "reason": f"Current BMI of {round(bmi, 1)} exceeds normal threshold (> 25.0).",
            "rules": [
                "Keep a moderate caloric deficit of about 300 to 500 kcal a day: smaller portions of rice and roti, and fewer fried snacks, sweets and sugary chai.",
                "Raise your fiber to 30 g or more a day with dal, chana, rajma, sprouts, whole-wheat atta, millets (ragi, jowar, bajra), oats, sabzi and salad.",
                "Include protein at every meal (about 1.2 g per kg of body weight) to protect muscle: dal, curd, paneer, soya, eggs, fish or skinless chicken, as your diet allows.",
                "Cut out sugary drinks: packaged juices, cold drinks, sweetened lassi and sugar in chai.",
                "Use the plate method: half sabzi and salad, a quarter dal or protein, a quarter rice or roti. Avoid heavy late-night meals."
            ]
        })
        lifestyle_guidance.append("Aim for 150 to 300 minutes of brisk walking or similar activity a week, plus 2 days of strength exercise such as squats or yoga.")
    elif bmi is not None and bmi < 18.5:
        diet_types.append("Nutrient-Dense Weight Recovery")
        recommendations.append({
            "category": "Weight Recovery",
            "diet": "Nutrient-Dense Weight Gain Diet",
            "reason": f"Current BMI of {round(bmi, 1)} is below recommended threshold (< 18.5).",
            "rules": [
                "Add healthy energy-dense foods every day: peanuts, peanut chikki, almonds, til, banana, and a teaspoon of ghee on dal or roti.",
                "Eat 5 to 6 times a day: three meals plus snacks such as a banana shake, poha, sprouts chaat or dry fruit laddoo.",
                "Include protein at every meal (dal, paneer, curd, milk, eggs or fish as your diet allows) to build healthy body mass."
            ]
        })

    # -------------------------------------------------------------
    # Rule 2: Cardiovascular & Blood Pressure (Heart Risk > 50% or High BP)
    # -------------------------------------------------------------
    heart_risk_pct = (heart_risk * 100.0) if heart_risk is not None else 0.0
    has_cardio_condition = any("hypertension" in c or "blood pressure" in c or "heart" in c for c in active_conditions)
    heart_score_high = heart_risk is not None and heart_risk > 0.50
    cardiac_caution = heart_score_high or heart_risk_elevated or high_bp or has_cardio_condition or high_cholesterol

    if cardiac_caution:
        diet_types.extend(["DASH Diet", "Low Sodium Diet"])
        reason_parts = []
        if heart_score_high:
            reason_parts.append(f"Heart disease risk assessment is elevated at {round(heart_risk_pct, 1)}% (> 50%)")
        elif heart_risk_elevated:
            reason_parts.append("Your latest heart disease risk assessment showed an elevated risk indicator")
        if high_bp or has_cardio_condition:
            reason_parts.append("Elevated blood pressure or hypertension indicators detected")
        if high_cholesterol:
            reason_parts.append("High cholesterol was recorded in one of your assessments")

        recommendations.append({
            "category": "Cardiovascular Health & Blood Pressure",
            "diet": "Low-Salt, Heart-Friendly Indian Diet (DASH pattern)",
            "reason": "; ".join(reason_parts) if reason_parts else "Elevated cardiovascular risk profile",
            "rules": [
                "Keep sodium under about 1,500 to 2,000 mg a day (under 1 teaspoon of salt in total): no extra salt at the table, and limit achar, papad, namkeen, chips and instant noodles.",
                "Eat potassium-rich foods daily, such as banana, coconut water, palak, methi, tomato, dal and curd (unless your doctor has asked you to limit potassium for a kidney problem).",
                "Cook with small amounts of mustard, groundnut, rice-bran or til oil. Limit ghee, butter and vanaspati, and never reuse frying oil.",
                "Get omega-3 fats twice a week or more from alsi (flaxseed), walnuts, or fish such as bangda (mackerel) or mathi (sardine) if you eat fish.",
                "Choose dal, chana, paneer, curd, fish or skinless chicken over mutton and processed meat."
            ]
        })
        lifestyle_guidance.append("Check your blood pressure regularly (a home BP monitor helps), limit alcohol, and spend 10 to 15 minutes a day on pranayama, meditation or a quiet walk.")

    # -------------------------------------------------------------
    # Rule 3: Glycemic Control (Fasting Glucose >= 100 mg/dL, diabetes
    # history, or an elevated diabetes risk assessment)
    # -------------------------------------------------------------
    has_diabetes_condition = any("diabet" in c for c in active_conditions)
    is_glucose_high = (fasting_glucose is not None and fasting_glucose >= 100.0)
    # A 2-hour oral glucose tolerance test (OGTT) value has its own range:
    # 140 mg/dL or more is above the usual range (ADA).
    is_ogtt_high = (two_hour_glucose is not None and two_hour_glucose >= 140.0)
    glucose_caution = is_glucose_high or is_ogtt_high or has_diabetes_condition or diabetes_risk_elevated

    if glucose_caution:
        diet_types.append("Diabetic Low-GI Diet")
        if is_glucose_high:
            reason_desc = f"Fasting glucose level of {round(fasting_glucose, 1)} mg/dL is elevated (>= 100 mg/dL)"
        elif is_ogtt_high:
            reason_desc = f"2-hour glucose (OGTT) of {round(two_hour_glucose, 1)} mg/dL is above the usual range (>= 140 mg/dL)"
        elif has_diabetes_condition:
            reason_desc = "Diabetes or prediabetes history recorded in profile"
        else:
            reason_desc = "Your latest diabetes risk assessment showed an elevated risk indicator"
        recommendations.append({
            "category": "Glycemic Control & Metabolic Health",
            "diet": "Low-GI Indian Diet for Blood Sugar",
            "reason": reason_desc,
            "rules": [
                "Choose low glycemic index (GI under 55) complex carbohydrates: millets (ragi, jowar, bajra), multigrain atta, small portions of brown or red rice, oats, dal, chana and rajma.",
                "Limit refined carbs and sugar: maida (white bread, naan, biscuits), large portions of white rice, mithai, jaggery, honey and sugary chai.",
                "Pair every carbohydrate with protein or fibre: roti with dal and sabzi, rice with plenty of sambar or curd, fruit with a few nuts.",
                "Eat at regular times and don't skip meals, especially breakfast. Spread rice and roti evenly through the day.",
                "Prefer whole fruits such as guava, jamun, apple, orange and papaya in small portions over juice, and limit mango, chikoo, grapes and banana.",
                "Drink 2.5 to 3 litres of water a day. Choose water, plain chaas or lemon water without sugar."
            ]
        })
        lifestyle_guidance.append("Take a light 10 to 15 minute walk after lunch and dinner. It helps your body handle blood sugar.")

    # -------------------------------------------------------------
    # Rule 4: Liver health (elevated liver risk assessment or a recorded
    # liver condition)
    # -------------------------------------------------------------
    has_liver_condition = any("liver" in c or "hepat" in c for c in active_conditions)
    liver_caution = liver_risk_elevated or has_liver_condition

    if liver_caution:
        diet_types.append("Liver-Friendly Diet")
        recommendations.append({
            "category": "Liver Health",
            "diet": "Liver-Friendly Indian Diet",
            "reason": (
                "Your latest liver risk assessment showed an elevated risk indicator"
                if liver_risk_elevated
                else "A liver-related condition is recorded in your profile"
            ),
            "rules": [
                "Avoid alcohol unless your doctor has told you it is safe for you.",
                "Cut down on deep-fried foods (puri, bhature, samosa, pakora), ghee-heavy dishes and bakery items.",
                "Limit added sugar and sweetened drinks, which the liver converts to fat.",
                "Fill half your plate with sabzi and salad, and choose whole grains such as whole-wheat atta, brown rice, oats and millets.",
                "Do not take herbal or ayurvedic preparations or over-the-counter painkillers regularly without asking your doctor, as some can strain the liver."
            ]
        })
        lifestyle_guidance.append("Ask your doctor whether a liver function test or a follow-up check is appropriate for you.")

    # -------------------------------------------------------------
    # Rule 5: Baseline / Maintenance (If no specific alerts triggered)
    # -------------------------------------------------------------
    if not recommendations:
        diet_types.append("Balanced Indian Thali")
        recommendations.append({
            "category": "General Preventive Health",
            "diet": "Balanced Indian Thali",
            "reason": "Your records show no specific risk flags, so the focus is on staying healthy long term.",
            "rules": [
                "Build each main meal like a balanced thali: half sabzi and salad, a quarter dal or other protein, a quarter roti or rice.",
                "Prefer whole grains: whole-wheat or multigrain atta, millets, brown or red rice and oats.",
                "Have curd or buttermilk daily (or a plant alternative if you are vegan), and 2 to 3 servings of seasonal fruit.",
                "Cook with small amounts of mustard, groundnut or rice-bran oil, and keep fried snacks and mithai for occasions.",
                "Drink 2 to 2.5 litres of water a day and limit packaged and ready-to-eat foods."
            ]
        })
        lifestyle_guidance.append("Keep 7 to 8 hours of sleep and some physical activity every day.")

    # -------------------------------------------------------------
    # Lifestyle tailoring (smoking, alcohol, sleep, activity)
    # -------------------------------------------------------------
    if smoking_status == "current":
        lifestyle_guidance.append(
            "Stopping tobacco in any form (cigarettes, bidi, gutka, khaini or paan masala) is one of the "
            "most effective things you can do for your heart, lungs and mouth. Your doctor can help "
            "with a quit plan, or call the National Tobacco Quit Line on 1800-11-2356 (free)."
        )
    elif smoking_status == "former":
        lifestyle_guidance.append("Staying tobacco-free continues to lower your heart and lung risk every year. Keep it up.")

    if alcohol_use == "regular":
        lifestyle_guidance.append(
            "Cutting down on alcohol lowers blood pressure, protects the liver and helps with weight. "
            "Aim for several alcohol-free days each week, and speak to your doctor if cutting down is difficult."
        )
    elif alcohol_use == "occasional" and liver_caution:
        lifestyle_guidance.append("Given your liver risk indicators, it is safest to avoid alcohol until you have discussed it with your doctor.")

    if sleep_hours is not None and sleep_hours < 7:
        lifestyle_guidance.append(
            f"You report about {sleep_hours:g} hours of sleep. Most adults need 7 to 9 hours: keep a fixed "
            "bedtime, avoid screens and caffeine late in the evening, and keep your room dark and cool."
        )
    elif sleep_hours is not None and sleep_hours > 9:
        lifestyle_guidance.append(
            f"You report about {sleep_hours:g} hours of sleep. Regularly sleeping more than 9 hours and "
            "still feeling tired is worth mentioning to your doctor."
        )

    if activity_level == "sedentary":
        lifestyle_guidance.append("Break up long periods of sitting: stand up and move for 2 to 3 minutes every half hour.")

    # -------------------------------------------------------------
    # Food preference and allergy notes
    # -------------------------------------------------------------
    preference_notes: List[str] = []
    if diet_preference in _PREFERENCE_NOTES:
        preference_notes.append(_PREFERENCE_NOTES[diet_preference])
    clean_allergies = [a for a in (allergies or []) if a]
    if clean_allergies:
        preference_notes.append(
            "You have recorded these allergies: " + ", ".join(clean_allergies) + ". Leave out any "
            "suggested food that contains them, and check ingredient labels on packaged foods."
        )

    # Deduplicate diet types while maintaining order
    unique_diet_types = list(dict.fromkeys(diet_types))

    return {
        "diet_types": unique_diet_types,
        "metrics_evaluated": {
            "bmi": bmi,
            "heart_risk": heart_risk,
            "high_bp": high_bp,
            "fasting_glucose": fasting_glucose,
            "conditions": conditions or [],
            "diabetes_risk_elevated": diabetes_risk_elevated,
            "liver_risk_elevated": liver_risk_elevated,
            "heart_risk_elevated": heart_risk_elevated or heart_score_high,
            "high_cholesterol": high_cholesterol,
            "two_hour_glucose": two_hour_glucose,
            "age": age,
            "activity_level": activity_level,
            "diet_preference": diet_preference,
            "smoking_status": smoking_status,
            "alcohol_use": alcohol_use,
            "sleep_hours": sleep_hours,
            "occupation_type": occupation_type,
            "cuisine_region": cuisine_region,
        },
        "recommendations": recommendations,
        "lifestyle_guidance": lifestyle_guidance,
        "routine_tips": routine_tips(occupation_type),
        "preference_notes": preference_notes,
        "meal_plan": build_daily_meal_plan(
            occupation_type,
            diet_preference,
            cuisine_region,
            glucose_caution=glucose_caution,
            cardiac_caution=cardiac_caution,
            liver_caution=liver_caution,
            weight_loss=bmi is not None and bmi > 25.0,
            underweight=bmi is not None and bmi < 18.5,
        ),
        "exercise_plan": build_exercise_plan(
            activity_level=activity_level,
            bmi=bmi,
            age=age,
            cardiac_caution=cardiac_caution,
            glucose_caution=glucose_caution,
            occupation_type=occupation_type,
        ),
        "medication_guidance": build_medication_guidance(medications, alcohol_use),
        "disclaimer": DIET_DISCLAIMER,
    }


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


async def _latest_report_fasting_glucose(user_id: str) -> Optional[float]:
    """Fasting glucose from the user's most recent analysed lab report that
    contains one. Optional enrichment: a failure here must not break the
    guidance, so it is logged and treated as "no value"."""
    try:
        cursor = medical_report_repo.collection.find({"user_id": user_id}).sort("created_at", -1)
        for report in await cursor.to_list(length=10):
            for value in (report.get("result") or {}).get("values", []):
                if value.get("key") == "fasting_glucose":
                    return _as_float(value.get("value"))
    except Exception as e:
        logger.warning(f"Could not read analysed reports for diet guidance: {e}")
    return None


async def _active_medications(user_id: str) -> List[Dict[str, Any]]:
    """Active medicines recorded under this account (optional enrichment)."""
    try:
        cursor = medication_repo.collection.find({"user_id": user_id, "status": "active"}).sort("created_at", -1)
        return await cursor.to_list(length=50)
    except Exception as e:
        logger.warning(f"Could not read medications for diet guidance: {e}")
        return []


# How many recent results to scan when finding the latest of each assessment.
PREDICTION_SCAN_LIMIT = 200

# Assessments that shape diet guidance. Image checks (skin) do not.
_DIET_AREAS = ("diabetes", "heart", "liver")

_PLAN_EFFECT = {
    "diabetes": "Low-GI meals: millets or brown rice in place of white rice and maida, and chai without sugar.",
    "heart": "Low-salt, heart-friendly meals, and a gentler start to exercise.",
    "liver": "Liver-friendly meals: no alcohol, no fried food and less added sugar.",
}


def _is_yes(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "yes", "true")
    return value is True or value == 1


def _latest_per_assessment(predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The most recent result of each assessment, newest first.

    Each model counts on its own: the lifestyle-question and lab-value
    versions of an assessment measure different things, so a newer result
    from one does not cancel an older result from the other. `predictions`
    must already be sorted newest first.
    """
    latest: Dict[str, Dict[str, Any]] = {}
    for pred in predictions:
        condition = pred.get("condition") or ""
        info = CONDITION_INFO.get(condition)
        if info and info[1] in _DIET_AREAS:
            latest.setdefault(condition, pred)
    return list(latest.values())


def _signals_from_assessments(latest: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Health signals from the latest result of each assessment: each
    model's own elevated / not-elevated verdict, plus measurements the user
    entered (BMI, blood pressure, glucose, cholesterol). Newest value wins."""
    s: Dict[str, Any] = {
        "bmi": None, "heart_risk": None, "high_bp": False,
        "fasting_glucose": None, "two_hour_glucose": None, "high_cholesterol": False,
        "diabetes_elevated": False, "heart_elevated": False, "liver_elevated": False,
    }
    for pred in latest:
        condition = pred.get("condition") or ""
        area = CONDITION_INFO[condition][1]
        snapshot = pred.get("input_snapshot") or {}
        result = pred.get("result") or {}

        if result.get("is_elevated"):
            s[f"{area}_elevated"] = True
        if area == "heart" and s["heart_risk"] is None:
            s["heart_risk"] = _as_float(result.get("risk_probability"))

        if s["bmi"] is None:
            s["bmi"] = _as_float(snapshot.get("bmi") or snapshot.get("BMI") or snapshot.get("BMXBMI"))

        if any(_is_yes(snapshot.get(k)) for k in ("HighBP", "high_bp", "hypertension")):
            s["high_bp"] = True
        systolic = _as_float(snapshot.get("BPXSY1") or snapshot.get("systolic_bp"))
        diastolic = _as_float(snapshot.get("BPXDI1") or snapshot.get("diastolic_bp") or snapshot.get("BloodPressure"))
        if (systolic and systolic >= 130) or (diastolic and diastolic >= 80):
            s["high_bp"] = True

        if s["fasting_glucose"] is None:
            s["fasting_glucose"] = _as_float(snapshot.get("LBXGLU") or snapshot.get("fasting_glucose"))
        # The lab-value diabetes assessment asks for a 2-hour OGTT reading,
        # which has a different normal range from a fasting reading.
        if condition == "diabetes_pima" and s["two_hour_glucose"] is None:
            s["two_hour_glucose"] = _as_float(snapshot.get("Glucose"))

        if any(_is_yes(snapshot.get(k)) for k in ("HighChol", "high_cholesterol")):
            s["high_cholesterol"] = True
        total_chol = _as_float(snapshot.get("total_cholesterol") or snapshot.get("LBXTC"))
        if total_chol is not None and total_chol >= 240:
            s["high_cholesterol"] = True
    return s


def _assessments_used(latest: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """What the plan took from each assessment, for display."""
    items = []
    for pred in latest:
        label, area = CONDITION_INFO[pred["condition"]]
        elevated = bool((pred.get("result") or {}).get("is_elevated"))
        items.append({
            "assessment": area,
            "label": label,
            "assessed_at": pred.get("created_at"),
            "is_elevated": elevated,
            "plan_effect": _PLAN_EFFECT[area] if elevated else "No extra changes were needed from this result.",
        })
    return items


async def get_diet_and_lifestyle_guidance(user_id: str) -> Dict[str, Any]:
    """
    Gathers the authenticated user's health profile, lifestyle details, latest
    risk assessments, analysed lab reports and active medications from
    MongoDB, then applies the rule-based engine.
    """
    # 1. Health profile and lifestyle information
    profile_doc = await health_profile_repo.collection.find_one({"user_id": user_id}) or {}
    conditions: List[str] = [
        c.get("label", "") for c in profile_doc.get("conditions", []) if isinstance(c, dict) and c.get("label")
    ]

    age: Optional[int] = None
    dob_raw = profile_doc.get("date_of_birth")
    if dob_raw:
        try:
            from datetime import date
            age = calculate_age(date.fromisoformat(dob_raw))
        except (ValueError, TypeError):
            age = None

    # The profile's own height and weight are the user's current
    # measurements, so they take priority over a BMI typed into an old
    # risk assessment.
    extracted_bmi: Optional[float] = calculate_bmi(profile_doc.get("height_cm"), profile_doc.get("weight_kg"))

    # 2. Health-risk context from the user's own saved assessments.
    # Results saved for a family member describe someone else, so only the
    # account holder's results are used ({"family_member_id": None} also
    # matches records without the field).
    cursor = prediction_repo.collection.find(
        {"user_id": user_id, "family_member_id": None}
    ).sort("created_at", -1)
    predictions = [
        p for p in await cursor.to_list(length=PREDICTION_SCAN_LIMIT)
        if not p.get("family_member_id")
    ]
    latest = _latest_per_assessment(predictions)
    signals = _signals_from_assessments(latest)

    extracted_heart_risk = signals["heart_risk"]
    extracted_high_bp = signals["high_bp"]
    extracted_fasting_glucose = signals["fasting_glucose"]
    if extracted_bmi is None:
        extracted_bmi = signals["bmi"]

    # Fallback to health profile conditions for high blood pressure
    for cond in conditions:
        cond_lower = cond.lower()
        if "hypertension" in cond_lower or "high blood pressure" in cond_lower:
            extracted_high_bp = True

    # 3. Health records: analysed lab reports and active medications
    if extracted_fasting_glucose is None:
        extracted_fasting_glucose = await _latest_report_fasting_glucose(user_id)
    medications = await _active_medications(user_id)

    # 4. Apply rule-based engine
    evaluation = evaluate_diet_rules(
        bmi=extracted_bmi,
        heart_risk=extracted_heart_risk,
        high_bp=extracted_high_bp,
        fasting_glucose=extracted_fasting_glucose,
        conditions=conditions,
        diabetes_risk_elevated=signals["diabetes_elevated"],
        liver_risk_elevated=signals["liver_elevated"],
        heart_risk_elevated=signals["heart_elevated"],
        high_cholesterol=signals["high_cholesterol"],
        two_hour_glucose=signals["two_hour_glucose"],
        activity_level=profile_doc.get("activity_level"),
        diet_preference=profile_doc.get("diet_preference"),
        smoking_status=profile_doc.get("smoking_status"),
        alcohol_use=profile_doc.get("alcohol_use"),
        sleep_hours=profile_doc.get("sleep_hours"),
        age=age,
        allergies=profile_doc.get("allergies") or [],
        medications=medications,
        occupation_type=profile_doc.get("occupation_type"),
        cuisine_region=profile_doc.get("cuisine_region"),
    )

    # 5. Tell the UI what the user could add to make this more personal.
    missing_inputs: List[str] = []
    if extracted_bmi is None:
        missing_inputs.append("height_weight")
    # The questionnaire on the Diet & Lifestyle page asks for these.
    if not all(profile_doc.get(k) for k in ("occupation_type", "diet_preference", "cuisine_region", "activity_level")):
        missing_inputs.append("lifestyle")
    if not latest:
        missing_inputs.append("risk_assessment")

    return {
        "user_id": user_id,
        **evaluation,
        "assessments_used": _assessments_used(latest),
        "missing_inputs": missing_inputs,
    }
