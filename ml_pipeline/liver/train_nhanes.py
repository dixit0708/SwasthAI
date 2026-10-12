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
DATA_PATH = BASE / "data" / "processed" / "nhanes_liver_pooled.csv"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR = BASE / "reports"

NUMERIC_FEATURES = ["age_years", "bmi", "waist_circumference_cm"]
CATEGORICAL_FEATURES = [
    "sex", "race_ethnicity", "general_health", "heavy_alcohol_use", "smoker",
    "diabetes_status", "hypertension", "physical_activity",
]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

TARGET_COLUMN = "liver_condition"
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


def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])

    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].astype(int)

    # Three-way split, not two: the decision threshold is itself a choice
    # made *using* labeled data (AGENTS.md Section 8 — "never allow test
    # data to influence training/model selection"). A threshold picked by
    # sweeping against the same test set used for final reporting is a
    # real, if narrow, form of that leak — it optimizes the threshold for
    # the exact data the headline numbers are computed on. Held out here:
    # X_val exists only to choose the threshold; X_test is touched exactly
    # once, after the threshold is already fixed.
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=RANDOM_STATE, stratify=y_trainval
    )
    # Overall split is ~60% train / 20% val / 20% test.

    scale_pos_weight = float((y_trainval == 0).sum() / (y_trainval == 1).sum())

    print("Evaluating Model Families (CV on train+val, test set untouched)...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    candidates = {
        "logistic_regression": build_pipeline(
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
        ),
        "random_forest": build_pipeline(
            RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=RANDOM_STATE)
        ),
        "xgboost": build_pipeline(
            XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight, random_state=RANDOM_STATE)
        ),
    }

    cv_results = {}
    best_roc = 0
    best_name = ""
    for name, pipeline in candidates.items():
        scores = cross_validate(pipeline, X_trainval, y_trainval, cv=cv, scoring=["roc_auc", "f1", "recall"])
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

    # Threshold selection: fit a fresh (unfit) clone of the chosen pipeline
    # on train only, sweep against the held-out validation split — the
    # test set plays no part in this decision.
    threshold_pipeline = clone(candidates[best_name])
    threshold_pipeline.fit(X_train, y_train)
    val_proba = threshold_pipeline.predict_proba(X_val)[:, 1]
    threshold = sweep_threshold_for_recall(val_proba, y_val, target_recall=0.80)
    print(f"Threshold chosen on validation split: {threshold:.2f}")

    # Final production pipeline: refit on train+val combined (all
    # non-test data) at the threshold just chosen, so the shipped model
    # isn't trained on less data than necessary — then evaluate this exact
    # pipeline+threshold on the test set exactly once, for the headline
    # numbers.
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

    pipeline_path = ARTIFACTS_DIR / "liver_pipeline_nhanes_v1.pkl"
    joblib.dump(final_pipeline, pipeline_path)

    metadata = {
        "model_name": "liver_risk_model_nhanes",
        "model_version": "liver-nhanes-v1",
        "model_algorithm": best_name,
        "feature_order": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "decision_threshold": threshold,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "cv_results": cv_results,
        "test_metrics": test_metrics,
        "data_source": "NHANES 2013-2014 / 2015-2016 / 2017-2018 pooled (SEQN-merged within cycle)",
        "target_definition": "MCQ160L: self-reported, doctor-diagnosed liver condition (Yes/No)",
        "split_methodology": "60/20/20 train/val/test (stratified); threshold chosen by recall-sweep on the val split only, final pipeline refit on train+val, test set evaluated exactly once",
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_test)),
        "positive_rate": float(y.mean()),
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
        },
    }

    metadata_path = ARTIFACTS_DIR / "liver_metadata_nhanes_v1.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved {pipeline_path}")
    print(f"Saved {metadata_path}")


if __name__ == "__main__":
    main()
