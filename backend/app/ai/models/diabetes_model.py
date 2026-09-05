import os

import joblib
import pandas as pd

FEATURE_ORDER = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin",
    "BMI", "DiabetesPedigreeFunction", "Age",
]


def load_diabetes_model(model_path: str):
    """Loads the fitted sklearn Pipeline produced by ml_pipeline/diabetes/train.py."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Diabetes model not found at {model_path}")
    return joblib.load(model_path)


def predict_diabetes(model, features: dict) -> float:
    """Returns the model's predicted probability of elevated diabetes risk (0.0-1.0)."""
    row = [[features[col] for col in FEATURE_ORDER]]
    df = pd.DataFrame(row, columns=FEATURE_ORDER)
    return float(model.predict_proba(df)[0][1])
