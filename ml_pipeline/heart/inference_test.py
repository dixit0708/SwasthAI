"""
Smoke-test: loads the production heart disease model and runs a sample
inference to verify the artifact is valid and the feature contract is intact.

Run: python inference_test.py
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PRODUCTION_MODEL_PATH = (
    Path(__file__).parent.parent.parent
    / "backend" / "app" / "ai" / "models" / "heart_disease_model.pkl"
)

FEATURE_COLUMNS = [
    "Sex",
    "AgeCategory",
    "BMI",
    "GeneralHealth",
    "PhysicalHealthDays",
    "MentalHealthDays",
    "SleepHours",
    "PhysicalActivities",
    "HadStroke",
    "HadAsthma",
    "HadCOPD",
    "HadDepressiveDisorder",
    "HadKidneyDisease",
    "HadArthritis",
    "HadDiabetes",
    "DifficultyWalking",
    "DifficultyConcentrating",
    "DifficultyErrands",
    "SmokerStatus",
    "AlcoholDrinkers",
    "ChestScan",
    "HighRiskLastYear",
    "RemovedTeeth",
    "LastCheckupTime",
]

# --- Two contrasting test samples ---
# Sample A: low-risk profile (young, healthy, non-smoker)
SAMPLE_A = {
    "Sex": 0,                  # Female
    "AgeCategory": 3,          # 30-34
    "BMI": 22.5,
    "GeneralHealth": 5,        # Excellent
    "PhysicalHealthDays": 0.0,
    "MentalHealthDays": 0.0,
    "SleepHours": 7.0,
    "PhysicalActivities": 1,   # Yes
    "HadStroke": 0,
    "HadAsthma": 0,
    "HadCOPD": 0,
    "HadDepressiveDisorder": 0,
    "HadKidneyDisease": 0,
    "HadArthritis": 0,
    "HadDiabetes": 0,
    "DifficultyWalking": 0,
    "DifficultyConcentrating": 0,
    "DifficultyErrands": 0,
    "SmokerStatus": 0,         # Never
    "AlcoholDrinkers": 0,
    "ChestScan": 0,
    "HighRiskLastYear": 0,
    "RemovedTeeth": 0,
    "LastCheckupTime": 0,
}

# Sample B: higher-risk profile (older, smoker, multiple comorbidities)
SAMPLE_B = {
    "Sex": 1,                  # Male
    "AgeCategory": 11,         # 70-74
    "BMI": 31.5,
    "GeneralHealth": 2,        # Fair
    "PhysicalHealthDays": 15.0,
    "MentalHealthDays": 5.0,
    "SleepHours": 5.0,
    "PhysicalActivities": 0,   # No
    "HadStroke": 1,
    "HadAsthma": 0,
    "HadCOPD": 1,
    "HadDepressiveDisorder": 1,
    "HadKidneyDisease": 0,
    "HadArthritis": 1,
    "HadDiabetes": 1,
    "DifficultyWalking": 1,
    "DifficultyConcentrating": 0,
    "DifficultyErrands": 1,
    "SmokerStatus": 3,         # Every day
    "AlcoholDrinkers": 0,
    "ChestScan": 1,
    "HighRiskLastYear": 1,
    "RemovedTeeth": 2,
    "LastCheckupTime": 1,
}


def main():
    print(f"Loading model from: {PRODUCTION_MODEL_PATH}")
    assert PRODUCTION_MODEL_PATH.exists(), (
        f"Model not found at {PRODUCTION_MODEL_PATH}. Run train.py first."
    )
    model = joblib.load(PRODUCTION_MODEL_PATH)
    print("  Model loaded successfully.")

    # Verify feature order
    scaler = model.named_steps["scaler"]
    assert hasattr(scaler, "mean_"), "Pipeline scaler not fitted?"
    assert scaler.n_features_in_ == len(FEATURE_COLUMNS), (
        f"Feature count mismatch: model={scaler.n_features_in_}, "
        f"expected={len(FEATURE_COLUMNS)}"
    )
    print(f"  Feature count: {scaler.n_features_in_} — OK")

    for label, sample in [("Sample A (low-risk)", SAMPLE_A),
                           ("Sample B (high-risk)", SAMPLE_B)]:
        df = pd.DataFrame([sample])[FEATURE_COLUMNS]
        proba = model.predict_proba(df)[0, 1]
        print(f"  {label}: P(heart disease risk) = {proba:.4f}")

    print("\nInference test PASSED.")


if __name__ == "__main__":
    main()
