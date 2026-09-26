
import sys, joblib
sys.path.insert(0, '.')
import pandas as pd
model = joblib.load('app/ai/models/heart_clinical_model.pkl')
scaler = joblib.load('app/ai/models/scaler.pkl')

def test_prediction(age, sbp, dbp, tc, hdl, glu, name):
    raw_features_dict = {
        'RIDAGEYR': [age],
        'BPXSY1': [sbp],
        'BPXDI1': [dbp],
        'LBXTC': [tc],
        'LBDHDD': [hdl],
        'LBXGLU': [glu]
    }
    df = pd.DataFrame(raw_features_dict)
    scaled = scaler.transform(df)
    prob = model.predict_proba(scaled)[0, 1]
    print(f'{name} | Age:{age} SBP:{sbp} DBP:{dbp} TC:{tc} HDL:{hdl} GLU:{glu} -> Risk: {prob*100:.1f}%')

print('Testing Clinical Track Model:')
test_prediction(30, 110, 70, 160, 60, 90, 'LOW RISK')
test_prediction(75, 180, 100, 280, 30, 200, 'HIGH RISK')

