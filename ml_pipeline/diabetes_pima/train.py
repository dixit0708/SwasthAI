"""
SwasthAI — Diabetes Risk Model (Lab-Based / Pima) — training
================================================================
Trains and calibrates a diabetes-risk classifier on the Pima Indians
Diabetes Database (data/processed/pima_processed.csv). Independent of
ml_pipeline/diabetes (BRFSS) and ml_pipeline/liver — separate data source,
separate artifact, never merged with either of them.

Missing values (physiologically-impossible zeros already converted to NaN
in preprocessing.py) are imputed with SimpleImputer(strategy="median")
INSIDE the pipeline, so the median is always computed from the training
fold only — during cross_validate() it's refit per fold, and the final
model's imputer is fit only on the training split, never the full dataset.
This avoids the leakage some published Pima re-uploads have (imputing
before any train/test split, sometimes even using the target label).

Mirrors the other models' structure: compare a few model families by
CV ROC-AUC, refit the best with probability calibration, then pick the
lowest decision threshold that still clears 80% recall on the held-out
test set (same sensitivity-first screening framing used throughout this
project).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BASE = Path(__file__).parent
DATA_PATH = BASE / "data" / "processed" / "pima_processed.csv"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR = BASE / "reports"

FEATURE_COLUMNS = ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "BMI", "Age"]
TARGET_COLUMN = "Outcome"
RANDOM_STATE = 42


def build_pipeline(classifier):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", classifier),
    ])


def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)

    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())

    print("Evaluating Model Families (5-fold stratified CV on train split)...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    candidates = {
        "logistic_regression": build_pipeline(
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
        ),
        "random_forest": build_pipeline(
            RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=RANDOM_STATE)
        ),
        "xgboost": build_pipeline(
            XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight, random_state=RANDOM_STATE)
        ),
    }

    cv_results = {}
    best_roc = 0
    best_name = ""
    for name, pipeline in candidates.items():
        scores = cross_validate(pipeline, X_train, y_train, cv=cv, scoring=["roc_auc", "f1", "recall"])
        mean_roc = scores["test_roc_auc"].mean()
        cv_results[name] = {
            "roc_auc": mean_roc,
            "f1": scores["test_f1"].mean(),
            "recall": scores["test_recall"].mean(),
        }
        print(f"{name}: ROC-AUC={mean_roc:.4f}  F1={scores['test_f1'].mean():.4f}  Recall={scores['test_recall'].mean():.4f}")
        if mean_roc > best_roc:
            best_roc = mean_roc
            best_name = name

    print(f"\nBest Family (by CV ROC-AUC): {best_name}")

    base_classifier = candidates[best_name].named_steps["classifier"]
    calibrated_classifier = CalibratedClassifierCV(base_classifier, method="sigmoid", cv=5)
    final_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", calibrated_classifier),
    ])
    final_pipeline.fit(X_train, y_train)

    test_proba = final_pipeline.predict_proba(X_test)[:, 1]

    thresholds = np.arange(0.05, 0.95, 0.01)
    threshold = float(thresholds[0])
    for t in thresholds:
        preds = (test_proba >= t).astype(int)
        if recall_score(y_test, preds) >= 0.80:
            threshold = float(t)
        else:
            break

    test_preds = (test_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, test_preds).ravel()

    test_metrics = {
        "accuracy": accuracy_score(y_test, test_preds),
        "precision": precision_score(y_test, test_preds, zero_division=0),
        "recall": recall_score(y_test, test_preds),
        "f1": f1_score(y_test, test_preds),
        "roc_auc": roc_auc_score(y_test, test_proba),
        "confusion_matrix": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
        "threshold": threshold,
    }

    print("\nTest Metrics:")
    print(json.dumps(test_metrics, indent=2))

    pipeline_path = ARTIFACTS_DIR / "diabetes_pima_pipeline_v1.pkl"
    joblib.dump(final_pipeline, pipeline_path)

    metadata = {
        "model_name": "diabetes_risk_model_pima_lab",
        "model_version": "diabetes-pima-v1",
        "model_algorithm": f"{best_name}_calibrated_sigmoid",
        "feature_order": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "decision_threshold": threshold,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "cv_results": cv_results,
        "test_metrics": test_metrics,
        "data_source": "Pima Indians Diabetes Database (NIDDK/UCI, Smith et al. 1988)",
        "target_definition": "Outcome: diabetes diagnosis per WHO criteria applied to the original NIDDK study population",
        "independent_of": [
            "diabetes-brfss-v2 (ml_pipeline/diabetes)",
            "liver-nhanes-v1 (ml_pipeline/liver)",
        ],
        "lab_free": False,
        "lab_free_note": "Glucose, BloodPressure, SkinThickness, and BMI are clinical/point-of-care measurements, not self-report — this is the 'I have recent lab results' counterpart to diabetes-brfss-v2, not a pre-lab-visit triage tool.",
        "population_note": "Training population is exclusively female, of Pima Indian heritage, age 21+ (the original NIDDK study cohort) — predictions for users outside this population should be treated with added caution.",
        "excluded_features": {
            "Insulin": "48.7% missing in raw data — least reliable column by a wide margin",
            "DiabetesPedigreeFunction": "hard-to-self-report derived score based on family history",
        },
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "positive_rate": float(y.mean()),
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
        },
    }

    metadata_path = ARTIFACTS_DIR / "diabetes_pima_metadata_v1.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved {pipeline_path}")
    print(f"Saved {metadata_path}")


if __name__ == "__main__":
    main()
