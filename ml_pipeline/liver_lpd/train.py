"""
SwasthAI — Liver Disease Risk Model (Lab-Based / LPD) — training
====================================================================
Trains a liver-disease classifier on the cleaned, deduplicated LPD dataset
(data/processed/liver_lpd_processed.csv). This is the deliberate "I have
my lab report" counterpart to ml_pipeline/liver/train_nhanes.py
(liver-nhanes-v1, lab-free) — same relationship as diabetes-pima-v1 is to
diabetes-brfss-v2. Independent artifact, never merged with either.

Split/threshold methodology mirrors every other model in this project
(train_nhanes.py, diabetes_pima/train.py): 60/20/20 train/val/test,
stratified. Model family is chosen by 5-fold CV ROC-AUC on train+val: the
test set plays no part in that choice. The decision threshold is then
swept on the held-out validation split only (fit on train), and the final
pipeline is refit on train+val and evaluated on the test split exactly
once — the test set is never used to pick a model, a hyperparameter, or a
threshold.

No target accuracy number was set before this ran, and none was optimized
for after the fact: per AGENTS.md Section 9 ("never fabricate performance
metrics, never improve metrics artificially"), the metrics below are
whatever this honest, leakage-checked methodology produces. See
reports/evaluation.md for the achieved numbers and an explicit discussion
of what would be required to push them higher, and why that isn't done
here.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from xgboost import XGBClassifier

BASE = Path(__file__).parent
DATA_PATH = BASE / "data" / "processed" / "liver_lpd_processed.csv"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR = BASE / "reports"

NUMERIC_FEATURES = [
    "age_years", "total_bilirubin_mg_dl", "direct_bilirubin_mg_dl",
    "alkaline_phosphatase_u_l", "alanine_aminotransferase_u_l",
    "aspartate_aminotransferase_u_l", "total_proteins_g_dl", "albumin_g_dl",
    "albumin_globulin_ratio",
]
CATEGORICAL_FEATURES = ["gender"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "liver_disease_status"
RANDOM_STATE = 42


def build_pipeline(classifier):
    numeric_indices = list(range(len(NUMERIC_FEATURES)))
    categorical_indices = list(range(len(NUMERIC_FEATURES), len(FEATURE_COLUMNS)))

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_indices),
            ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), categorical_indices),
        ],
        remainder="drop",
    )

    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])


def sweep_threshold_for_recall(proba: np.ndarray, y_true: pd.Series, target_recall: float = 0.80) -> float:
    thresholds = np.linspace(0.05, 0.95, 91)
    threshold = 0.5
    for t in thresholds:
        preds = (proba >= t).astype(int)
        if recall_score(y_true, preds) >= target_recall:
            threshold = float(t)
        else:
            break
    return threshold


def accuracy_maximizing_threshold(proba: np.ndarray, y_true: pd.Series) -> tuple:
    thresholds = np.linspace(0.05, 0.95, 91)
    best_t, best_acc = 0.5, 0.0
    for t in thresholds:
        preds = (proba >= t).astype(int)
        acc = accuracy_score(y_true, preds)
        if acc > best_acc:
            best_acc, best_t = acc, float(t)
    return best_t, best_acc


def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].astype(int)

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=RANDOM_STATE, stratify=y_trainval
    )
    # Overall split is ~60% train / 20% val / 20% test.

    scale_pos_weight = float((y_trainval == 0).sum() / (y_trainval == 1).sum())

    print("Evaluating Model Families (5-fold CV on train+val, test set untouched)...")
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
        scores = cross_validate(pipeline, X_trainval, y_trainval, cv=cv, scoring=["roc_auc", "f1", "recall", "accuracy"])
        mean_roc = scores["test_roc_auc"].mean()
        cv_results[name] = {
            "roc_auc": mean_roc,
            "f1": scores["test_f1"].mean(),
            "recall": scores["test_recall"].mean(),
            "accuracy": scores["test_accuracy"].mean(),
        }
        print(f"{name}: ROC-AUC={mean_roc:.4f}  F1={scores['test_f1'].mean():.4f}  "
              f"Recall={scores['test_recall'].mean():.4f}  Accuracy={scores['test_accuracy'].mean():.4f}")
        if mean_roc > best_roc:
            best_roc = mean_roc
            best_name = name

    print(f"\nBest Family (by CV ROC-AUC): {best_name}")

    # Threshold selection: fit a fresh (unfit) clone of the chosen pipeline
    # on train only, sweep against the held-out validation split — the
    # test set plays no part in this decision.
    threshold_pipeline = clone(candidates[best_name])
    threshold_pipeline.fit(X_train, y_train)
    val_proba = threshold_pipeline.predict_proba(X_val)[:, 1]
    threshold = sweep_threshold_for_recall(val_proba, y_val, target_recall=0.80)
    acc_max_threshold, acc_max_value = accuracy_maximizing_threshold(val_proba, y_val)
    print(f"Threshold chosen on validation split (80% recall target): {threshold:.2f}")
    print(f"For reference — accuracy-maximizing threshold on validation: {acc_max_threshold:.2f} "
          f"(accuracy {acc_max_value:.4f}); NOT used as the production threshold "
          f"(see reports/evaluation.md for why).")

    # Final production pipeline: refit on train+val combined, then evaluate
    # this exact pipeline+threshold on the test set exactly once.
    final_pipeline = candidates[best_name]
    final_pipeline.fit(X_trainval, y_trainval)

    test_proba = final_pipeline.predict_proba(X_test)[:, 1]
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

    print("\nTest Metrics (test set touched exactly once, after threshold was fixed on validation):")
    print(json.dumps(test_metrics, indent=2))

    pipeline_path = ARTIFACTS_DIR / "liver_lpd_pipeline_v1.pkl"
    joblib.dump(final_pipeline, pipeline_path)

    metadata = {
        "model_name": "liver_risk_model_lpd_lab",
        "model_version": "liver-lpd-v1",
        "model_algorithm": best_name,
        "feature_order": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "decision_threshold": threshold,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "cv_results": cv_results,
        "test_metrics": test_metrics,
        "accuracy_maximizing_threshold_reference": {
            "threshold": acc_max_threshold,
            "validation_accuracy": acc_max_value,
            "note": "NOT the production threshold. Reported only for transparency about the "
                    "accuracy/recall trade-off; see reports/evaluation.md.",
        },
        "data_source": "User-provided 'Liver Patient Dataset (LPD)' CSV, ILPD-schema, 30,691 raw rows "
                        "(11,323 exact duplicates dropped before any split — see data/raw/README.md)",
        "target_definition": "Result: liver patient (1) vs not a liver patient (2), remapped to 1/0",
        "split_methodology": "60/20/20 train/val/test (stratified); threshold chosen by recall-sweep on "
                              "the val split only, final pipeline refit on train+val, test set evaluated exactly once",
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_test)),
        "n_raw_rows": 30691,
        "n_exact_duplicates_dropped": 11323,
        "n_after_cleaning": int(len(df)),
        "positive_rate": float(y.mean()),
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
        },
    }

    metadata_path = ARTIFACTS_DIR / "liver_lpd_metadata_v1.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved {pipeline_path}")
    print(f"Saved {metadata_path}")


if __name__ == "__main__":
    main()
