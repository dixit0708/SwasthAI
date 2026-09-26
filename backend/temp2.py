import joblib
import pandas as pd
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
df = pd.read_csv('../ml_pipeline/heart_clinical/data/demographics.csv').merge(
     pd.read_csv('../ml_pipeline/heart_clinical/data/examination.csv'), on='SEQN').merge(
     pd.read_csv('../ml_pipeline/heart_clinical/data/laboratory.csv'), on='SEQN').merge(
     pd.read_csv('../ml_pipeline/heart_clinical/data/questionnaire.csv'), on='SEQN')
target_cols = ['MCQ160B', 'MCQ160C', 'MCQ160E']
df = df.dropna(subset=target_cols, how='all').copy()
df['target'] = ((df['MCQ160B'] == 1) | (df['MCQ160C'] == 1) | (df['MCQ160E'] == 1)).astype(int)
features = ['RIDAGEYR', 'BPXSY1', 'BPXDI1', 'LBXTC', 'LBDHDD', 'LBXGLU', 'BPXPLS', 'BMXBMI']
X = df[features].copy()
for col in features:
    X[col] = X[col].fillna(X[col].median())
scaler = joblib.load(r'C:\Users\sharm\Desktop\SwasthAI\ml_pipeline\heart_clinical\scaler.pkl')
X_scaled = scaler.transform(X)
y = df['target']
clf = XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42, eval_metric='logloss')
cal = CalibratedClassifierCV(estimator=clf, method='isotonic', cv=5)
cal.fit(X_scaled, y)
from app.models.prediction import HeartClinicalInput
payload = HeartClinicalInput(age=75, systolic_bp=190, diastolic_bp=100, total_cholesterol=300, hdl_cholesterol=30, fasting_glucose=180, pulse=90, bmi=35.0)
df_f = pd.DataFrame({'RIDAGEYR': [payload.age], 'BPXSY1': [payload.systolic_bp], 'BPXDI1': [payload.diastolic_bp], 'LBXTC': [payload.total_cholesterol], 'LBDHDD': [payload.hdl_cholesterol], 'LBXGLU': [payload.fasting_glucose], 'BPXPLS': [payload.pulse], 'BMXBMI': [payload.bmi]})
print('Prob:', cal.predict_proba(scaler.transform(df_f))[0, 1])
