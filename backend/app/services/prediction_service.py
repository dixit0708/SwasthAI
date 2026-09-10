from datetime import datetime, timezone

from app.ai.models.diabetes_model import predict_diabetes
from app.ai.safety.response_filter import build_screening_response
from app.db.collections import prediction_repo
from app.models.prediction import DiabetesPredictionInput

# Used only if metadata.json is somehow missing a model_version (load_diabetes_model
# already rejects that at startup) — kept as a last-resort label, never the
# primary source of truth.
FALLBACK_MODEL_VERSION = "diabetes-brfss-v2"


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
