import joblib
import pandas as pd
scaler = joblib.load(r'C:\Users\sharm\Desktop\SwasthAI\ml_pipeline\heart_clinical\scaler.pkl')
model = joblib.load(r'C:\Users\sharm\Desktop\SwasthAI\ml_pipeline\heart_clinical\heart_clinical_model.pkl')
from app.models.prediction import HeartClinicalInput
payload = HeartClinicalInput(age=75, systolic_bp=190, diastolic_bp=120, total_cholesterol=300, hdl_cholesterol=10, fasting_glucose=300, pulse=120, bmi=45.0)
df_f = pd.DataFrame({'RIDAGEYR': [payload.age], 'BPXSY1': [payload.systolic_bp], 'BPXDI1': [payload.diastolic_bp], 'LBXTC': [payload.total_cholesterol], 'LBDHDD': [payload.hdl_cholesterol], 'LBXGLU': [payload.fasting_glucose], 'BPXPLS': [payload.pulse], 'BMXBMI': [payload.bmi]})
print('Prob:', model.predict_proba(scaler.transform(df_f))[0, 1])
