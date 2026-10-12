"""
Rule-Based Diet & Lifestyle Guidance Engine (Module 3).

STRICTLY rule-based — evaluates validated health records, vital metrics,
and prediction scores from MongoDB. Does NOT use LLMs/Gemini to ensure
deterministic, reproducible, and clinically safe nutritional guidelines.
"""
import logging
from typing import Any, Dict, List, Optional

from app.db.collections import health_profile_repo, prediction_repo

logger = logging.getLogger(__name__)

DIET_DISCLAIMER = (
    "These dietary and lifestyle recommendations are generated using evidence-based "
    "clinical screening guidelines for general wellness and educational purposes only. "
    "They do not constitute medical nutrition therapy, individual diagnosis, or a prescription. "
    "Always consult a registered dietitian, physician, or qualified healthcare professional "
    "before initiating any major dietary changes or exercise program."
)


def evaluate_diet_rules(
    bmi: Optional[float] = None,
    heart_risk: Optional[float] = None,
    high_bp: bool = False,
    fasting_glucose: Optional[float] = None,
    conditions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluates patient health metrics against clinical dietary rules.
    STRICTLY deterministic logic:
    - If BMI > 25: Weight-loss rules.
    - If Heart Risk > 50% or High BP: "DASH Diet" and "Low Sodium" rules.
    - If Fasting Glucose is high (>= 100 mg/dL or diabetes history): "Diabetic low-GI diet" rules.
    - Otherwise: Balanced Mediterranean wellness baseline.
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
            "diet": "Caloric Balance & High-Fiber Diet",
            "reason": f"Current BMI of {round(bmi, 1)} exceeds normal threshold (> 25.0).",
            "rules": [
                "Maintain a moderate daily caloric deficit (300–500 kcal/day below total daily expenditure) through whole foods.",
                "Increase daily dietary fiber intake to 30g+ using legumes, lentils, chia seeds, vegetables, and whole oats.",
                "Prioritize lean protein sources (1.2–1.6 g/kg of body weight) such as legumes, tofu, skinless poultry, and fish to preserve lean muscle mass.",
                "Strictly eliminate sugar-sweetened beverages, commercial sodas, fruit juices with added sugars, and ultra-processed snacks.",
                "Practice mindful eating with structured portion control and minimize late-night calorie consumption."
            ]
        })
        lifestyle_guidance.append("Engage in at least 150–300 minutes of moderate-intensity aerobic physical activity weekly, complemented by 2+ days of strength training.")
    elif bmi is not None and bmi < 18.5:
        diet_types.append("Nutrient-Dense Weight Recovery")
        recommendations.append({
            "category": "Weight Recovery",
            "diet": "Nutrient-Dense Caloric Surplus",
            "reason": f"Current BMI of {round(bmi, 1)} is below recommended threshold (< 18.5).",
            "rules": [
                "Incorporate nutrient-dense healthy fats such as avocados, nuts, seed butters, and olive oil into daily meals.",
                "Eat regular, energy-dense balanced meals and wholesome snacks throughout the day.",
                "Ensure sufficient high-quality protein to support healthy body mass."
            ]
        })

    # -------------------------------------------------------------
    # Rule 2: Cardiovascular & Blood Pressure (Heart Risk > 50% or High BP)
    # -------------------------------------------------------------
    heart_risk_pct = (heart_risk * 100.0) if heart_risk is not None else 0.0
    has_cardio_condition = any("hypertension" in c or "blood pressure" in c or "heart" in c for c in active_conditions)
    
    if (heart_risk is not None and heart_risk > 0.50) or high_bp or has_cardio_condition:
        diet_types.extend(["DASH Diet", "Low Sodium Diet"])
        reason_parts = []
        if heart_risk is not None and heart_risk > 0.50:
            reason_parts.append(f"Heart disease risk assessment is elevated at {round(heart_risk_pct, 1)}% (> 50%)")
        if high_bp or has_cardio_condition:
            reason_parts.append("Elevated blood pressure or hypertension indicators detected")
        
        recommendations.append({
            "category": "Cardiovascular Health & Blood Pressure",
            "diet": "DASH Diet & Low Sodium Pattern",
            "reason": "; ".join(reason_parts) if reason_parts else "Elevated cardiovascular risk profile",
            "rules": [
                "Restrict total daily dietary sodium strictly to under 1,500–2,000 mg (avoid canned soups, salted snacks, cured meats, and table salt).",
                "Increase potassium-, magnesium-, and calcium-rich foods: spinach, swiss chard, broccoli, avocados, bananas, and unsalted nuts.",
                "Replace saturated and industrial trans fats with monounsaturated fats (extra virgin olive oil, avocado, walnuts).",
                "Choose omega-3 fatty acid sources (salmon, mackerel, flaxseed, chia seeds) at least 2 times per week.",
                "Limit red meat and full-fat dairy products, substituting with skinless poultry, fish, and plant legumes."
            ]
        })
        lifestyle_guidance.append("Monitor resting blood pressure regularly, limit alcohol intake to moderate/minimal levels, and incorporate 10–15 minutes of daily stress-reduction practices.")

    # -------------------------------------------------------------
    # Rule 3: Glycemic Control (Fasting Glucose high >= 100 mg/dL or Diabetes history)
    # -------------------------------------------------------------
    has_diabetes_condition = any("diabet" in c for c in active_conditions)
    is_glucose_high = (fasting_glucose is not None and fasting_glucose >= 100.0)

    if is_glucose_high or has_diabetes_condition:
        diet_types.append("Diabetic Low-GI Diet")
        reason_desc = (
            f"Fasting glucose level of {round(fasting_glucose, 1)} mg/dL is elevated (>= 100 mg/dL)"
            if is_glucose_high
            else "Diabetes or prediabetes history recorded in profile"
        )
        recommendations.append({
            "category": "Glycemic Control & Metabolic Health",
            "diet": "Diabetic Low-GI Diet",
            "reason": reason_desc,
            "rules": [
                "Select low Glycemic Index (GI < 55) complex carbohydrates: steel-cut oats, barley, quinoa, lentils, chickpeas, and non-starchy vegetables.",
                "Avoid refined carbohydrates and simple sugars: white bread, refined pastries, white rice, syrups, and confectionery.",
                "Pair any carbohydrate portions with dietary protein or healthy fats (e.g., apple slices with raw almond butter) to blunt post-meal glucose spikes.",
                "Maintain consistent meal timing with evenly distributed carbohydrate quantities throughout the day.",
                "Drink 2.5–3 liters of water daily to support metabolic hydration and kidney filtration."
            ]
        })
        lifestyle_guidance.append("Take a light 10–15 minute walk following major meals to enhance peripheral insulin sensitivity and glucose clearance.")

    # -------------------------------------------------------------
    # Rule 4: Baseline / Maintenance (If no specific clinical alerts triggered)
    # -------------------------------------------------------------
    if not recommendations:
        diet_types.append("Balanced Mediterranean Wellness Diet")
        recommendations.append({
            "category": "General Preventive Health",
            "diet": "Mediterranean Whole Foods Diet",
            "reason": "Current records indicate normal health baseline; focus on long-term disease prevention.",
            "rules": [
                "Emphasize diverse colorful vegetables, fresh whole fruits, legumes, and whole grains as daily dietary anchors.",
                "Use extra virgin olive oil as your primary healthy fat source.",
                "Consume lean protein sources including fish, poultry, eggs, and plant proteins in balanced portions.",
                "Drink adequate water (2–2.5 liters/day) and minimize consumption of ultra-processed convenience foods."
            ]
        })
        lifestyle_guidance.append("Maintain 7–8 hours of quality sleep nightly and maintain consistent daily physical activity.")

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
        },
        "recommendations": recommendations,
        "lifestyle_guidance": lifestyle_guidance,
        "disclaimer": DIET_DISCLAIMER,
    }


async def get_diet_and_lifestyle_guidance(user_id: str) -> Dict[str, Any]:
    """
    Fetches the authenticated user's latest health profile and prediction records from MongoDB,
    extracts the clinical metrics, and applies the rule-based diet engine.
    """
    # 1. Fetch Health Profile
    profile_doc = await health_profile_repo.collection.find_one({"user_id": user_id})
    conditions: List[str] = []
    if profile_doc and "conditions" in profile_doc:
        conditions = [c.get("label", "") for c in profile_doc.get("conditions", []) if isinstance(c, dict) and c.get("label")]

    # 2. Fetch Latest Predictions
    cursor = prediction_repo.collection.find({"user_id": user_id}).sort("created_at", -1)
    predictions = await cursor.to_list(length=30)

    extracted_bmi: Optional[float] = None
    extracted_heart_risk: Optional[float] = None
    extracted_high_bp: bool = False
    extracted_fasting_glucose: Optional[float] = None

    for pred in predictions:
        snapshot = pred.get("input_snapshot") or {}
        result = pred.get("result") or {}
        condition_name = pred.get("condition", "")

        # Extract BMI from snapshots if not yet found
        if extracted_bmi is None:
            bmi_val = snapshot.get("bmi") or snapshot.get("BMI") or snapshot.get("BMXBMI")
            if bmi_val is not None:
                try:
                    extracted_bmi = float(bmi_val)
                except (ValueError, TypeError):
                    pass

        # Extract Heart Risk
        if extracted_heart_risk is None and ("heart" in condition_name):
            risk_prob = result.get("risk_probability")
            if risk_prob is not None:
                try:
                    extracted_heart_risk = float(risk_prob)
                except (ValueError, TypeError):
                    pass

        # Extract High Blood Pressure flags
        if not extracted_high_bp:
            high_bp_flag = snapshot.get("HighBP") or snapshot.get("high_bp") or snapshot.get("hypertension")
            if high_bp_flag in (1, "1", True):
                extracted_high_bp = True
            systolic = snapshot.get("BPXSY1") or snapshot.get("systolic_bp")
            diastolic = snapshot.get("BPXDI1") or snapshot.get("diastolic_bp") or snapshot.get("BloodPressure")
            try:
                if systolic and float(systolic) >= 130:
                    extracted_high_bp = True
                if diastolic and float(diastolic) >= 80:
                    extracted_high_bp = True
            except (ValueError, TypeError):
                pass

        # Extract Fasting Glucose
        if extracted_fasting_glucose is None:
            gluc_val = snapshot.get("LBXGLU") or snapshot.get("fasting_glucose") or snapshot.get("Glucose")
            if gluc_val is not None:
                try:
                    extracted_fasting_glucose = float(gluc_val)
                except (ValueError, TypeError):
                    pass

    # Fallback to health profile conditions for high blood pressure / diabetes
    for cond in conditions:
        cond_lower = cond.lower()
        if "hypertension" in cond_lower or "high blood pressure" in cond_lower:
            extracted_high_bp = True

    # 3. Apply rule-based engine
    evaluation = evaluate_diet_rules(
        bmi=extracted_bmi,
        heart_risk=extracted_heart_risk,
        high_bp=extracted_high_bp,
        fasting_glucose=extracted_fasting_glucose,
        conditions=conditions,
    )

    return {
        "user_id": user_id,
        **evaluation,
    }
