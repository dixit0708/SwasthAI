"""
Train the diabetes risk model.

Compares several candidate algorithms via cross-validation on the training
split ONLY, per AGENTS.md Section 6 ("XGBoost may be used where appropriate,
but never assume it's automatically the best model — compare suitable
algorithms and select based on validation performance"). The winner is
refit on the full training set and saved as a single sklearn Pipeline
(imputer + scaler + classifier) so preprocessing travels with the model —
the exact same transform is guaranteed at inference time.

Run: python train.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
MODELS_DIR = Path(__file__).parent / "models"

FEATURE_COLUMNS = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin",
    "BMI", "DiabetesPedigreeFunction", "Age",
]
TARGET_COLUMN = "Outcome"
MODEL_VERSION = "diabetes-v1"
RANDOM_STATE = 42


def build_pipeline(classifier) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", classifier),
    ])


CANDIDATES = {
    "logistic_regression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
    "random_forest": RandomForestClassifier(n_estimators=300, random_state=RANDOM_STATE),
    "xgboost": XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        eval_metric="logloss", random_state=RANDOM_STATE,
    ),
}


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_results = {}
    for name, clf in CANDIDATES.items():
        pipeline = build_pipeline(clf)
        scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="roc_auc")
        cv_results[name] = {"mean_roc_auc": float(scores.mean()), "std_roc_auc": float(scores.std())}
        print(f"{name}: ROC-AUC = {scores.mean():.4f} (+/- {scores.std():.4f})")

    best_name = max(cv_results, key=lambda n: cv_results[n]["mean_roc_auc"])
    print(f"\nSelected model: {best_name} (best mean CV ROC-AUC)")

    final_pipeline = build_pipeline(CANDIDATES[best_name])
    final_pipeline.fit(X_train, y_train)

    joblib.dump(final_pipeline, MODELS_DIR / "diabetes_model.joblib")

    metadata = {
        "model_name": "diabetes_risk_model",
        "model_version": MODEL_VERSION,
        "algorithm": best_name,
        "dataset_source": "Pima Indians Diabetes Database (UCI, via jbrownlee/Datasets mirror)",
        "dataset_version": "raw file data/raw/pima-diabetes-raw.csv, 768 rows",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "feature_order": FEATURE_COLUMNS,
        "target": TARGET_COLUMN,
        "preprocessing_version": "median-impute-zero-as-missing + standard-scale (see preprocessing.py)",
        "cross_validation_results": cv_results,
        "limitations": [
            "Training data is exclusively female patients of Pima Indian heritage, age 21+ — "
            "this model must not be presented as generalizing to men, children, or other populations.",
            "Dataset size (768 rows) is small by modern ML standards; confidence intervals on "
            "held-out metrics are wide.",
            "Several input features (Glucose, BloodPressure, SkinThickness, Insulin, BMI) had "
            "substantial missing-value rates in the source data (see data/processed/dataset_stats.json) "
            "and are median-imputed; predictions for patients far outside the training distribution "
            "for these fields should be treated with lower confidence.",
        ],
    }
    with open(MODELS_DIR / "diabetes_model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved model to {MODELS_DIR / 'diabetes_model.joblib'}")
    print(f"Saved metadata to {MODELS_DIR / 'diabetes_model_metadata.json'}")


if __name__ == "__main__":
    main()
