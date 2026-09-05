import os

import joblib

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
    """Returns the model's predicted probability of elevated diabetes risk (0.0-1.0).

    Takes a plain list (not a pandas DataFrame) so production inference never
    needs to import pandas: the fitted Pipeline is
    SimpleImputer -> StandardScaler -> classifier, none of which require
    named columns, only positional ones in FEATURE_ORDER. pandas stays a
    training-only dependency (see ml_pipeline/diabetes/train.py).
    """
    row = [[features[col] for col in FEATURE_ORDER]]
    return float(model.predict_proba(row)[0][1])
