from datetime import datetime, timezone

from app.ai.models.diabetes_model import predict_diabetes
from app.ai.safety.response_filter import build_risk_response
from app.db.collections import prediction_repo
from app.models.prediction import DiabetesPredictionInput

DIABETES_MODEL_VERSION = "diabetes-v1"


async def predict_diabetes_risk(user_id: str, payload: DiabetesPredictionInput, model) -> dict:
    features = {
        "Pregnancies": payload.pregnancies,
        "Glucose": payload.glucose,
        "BloodPressure": payload.blood_pressure,
        "SkinThickness": payload.skin_thickness,
        "Insulin": payload.insulin,
        "BMI": payload.bmi,
        "DiabetesPedigreeFunction": payload.diabetes_pedigree_function,
        "Age": payload.age,
    }
    probability = predict_diabetes(model, features)
    response = build_risk_response("diabetes", probability, DIABETES_MODEL_VERSION)

    await prediction_repo.create({
        "user_id": user_id,
        "condition": "diabetes",
        "model_version": DIABETES_MODEL_VERSION,
        "input_snapshot": features,
        "result": response,
        "created_at": datetime.now(timezone.utc),
    })

    return response
