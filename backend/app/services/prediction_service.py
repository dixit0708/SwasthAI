from datetime import datetime, timezone

from app.ai.models.diabetes_model import predict_diabetes
from app.ai.models.diabetes_pima_model import predict_diabetes_pima
from app.ai.models.heart_model import predict_heart
from app.ai.models.liver_model import predict_liver
from app.ai.models.liver_ilpd_model import predict_liver_ilpd
from app.ai.safety.clinical_rules import apply_clinical_overlay
from app.ai.safety.response_filter import build_screening_response
from app.db.collections import prediction_repo
from app.models.prediction import (
    DiabetesPimaPredictionInput, DiabetesPredictionInput, HeartPredictionInput, HeartClinicalInput,
    LiverIlpdPredictionInput, LiverPredictionInput,
)
import numpy as np

# Used only if metadata.json is somehow missing a model_version (load_diabetes_model
# already rejects that at startup) — kept as a last-resort label, never the
# primary source of truth.
FALLBACK_MODEL_VERSION = "diabetes-brfss-v2"
FALLBACK_LIVER_MODEL_VERSION = "liver-nhanes-v1"
FALLBACK_DIABETES_PIMA_MODEL_VERSION = "diabetes-pima-v1"
FALLBACK_LIVER_ILPD_MODEL_VERSION = "liver-ilpd-logistic-v1"


async def predict_diabetes_risk(user_id: str, payload: DiabetesPredictionInput, model, metadata: dict) -> dict:
    # Explicit field mapping (BRFSS training-time names) — never rely on
    # dict/attribute iteration order for this; see
    # ml_pipeline/diabetes/data/raw/README_brfss2015.md for the codebook.
    # 14-feature v2 contract — see ml_pipeline/diabetes/reports/candidate_assessments.md.
    features = {
        "HighBP": payload.high_bp,
        "HighChol": payload.high_chol,
        "CholCheck": payload.chol_check,
        "BMI": payload.bmi,
        "Smoker": payload.smoker,
        "Stroke": payload.stroke,
        "HeartDiseaseorAttack": payload.heart_disease_or_attack,
        "PhysActivity": payload.phys_activity,
        "Fruits": payload.fruits,
        "HvyAlcoholConsump": payload.hvy_alcohol_consump,
        "GenHlth": payload.gen_hlth,
        "DiffWalk": payload.diff_walk,
        "Sex": payload.sex,
        "Age": payload.age,
    }

    result = predict_diabetes(model, metadata, features)
    model_version = metadata.get("model_version", FALLBACK_MODEL_VERSION)
    response = build_screening_response(
        "diabetes", result["risk_probability"], result["threshold"], model_version,
    )

    await prediction_repo.create({
        "user_id": user_id,
        "condition": "diabetes",
        "model_version": model_version,
        "input_snapshot": features,
        "result": response,
        "created_at": datetime.now(timezone.utc),
    })

    return response



async def predict_heart_disease(
    user_id: str,
    payload: HeartPredictionInput,
    model,
    metadata: dict,
) -> dict:
    """Transform the Pydantic HeartPredictionInput into the PascalCase raw
    dict expected by heart_model.encode_heart_features(), run inference,
    build the screening response, and persist to the predictions collection.

    The mapping here uses the exact column names from the training dataset
    (PascalCase) so encode_heart_features() can apply the encoding maps
    copied from ml_pipeline/heart/preprocessing.py without any ambiguity.
    """
    raw_features = {
        "Sex":                   payload.sex,
        "AgeCategory":           payload.age_category,
        "BMI":                   payload.bmi,
        "GeneralHealth":         payload.general_health,
        "PhysicalHealthDays":    payload.physical_health_days,
        "MentalHealthDays":      payload.mental_health_days,
        "SleepHours":            payload.sleep_hours,
        "PhysicalActivities":    payload.physical_activities,
        "HadStroke":             payload.had_stroke,
        "HadAsthma":             payload.had_asthma,
        "HadCOPD":               payload.had_copd,
        "HadDepressiveDisorder": payload.had_depressive_disorder,
        "HadKidneyDisease":      payload.had_kidney_disease,
        "HadArthritis":          payload.had_arthritis,
        "HadDiabetes":           payload.had_diabetes,
        "DifficultyWalking":     payload.difficulty_walking,
        "DifficultyConcentrating": payload.difficulty_concentrating,
        "DifficultyErrands":     payload.difficulty_errands,
        "SmokerStatus":          payload.smoker_status,
        "AlcoholDrinkers":       payload.alcohol_drinkers,
        "ChestScan":             payload.chest_scan,
        "HighRiskLastYear":      payload.high_risk_last_year,
        "RemovedTeeth":          payload.removed_teeth,
        "LastCheckupTime":       payload.last_checkup_time,
    }

    result = predict_heart(model, metadata, raw_features)

    # ------------------------------------------------------------------
    # Clinical rule overlay — applies a floor probability for clinically
    # severe feature combinations that the CDC survey-based XGBoost model
    # underweights due to training data correlation limits.
    # The overlay is a minimum floor: model score is preserved when it
    # already exceeds the tier floor.  See app/ai/safety/clinical_rules.py
    # for the full evidence basis and rule definitions.
    # ------------------------------------------------------------------
    overlay = apply_clinical_overlay(result["risk_probability"], raw_features)

    model_version = metadata.get("model_version", "heart-cdc2022-v1")
    response = build_screening_response(
        "heart disease",
        overlay.adjusted_probability,   # may be higher than raw model score
        result["threshold"],
        model_version,
    )

    # Append overlay metadata to the response so the frontend can surface it
    response["model_probability"]   = overlay.model_probability
    response["clinical_tier"]       = overlay.tier
    response["clinical_flags"]      = overlay.rules_triggered
    response["overlay_applied"]     = overlay.overlay_applied

    await prediction_repo.create({
        "user_id":          user_id,
        "condition":        "heart_disease",
        "model_version":    model_version,
        "input_snapshot":   raw_features,
        "result":           response,
        "overlay_tier":     overlay.tier,
        "overlay_rules":    overlay.rules_triggered,
        "created_at":       datetime.now(timezone.utc),
    })

    return response

async def predict_heart_clinical(
    user_id: str,
    payload: HeartClinicalInput,
    model,
    scaler,
) -> dict:
    import pandas as pd

    # The exact column names used during training in ml_pipeline/heart_clinical/train.py
    # ['RIDAGEYR', 'BPXSY1', 'BPXDI1', 'LBXTC', 'LBDHDD', 'LBXGLU', 'BPXPLS', 'BMXBMI']
    raw_features_dict = {
        'RIDAGEYR': [payload.age],
        'BPXSY1': [payload.systolic_bp],
        'BPXDI1': [payload.diastolic_bp],
        'LBXTC': [payload.total_cholesterol],
        'LBDHDD': [payload.hdl_cholesterol],
        'LBXGLU': [payload.fasting_glucose],
        'BPXPLS': [payload.pulse],
        'BMXBMI': [payload.bmi]
    }
    
    df_features = pd.DataFrame(raw_features_dict)
    
    # Pass the DataFrame to the scaler so it recognizes the feature names
    features_scaled = scaler.transform(df_features)
    
    # Temporary print statement for debugging
    print(f"=== [DEBUG] Scaled features passed to XGBoost: {features_scaled} ===")
    
    # Predict probability
    prob = float(model.predict_proba(features_scaled)[0, 1])
    print(f"=== [RAW XGBOOST PROB]: {prob} ===")
    
    # Scale empirical probability for UI representation
    # 1. Define the exact raw outputs we observe from the model
    # [Absolute Min, Healthy Baseline, Moderate Risk, Fatal/Extreme, Absolute Max]
    raw_anchors = [0.00, 0.0010069217532873154, 0.09806432109326124, 0.19512172043323517, 1.00]

    # 2. Define exactly what UI percentage we want to show for those raw outputs
    # [UI Floor, UI Healthy, UI Moderate, UI Critical, UI Ceiling]
    ui_anchors = [0.01, 0.08, 0.40, 0.95, 0.99]

    # 3. Smoothly map the incoming raw probability to the UI scale
    scaled_prob = float(np.interp(prob, raw_anchors, ui_anchors))
    
    model_version = "heart-clinical-nhanes-v1"

    if scaled_prob > 0.75:
        risk_level = "screening_elevated"
        message = "Your inputs show critical risk indicators for heart disease based on this clinical model. Please seek immediate medical consultation."
    elif scaled_prob > 0.50:
        risk_level = "screening_elevated"
        message = "Your inputs show high risk indicators for heart disease based on this clinical model. Please consult a healthcare professional immediately."
    elif scaled_prob >= 0.20:
        risk_level = "screening_elevated"
        message = "Your inputs show moderate risk indicators for heart disease based on this clinical model. Consider discussing these results with a healthcare professional."
    else:
        risk_level = "screening_negative"
        message = "Your inputs do not show elevated risk indicators for heart disease based on this clinical model. This is not a diagnosis and does not rule out heart disease — continue routine checkups."

    from app.ai.safety.medical_disclaimer import RISK_ASSESSMENT_DISCLAIMER
    response = {
        "risk_level": risk_level,
        "risk_probability": round(float(scaled_prob), 4),
        "threshold": 0.20,
        "is_elevated": scaled_prob >= 0.20,
        "message": message,
        "model_version": model_version,
        "disclaimer": RISK_ASSESSMENT_DISCLAIMER,
    }

    await prediction_repo.create({
        "user_id":          user_id,
        "condition":        "heart_disease_clinical",
        "model_version":    model_version,
        "input_snapshot":   payload.model_dump(),
        "result":           response,
        "created_at":       datetime.now(timezone.utc),
    })

    return response

async def predict_liver_risk(user_id: str, payload: LiverPredictionInput, model, metadata: dict) -> dict:
    """Runs inference using the saved liver risk pipeline and stores the result.

    Field mapping mirrors the training-time feature names used by
    ml_pipeline/liver/train_nhanes.py (pooled NHANES 2013-2018 data). The
    feature dict key order does not matter — predict_liver() rebuilds the
    row from metadata['feature_order'].
    """
    features = {
        "age_years": payload.age_years,
        "sex": payload.sex,
        "race_ethnicity": payload.race_ethnicity,
        "bmi": payload.bmi,
        "waist_circumference_cm": payload.waist_circumference_cm,
        "general_health": payload.general_health,
        "heavy_alcohol_use": payload.heavy_alcohol_use,
        "smoker": payload.smoker,
        "diabetes_status": payload.diabetes_status,
        "hypertension": payload.hypertension,
        "physical_activity": payload.physical_activity,
    }

    result = predict_liver(model, metadata, features)
    model_version = metadata.get("model_version", FALLBACK_LIVER_MODEL_VERSION)
    response = build_screening_response(
        "liver disease", result["risk_probability"], result["threshold"], model_version,
    )

    await prediction_repo.create({
        "user_id": user_id,
        "condition": "liver_disease",
        "model_version": model_version,
        "input_snapshot": features,
        "result": response,
        "created_at": datetime.now(timezone.utc),

    })

    return response


async def predict_diabetes_pima_risk(
    user_id: str, payload: DiabetesPimaPredictionInput, model, metadata: dict,
) -> dict:
    """Runs inference using the diabetes-pima-v1 pipeline and stores the
    result.

    INDEPENDENT of predict_diabetes_risk() above: a second, separate model
    (Pima Indians Diabetes Database — NIDDK/UCI). This is the "I have
    recent lab results" counterpart to the lab-free BRFSS model, requiring
    an actual glucose reading, blood pressure, and skinfold measurement.
    See ml_pipeline/diabetes_pima/reports/evaluation.md.
    """
    features = {
        "Pregnancies": payload.pregnancies,
        "Glucose": payload.glucose,
        "BloodPressure": payload.blood_pressure,
        "SkinThickness": payload.skin_thickness,
        "BMI": payload.bmi,
        "Age": payload.age,
    }

    result = predict_diabetes_pima(model, metadata, features)
    model_version = metadata.get("model_version", FALLBACK_DIABETES_PIMA_MODEL_VERSION)
    response = build_screening_response(
        "diabetes", result["risk_probability"], result["threshold"], model_version,
    )

    await prediction_repo.create({
        "user_id": user_id,
        "condition": "diabetes_pima",
        "model_version": model_version,
        "input_snapshot": features,
        "result": response,
        "created_at": datetime.now(timezone.utc),
    })

    return response


async def predict_liver_ilpd_risk(
    user_id: str, payload: LiverIlpdPredictionInput, model, metadata: dict,
) -> dict:
    """Runs inference using the locked liver-ilpd-logistic-v1 pipeline and
    stores the result.

    INDEPENDENT of predict_liver_risk() above (liver-nhanes-v1, lab-free):
    a second, separate model trained on the canonical UCI ILPD dataset —
    the "I have my lab report" counterpart, requiring an actual Liver
    Function Test (LFT) panel. See
    ml_pipeline/liver/reports/ilpd_final_model_report.md. Explicitly does
    NOT use the rejected liver_lpd dataset/model (see
    ml_pipeline/liver_lpd/reports/data_integrity_investigation.md).

    Field mapping translates this project's API-friendly names (payload.*)
    to the training-time feature names the locked pipeline expects
    (metadata['feature_names']) — predict_liver_ilpd() rebuilds the row
    from that list regardless of this dict's key order.
    """
    features = {
        "age_years": payload.age,
        "gender": payload.gender,
        "total_bilirubin_mg_dl": payload.total_bilirubin,
        "direct_bilirubin_mg_dl": payload.direct_bilirubin,
        "alkaline_phosphatase_u_l": payload.alkaline_phosphatase,
        "alanine_aminotransferase_u_l": payload.alt_sgpt,
        "aspartate_aminotransferase_u_l": payload.ast_sgot,
        "total_proteins_g_dl": payload.total_proteins,
        "albumin_g_dl": payload.albumin,
        "albumin_globulin_ratio": payload.albumin_globulin_ratio,
    }

    result = predict_liver_ilpd(model, metadata, features)
    model_version = metadata.get("model_version", FALLBACK_LIVER_ILPD_MODEL_VERSION)
    response = build_screening_response(
        "liver disease", result["risk_probability"], result["threshold"], model_version,
    )

    await prediction_repo.create({
        "user_id": user_id,
        "condition": "liver_disease_ilpd",
        "model_version": model_version,
        "input_snapshot": features,
        "result": response,
        "created_at": datetime.now(timezone.utc),
    })

    return response

