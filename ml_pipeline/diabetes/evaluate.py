"""
Evaluate the trained diabetes risk model on the held-out test split.

Reports accuracy, precision, recall, F1, ROC-AUC and the confusion matrix
(never accuracy alone, per AGENTS.md Section 9), plus an age-group slice
breakdown per Section 58 (dataset fairness/limitations must be documented,
not just aggregate metrics). Results are written to
data/processed/evaluation_results.json and appended to EXPERIMENTS.md.

Run: python evaluate.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
MODELS_DIR = Path(__file__).parent / "models"
EXPERIMENTS_LOG = Path(__file__).parent / "EXPERIMENTS.md"

FEATURE_COLUMNS = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin",
    "BMI", "DiabetesPedigreeFunction", "Age",
]
TARGET_COLUMN = "Outcome"


def compute_metrics(y_true, y_pred, y_proba) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n": int(len(y_true)),
    }


def main():
    test_df = pd.read_csv(PROCESSED_DIR / "test.csv")
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN]

    pipeline = joblib.load(MODELS_DIR / "diabetes_model.joblib")
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    overall = compute_metrics(y_test, y_pred, y_proba)

    # Age-group slice check (Section 58): does performance hold up across
    # age bands, or is it concentrated in one group the training data favored?
    slices = {}
    bands = [(21, 30), (31, 45), (46, 100)]
    for lo, hi in bands:
        mask = (test_df["Age"] >= lo) & (test_df["Age"] <= hi)
        if mask.sum() < 5:
            slices[f"age_{lo}_{hi}"] = {"n": int(mask.sum()), "note": "too few samples for a reliable metric"}
            continue
        slices[f"age_{lo}_{hi}"] = compute_metrics(y_test[mask], y_pred[mask], y_proba[mask])

    with open(MODELS_DIR / "diabetes_model_metadata.json") as f:
        metadata = json.load(f)

    results = {
        "model_version": metadata["model_version"],
        "algorithm": metadata["algorithm"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "age_group_slices": slices,
    }

    with open(PROCESSED_DIR / "evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))

    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(f"\n## Run {results['evaluated_at']}\n")
        f.write(f"- algorithm: {results['algorithm']}\n")
        f.write(f"- TEST accuracy: {overall['accuracy']:.4f}\n")
        f.write(f"- TEST precision: {overall['precision']:.4f}\n")
        f.write(f"- TEST recall: {overall['recall']:.4f}\n")
        f.write(f"- TEST f1: {overall['f1']:.4f}\n")
        f.write(f"- TEST roc_auc: {overall['roc_auc']:.4f}\n")
        f.write(f"- confusion_matrix: {overall['confusion_matrix']}\n")


if __name__ == "__main__":
    main()
