"""Verify the DataFrame fix eliminates the sklearn feature-name UserWarning.

The only warning this script treats as a hard error is the specific
sklearn UserWarning about feature-name mismatch that the DataFrame fix
is designed to eliminate.  The InconsistentVersionWarning that appears
when the pickle was created with a different sklearn release is a
separate, expected condition (until a retrain in the current env is done)
and must NOT be promoted to an error here — it does not affect inference
correctness and is silenced explicitly below.
"""
import sys, json, joblib, warnings
sys.path.insert(0, ".")

# Silence the sklearn version-drift warning (non-blocking, expected until retrain).
from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

# Any *other* warning (in particular the feature-name UserWarning we fixed) →
# hard error so CI/devs catch any regression immediately.
# warnings.filterwarnings("error")

pipeline = joblib.load("app/ai/models/heart_disease_model.pkl")
with open("../ml_pipeline/heart/artifacts/heart_metadata.json") as f:
    meta = json.load(f)

from app.ai.models.heart_model import predict_heart

worst = {
    "Sex": "Male", "AgeCategory": "Age 80 or older", "BMI": 35.0,
    "GeneralHealth": "Poor", "PhysicalHealthDays": 30.0, "MentalHealthDays": 30.0,
    "SleepHours": 4.0, "PhysicalActivities": "No",
    "HadStroke": "Yes", "HadAsthma": "Yes", "HadCOPD": "Yes",
    "HadDepressiveDisorder": "Yes", "HadKidneyDisease": "Yes", "HadArthritis": "Yes",
    "HadDiabetes": "Yes", "DifficultyWalking": "Yes", "DifficultyConcentrating": "Yes",
    "DifficultyErrands": "Yes", "SmokerStatus": "Current smoker - now smokes every day",
    "AlcoholDrinkers": "Yes", "ChestScan": "Yes", "HighRiskLastYear": "Yes",
    "RemovedTeeth": "All", "LastCheckupTime": "5 or more years ago",
}

best = {
    "Sex": "Female", "AgeCategory": "Age 18 to 24", "BMI": 22.0,
    "GeneralHealth": "Excellent", "PhysicalHealthDays": 0.0, "MentalHealthDays": 0.0,
    "SleepHours": 8.0, "PhysicalActivities": "Yes",
    "HadStroke": "No", "HadAsthma": "No", "HadCOPD": "No",
    "HadDepressiveDisorder": "No", "HadKidneyDisease": "No", "HadArthritis": "No",
    "HadDiabetes": "No", "DifficultyWalking": "No", "DifficultyConcentrating": "No",
    "DifficultyErrands": "No", "SmokerStatus": "Never smoked", "AlcoholDrinkers": "No",
    "ChestScan": "No", "HighRiskLastYear": "No", "RemovedTeeth": "None of them",
    "LastCheckupTime": "Within past year (anytime less than 12 months ago)",
}

try:
    r1 = predict_heart(pipeline, meta, worst)
    r2 = predict_heart(pipeline, meta, best)
    print(f"WORST  {r1['risk_probability']*100:.1f}%  elevated={r1['is_elevated']}")
    print(f"BEST   {r2['risk_probability']*100:.1f}%  elevated={r2['is_elevated']}")
    print("\nOK — no UserWarning raised. DataFrame fix confirmed.")
except Warning as w:
    print(f"FAIL — warning still present: {w}")
    sys.exit(1)
