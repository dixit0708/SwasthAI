import os
import sys
import asyncio

# Ensure app is in path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.models.prediction import HeartClinicalInput
from app.services.prediction_service import predict_heart_clinical
import joblib

async def test_extreme():
    print("Loading models...")
    model_path = os.path.join("app", "ai", "models", "heart_clinical_model.pkl")
    scaler_path = os.path.join("app", "ai", "models", "scaler.pkl")
    
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    
    # Age=75, Systolic=190, Cholesterol=300, and is on medication
    payload = HeartClinicalInput(
        age=75,
        systolic_bp=190,
        diastolic_bp=100,
        total_cholesterol=300,
        hdl_cholesterol=30, # Low HDL
        fasting_glucose=180, # High glucose
        pulse=90,
        bmi=35.0 # Obese
    )
    
    print("Running prediction...")
    from app.db.collections import prediction_repo
    
    async def mock_create(*args, **kwargs):
        pass
    prediction_repo.create = mock_create
    
    response = await predict_heart_clinical("test_user", payload, model, scaler)
    
    print("\n--- TEST RESULT ---")
    print(f"Risk Probability: {response['risk_probability']}")
    print(f"Risk Level:       {response['risk_level']}")
    print(f"Message:          {response['message']}")
    print("-------------------\n")

if __name__ == "__main__":
    asyncio.run(test_extreme())
