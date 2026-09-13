import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
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
DATA_DIR = BASE / "data" / "raw"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR = BASE / "reports"

FEATURE_COLUMNS = [
    "age_years",
    "gender",
    "total_bilirubin_mg_dl",
    "direct_bilirubin_mg_dl",
    "alkaline_phosphatase_u_l",
    "alanine_aminotransferase_u_l",
    "aspartate_aminotransferase_u_l",
    "total_proteins_g_dl",
    "albumin_g_dl",
    "albumin_globulin_ratio",
]

TARGET_COLUMN = "liver_disease_status"
RANDOM_STATE = 42

def build_pipeline(classifier):
    numeric_indices = [i for i, col in enumerate(FEATURE_COLUMNS) if col != "gender"]
    categorical_indices = [i for i, col in enumerate(FEATURE_COLUMNS) if col == "gender"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_indices),
            ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), categorical_indices),
        ],
        remainder="drop"
    )

    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier)
    ])

def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(DATA_DIR / "Indian_Liver_Patient_549_Clean_Dataset.xlsx")

    # Map 2 (no disease) to 0, 1 (disease) to 1
    df[TARGET_COLUMN] = df[TARGET_COLUMN].map({1: 1, 2: 0})
    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])

    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    
    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())

    print("Evaluating Model Families...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    
    candidates = {
        "logistic_regression": build_pipeline(LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)),
        "random_forest": build_pipeline(RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=RANDOM_STATE)),
        "xgboost": build_pipeline(XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight, random_state=RANDOM_STATE)),
    }

    best_roc = 0
    best_name = ""
    for name, pipeline in candidates.items():
        scores = cross_validate(pipeline, X_train, y_train, cv=cv, scoring=["roc_auc", "f1"])
        mean_roc = scores["test_roc_auc"].mean()
        print(f"{name}: ROC-AUC={mean_roc:.4f}")
        if mean_roc > best_roc:
            best_roc = mean_roc
            best_name = name

    print(f"\nBest Family: {best_name}")
    
    final_pipeline = candidates[best_name]
    final_pipeline.fit(X_train, y_train)

    test_proba = final_pipeline.predict_proba(X_test)[:, 1]
    
    # We choose 0.4 to bias slightly towards recall (screening tool)
    threshold = 0.4
    
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
    
    pipeline_path = ARTIFACTS_DIR / "liver_pipeline.pkl"
    joblib.dump(final_pipeline, pipeline_path)
    
    metadata = {
        "model_name": "liver_risk_model_ilpd",
        "model_version": "liver-ilpd-v1",
        "model_algorithm": best_name,
        "feature_order": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "decision_threshold": threshold,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "test_metrics": test_metrics,
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
        }
    }
    
    metadata_path = ARTIFACTS_DIR / "liver_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
        
    print(f"\nSaved {pipeline_path}")
    print(f"Saved {metadata_path}")

if __name__ == "__main__":
    main()
