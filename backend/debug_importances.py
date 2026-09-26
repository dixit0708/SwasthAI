"""Targeted symptom sensitivity tests."""
import sys, json, joblib
sys.path.insert(0, ".")
pipeline = joblib.load("app/ai/models/heart_disease_model.pkl")
meta = json.load(open("../ml_pipeline/heart/artifacts/heart_metadata.json"))
from app.ai.models.heart_model import predict_heart

BASE = {
    "Sex": "Male", "AgeCategory": "Age 35 to 39", "BMI": 27.0,
    "GeneralHealth": "Fair", "PhysicalHealthDays": 10.0, "MentalHealthDays": 10.0,
    "SleepHours": 6.0, "PhysicalActivities": "No",
    "HadStroke": "No", "HadAsthma": "No", "HadCOPD": "No",
    "HadDepressiveDisorder": "No", "HadKidneyDisease": "No", "HadArthritis": "No",
    "HadDiabetes": "No", "DifficultyWalking": "No", "DifficultyConcentrating": "No",
    "DifficultyErrands": "No", "SmokerStatus": "Never smoked", "AlcoholDrinkers": "No",
    "ChestScan": "No", "HighRiskLastYear": "No", "RemovedTeeth": "None of them",
    "LastCheckupTime": "Within past year (anytime less than 12 months ago)",
}

def test(label, overrides):
    r = predict_heart(pipeline, meta, {**BASE, **overrides})
    p = r["risk_probability"] * 100
    flag = "ELEVATED" if r["is_elevated"] else "low    "
    print(f"  {flag}  {p:5.1f}%   {label}")

print("=== SYMPTOM SENSITIVITY (base: male 35-39, fair health, no conditions) ===")
test("baseline", {})
test("+ difficulty walking", {"DifficultyWalking": "Yes"})
test("+ difficulty concentrating", {"DifficultyConcentrating": "Yes"})
test("+ difficulty walking + concentrating", {"DifficultyWalking": "Yes", "DifficultyConcentrating": "Yes"})
test("+ chest scan", {"ChestScan": "Yes"})
test("+ chest scan + walk + concentrate", {"ChestScan": "Yes", "DifficultyWalking": "Yes", "DifficultyConcentrating": "Yes"})
test("+ stroke", {"HadStroke": "Yes"})
test("+ arthritis", {"HadArthritis": "Yes"})
test("+ diabetes", {"HadDiabetes": "Yes"})
test("+ heavy smoker", {"SmokerStatus": "Current smoker - now smokes every day"})
test("+ walk+concentrate+stroke+smoker+poor health", {
    "DifficultyWalking": "Yes", "DifficultyConcentrating": "Yes",
    "HadStroke": "Yes", "SmokerStatus": "Current smoker - now smokes every day",
    "GeneralHealth": "Poor", "ChestScan": "Yes"})

print("\n=== AGE + SYMPTOMS (walk+concentrate+stroke+smoker) ===")
SICK = {"DifficultyWalking": "Yes", "DifficultyConcentrating": "Yes",
        "HadStroke": "Yes", "SmokerStatus": "Current smoker - now smokes every day",
        "GeneralHealth": "Poor"}
for age in ["Age 18 to 24","Age 35 to 39","Age 50 to 54","Age 65 to 69","Age 80 or older"]:
    test(age, {**SICK, "AgeCategory": age})
