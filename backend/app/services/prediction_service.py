from datetime import datetime, timezone

from app.ai.models.diabetes_model import predict_diabetes
from app.ai.models.diabetes_pima_model import predict_diabetes_pima
from app.ai.models.liver_model import predict_liver
from app.ai.models.liver_ilpd_model import predict_liver_ilpd
from app.ai.safety.response_filter import build_screening_response
from app.db.collections import prediction_repo
from app.models.prediction import (
    DiabetesPimaPredictionInput, DiabetesPredictionInput, LiverIlpdPredictionInput, LiverPredictionInput,
)

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

