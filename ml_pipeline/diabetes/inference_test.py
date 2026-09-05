"""
Smoke test for the saved diabetes model — loads the pipeline exactly as
production inference (backend/app/ai/models/diabetes_model.py) will, and
runs it against a couple of hand-picked sample inputs to sanity-check the
output shape and probability range before wiring it into the API.

Run: python inference_test.py
"""
from pathlib import Path

import joblib
import pandas as pd

MODELS_DIR = Path(__file__).parent / "models"
FEATURE_COLUMNS = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin",
    "BMI", "DiabetesPedigreeFunction", "Age",
]

SAMPLES = [
    # A profile with several parameters in a healthier range.
    {"Pregnancies": 1, "Glucose": 95, "BloodPressure": 70, "SkinThickness": 20,
     "Insulin": 80, "BMI": 22.5, "DiabetesPedigreeFunction": 0.2, "Age": 25},
    # A profile with several parameters in an elevated-risk range.
    {"Pregnancies": 6, "Glucose": 165, "BloodPressure": 88, "SkinThickness": 35,
     "Insulin": 200, "BMI": 35.0, "DiabetesPedigreeFunction": 0.9, "Age": 48},
]


def main():
    pipeline = joblib.load(MODELS_DIR / "diabetes_model.joblib")
    df = pd.DataFrame(SAMPLES, columns=FEATURE_COLUMNS)

    predictions = pipeline.predict(df)
    probabilities = pipeline.predict_proba(df)[:, 1]

    for sample, pred, proba in zip(SAMPLES, predictions, probabilities):
        print(f"input={sample}")
        print(f"  -> predicted_class={int(pred)} elevated_risk_probability={proba:.3f}\n")


if __name__ == "__main__":
    main()
