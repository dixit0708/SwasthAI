import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))
import joblib
import numpy as np
model_path = os.path.join('app', 'ai', 'models', 'heart_clinical_model.pkl')
model = joblib.load(model_path)
import pandas as pd
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
scaler = joblib.load(os.path.join('app', 'ai', 'models', 'scaler.pkl'))
X_scaled = scaler.transform(X)
probs = model.predict_proba(X_scaled)[:, 1]
print('Max Prob:', np.max(probs))
print('99th percentile:', np.percentile(probs, 99))
