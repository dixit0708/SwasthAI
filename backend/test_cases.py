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
        age=70.0,
        systolic_bp=120.0,
        diastolic_bp=80.0,
        total_cholesterol=200.0,
        hdl_cholesterol=50.0,
        fasting_glucose=100.0,
        pulse=75.0,
        bmi=25.95
    )
    
    borderline_payload = HeartClinicalInput(
        age=55,
        systolic_bp=140,
        diastolic_bp=90,
        total_cholesterol=220,
        hdl_cholesterol=40,
        fasting_glucose=110,
        pulse=80,
        bmi=28.0
    )

    fatal_payload = HeartClinicalInput(
        age=75,
        systolic_bp=200,
        diastolic_bp=100,
        total_cholesterol=550,
        hdl_cholesterol=35,
        fasting_glucose=150,
        pulse=90,
        bmi=32.0
    )

    print('\n--- HEALTHY TEST ---')
    res_healthy = await predict_heart_clinical('test_user', healthy_payload, model, scaler)
    print(f"Risk Probability: {res_healthy['risk_probability']}")
    print(f"Risk Level: {res_healthy['risk_level']}")
    
    print('\n--- BORDERLINE TEST ---')
    res_border = await predict_heart_clinical('test_user', borderline_payload, model, scaler)
    print(f"Risk Probability: {res_border['risk_probability']}")
    print(f"Risk Level: {res_border['risk_level']}")

    print('\n--- FATAL TEST ---')
    res_fatal = await predict_heart_clinical('test_user', fatal_payload, model, scaler)
    print(f"Risk Probability: {res_fatal['risk_probability']}")
    print(f"Risk Level: {res_fatal['risk_level']}")

if __name__ == '__main__':
    from app.services import prediction_service
    class MockRepo:
        async def create(self, doc):
            pass
    prediction_service.prediction_repo = MockRepo()
    asyncio.run(test_cases())
