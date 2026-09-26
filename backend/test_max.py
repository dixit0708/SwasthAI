import joblib
import os
import pandas as pd
import numpy as np

model_path = os.path.join('app', 'ai', 'models', 'heart_clinical_model.pkl')
scaler_path = os.path.join('app', 'ai', 'models', 'scaler.pkl')

model = joblib.load(model_path)
scaler = joblib.load(scaler_path)

df = pd.read_csv('../ml_pipeline/heart_clinical/data/demographics.csv').merge(
     pd.read_csv('../ml_pipeline/heart_clinical/data/examination.csv'), on='SEQN').merge(
     pd.read_csv('../ml_pipeline/heart_clinical/data/laboratory.csv'), on='SEQN').merge(
     pd.read_csv('../ml_pipeline/heart_clinical/data/questionnaire.csv'), on='SEQN')
target_cols = ['MCQ160B', 'MCQ160C', 'MCQ160E']
df = df.dropna(subset=target_cols, how='all').copy()
features = ['RIDAGEYR', 'BPXSY1', 'BPXDI1', 'LBXTC', 'LBDHDD', 'LBXGLU', 'BPXPLS', 'BMXBMI']
X = df[features].copy()
for col in features:
    X[col] = X[col].fillna(X[col].median())

features_scaled = scaler.transform(X)
probs = model.predict_proba(features_scaled)[:, 1]
max_idx = np.argmax(probs)
print('Max Prob:', probs[max_idx])
print('Features for Max Prob:')
print(X.iloc[max_idx])
