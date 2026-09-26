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
    healthy_payload = HeartClinicalInput(
        age=25,
        systolic_bp=110,
        diastolic_bp=70,
        total_cholesterol=160,
        hdl_cholesterol=60,
        fasting_glucose=90,
        pulse=70,
        bmi=22.0
    )
    
    fatal_payload = HeartClinicalInput(
        age=75,
        systolic_bp=200,
        diastolic_bp=100,
        total_cholesterol=550,
        hdl_cholesterol=20,
        fasting_glucose=150,
        pulse=90,
        bmi=32.0
    )

    print('\n--- HEALTHY TEST ---')
    res = await predict_heart_clinical('test_user', healthy_payload, model, scaler)
    print(f"Risk Probability (Scaled): {res['risk_probability']}")
    print(f"Risk Level: {res['risk_level']}")
    
    print('\n--- FATAL TEST ---')
    res = await predict_heart_clinical('test_user', fatal_payload, model, scaler)
    print(f"Risk Probability (Scaled): {res['risk_probability']}")
    print(f"Risk Level: {res['risk_level']}")

if __name__ == '__main__':
    from app.services import prediction_service
    class MockRepo:
        async def create(self, doc):
            pass
    prediction_service.prediction_repo = MockRepo()
    asyncio.run(test_cases())
