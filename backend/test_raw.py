import joblib
import os
import pandas as pd
from app.models.prediction import HeartClinicalInput

model_path = os.path.join('app', 'ai', 'models', 'heart_clinical_model.pkl')
scaler_path = os.path.join('app', 'ai', 'models', 'scaler.pkl')

model = joblib.load(model_path)
scaler = joblib.load(scaler_path)

payload = HeartClinicalInput(
    age=85,
    systolic_bp=250,
    diastolic_bp=120,
    total_cholesterol=500,
    hdl_cholesterol=10,
    fasting_glucose=300,
    pulse=120,
    bmi=45.0
)
df_features = pd.DataFrame({'RIDAGEYR': [payload.age], 'BPXSY1': [payload.systolic_bp], 'BPXDI1': [payload.diastolic_bp], 'LBXTC': [payload.total_cholesterol], 'LBDHDD': [payload.hdl_cholesterol], 'LBXGLU': [payload.fasting_glucose], 'BPXPLS': [payload.pulse], 'BMXBMI': [payload.bmi]})
features_scaled = scaler.transform(df_features)
print('Raw Prob:', model.predict_proba(features_scaled)[0, 1])
