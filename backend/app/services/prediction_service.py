from datetime import datetime, timezone

from app.ai.models.diabetes_model import predict_diabetes
from app.ai.models.liver_model import predict_liver
from app.ai.safety.response_filter import build_screening_response
from app.db.collections import prediction_repo
from app.models.prediction import DiabetesPredictionInput, LiverPredictionInput

# Used only if metadata.json is somehow missing a model_version (load_diabetes_model
# already rejects that at startup) — kept as a last-resort label, never the
# primary source of truth.
FALLBACK_MODEL_VERSION = "diabetes-brfss-v2"
FALLBACK_LIVER_MODEL_VERSION = "liver-ilpd-v1"


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


async def predict_liver_risk(user_id: str, payload: LiverPredictionInput, model, metadata: dict) -> dict:
    """Runs inference using the saved liver risk pipeline and stores the result.

    Field mapping mirrors the training-time feature names from
    Indian_Liver_Patient_549_Clean_Dataset.xlsx. The feature dict key order
    does not matter — predict_liver() rebuilds the row from metadata['feature_order'].
    """
    features = {
        "age_years": payload.age_years,
        "gender": payload.gender,
        "total_bilirubin_mg_dl": payload.total_bilirubin_mg_dl,
        "direct_bilirubin_mg_dl": payload.direct_bilirubin_mg_dl,
        "alkaline_phosphatase_u_l": payload.alkaline_phosphatase_u_l,
        "alanine_aminotransferase_u_l": payload.alanine_aminotransferase_u_l,
        "aspartate_aminotransferase_u_l": payload.aspartate_aminotransferase_u_l,
        "total_proteins_g_dl": payload.total_proteins_g_dl,
        "albumin_g_dl": payload.albumin_g_dl,
        "albumin_globulin_ratio": payload.albumin_globulin_ratio,
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

