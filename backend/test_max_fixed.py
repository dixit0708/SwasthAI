import joblib
import os
import pandas as pd
import numpy as np

model_path = os.path.join('app', 'ai', 'models', 'heart_clinical_model.pkl')
scaler_path = os.path.join('app', 'ai', 'models', 'scaler.pkl')

model = joblib.load(model_path)
scaler = joblib.load(scaler_path)

df = pd.DataFrame(columns=['RIDAGEYR', 'BPXSY1', 'BPXDI1', 'LBXTC', 'LBDHDD', 'LBXGLU', 'BPXPLS', 'BMXBMI'])

for hdl in range(10, 50, 10):
    for glucose in range(100, 300, 50):
        for pulse in range(60, 110, 10):
            for bmi in range(20, 45, 5):
                df.loc[len(df)] = [75, 190, 100, 300, hdl, glucose, pulse, bmi]

features_scaled = scaler.transform(df)
probs = model.predict_proba(features_scaled)[:, 1]
max_idx = np.argmax(probs)
print('Max Prob:', probs[max_idx])
print('Features for Max Prob:')
print(df.iloc[max_idx])
