import asyncio
from app.models.prediction import HeartClinicalInput
from app.services.prediction_service import predict_heart_clinical
import joblib
import os

model_path = os.path.join('app', 'ai', 'models', 'heart_clinical_model.pkl')
scaler_path = os.path.join('app', 'ai', 'models', 'scaler.pkl')

model = joblib.load(model_path)
scaler = joblib.load(scaler_path)

async def test_cases():
    payload = HeartClinicalInput(
        age=70.0,
        systolic_bp=120.0,
        diastolic_bp=80.0,
        total_cholesterol=200.0,
        hdl_cholesterol=50.0,
        fasting_glucose=100.0,
        pulse=75.0,
        bmi=25.95
    )

    res = await predict_heart_clinical('test_user', payload, model, scaler)
    print(f"Risk Probability: {res['risk_probability']}")
    print(f"Risk Level: {res['risk_level']}")

if __name__ == '__main__':
    from app.services import prediction_service
    class MockRepo:
        async def create(self, doc):
            pass
    prediction_service.prediction_repo = MockRepo()
    asyncio.run(test_cases())
