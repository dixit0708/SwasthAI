"""
Analysis-only script for the original UCI ILPD (583-row) dataset.

Does NOT save any production artifact, does NOT touch backend/frontend
code, does NOT modify the currently-shipped liver-nhanes-v1 model. This
exists purely to answer: does the original, documented ILPD dataset
support a trustworthy lab-based liver model, as opposed to the
suspect 30,691-row "LPD" file investigated separately in
ml_pipeline/liver_lpd/reports/data_integrity_investigation.md?

Methodology:
  - Raw file: data/raw/ilpd_uci_original.csv (downloaded directly from the
    UCI Machine Learning Repository, Ramana & Venkateswarlu 2022,
    https://doi.org/10.24432/C5D02C, CC BY 4.0).
  - Exact duplicate rows dropped before anything else touches the data.
  - All preprocessing (missing-value imputation, scaling, one-hot
    encoding) lives inside an sklearn Pipeline, so cross_val_predict
    refits it fresh on each fold's training data only — no statistic is
    ever computed on data a fold's validation split will be scored on.
  - Model comparison via 5-fold StratifiedKFold, using
    cross_val_predict(..., method="predict_proba") to get genuine
    out-of-fold probability estimates for every row (each row's
    prediction comes from a model that never saw that row during
    training) — this is what the full CV metrics and the later threshold
    sweep are both computed from.
  - A decision-tree depth sweep (identical diagnostic used on the LPD
    file) checks for the same kind of near-deterministic-label artifact
    found there.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from pathlib import Path

BASE = Path(__file__).parent
RAW_PATH = BASE / "data" / "raw" / "ilpd_uci_original.csv"

COLS = [
    "age_years", "gender", "total_bilirubin_mg_dl", "direct_bilirubin_mg_dl",
    "alkaline_phosphatase_u_l", "alanine_aminotransferase_u_l",
    "aspartate_aminotransferase_u_l", "total_proteins_g_dl", "albumin_g_dl",
    "albumin_globulin_ratio", "liver_disease_status",
]
NUMERIC_FEATURES = [c for c in COLS[:-1] if c != "gender"]
CATEGORICAL_FEATURES = ["gender"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "liver_disease_status"
RANDOM_STATE = 42


def build_pipeline(classifier):
    numeric_indices = list(range(len(NUMERIC_FEATURES)))
    categorical_indices = list(range(len(NUMERIC_FEATURES), len(FEATURE_COLUMNS)))
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), numeric_indices),
            ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), categorical_indices),
        ],
        remainder="drop",
    )
    return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])


def specificity_score(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return tn / (tn + fp) if (tn + fp) else 0.0


def full_metrics(y_true, y_pred, y_proba):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "roc_auc": roc_auc_score(y_true, y_proba),
        "pr_auc": average_precision_score(y_true, y_proba),
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred),
        "specificity": specificity_score(y_true, y_pred),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }


def main():
    df = pd.read_csv(RAW_PATH, header=None, names=COLS)

    print(f"Raw rows: {len(df)}")
    n_dupes = df.duplicated().sum()
    print(f"Exact full-row duplicates: {n_dupes} ({n_dupes/len(df):.1%})")
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Rows after dedup: {len(df)}")

    df[TARGET_COLUMN] = df[TARGET_COLUMN].map({1: 1, 2: 0})
    print(f"\nMissing values:\n{df[FEATURE_COLUMNS].isna().sum().to_string()}")
    print(f"\nClass balance:\n{df[TARGET_COLUMN].value_counts().to_string()}")
    print(f"Positive rate: {df[TARGET_COLUMN].mean():.4f}")

    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].astype(int).values

    # --- Leakage sanity check: decision-tree depth sweep (same diagnostic
    # used on the suspect LPD file) ---
    numeric_only = df[NUMERIC_FEATURES].values
    Xtr, Xte, ytr, yte = train_test_split(numeric_only, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y)
    print("\n--- Decision-tree depth sweep (leakage/determinism sanity check) ---")
    for depth in [2, 3, 4, 6, None]:
        clf = DecisionTreeClassifier(max_depth=depth, random_state=RANDOM_STATE)
        clf.fit(Xtr, ytr)
        proba = clf.predict_proba(Xte)[:, 1]
        preds = clf.predict(Xte)
        print(f"depth={depth}: test accuracy={accuracy_score(yte, preds):.4f}  "
              f"test ROC-AUC={roc_auc_score(yte, proba):.4f}  n_leaves={clf.get_n_leaves()}")

    # --- Leakage-safe CV model comparison via out-of-fold predictions ---
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    scale_pos_weight = float((y == 0).sum() / (y == 1).sum())

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

    oof_results = {}
    print("\n--- 5-fold out-of-fold CV comparison (threshold=0.5 for this table only) ---")
    for name, pipeline in candidates.items():
        oof_proba = cross_val_predict(pipeline, X, y, cv=cv, method="predict_proba")[:, 1]
        oof_preds = (oof_proba >= 0.5).astype(int)
        metrics = full_metrics(y, oof_preds, oof_proba)
        oof_results[name] = {"proba": oof_proba, "metrics": metrics}
        print(f"{name}: " + "  ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                                       for k, v in metrics.items()))

    best_name = max(oof_results, key=lambda n: oof_results[n]["metrics"]["roc_auc"])
    print(f"\nBest by out-of-fold ROC-AUC: {best_name}")

    # --- Threshold sweep on the best model's OOF probabilities ---
    best_proba = oof_results[best_name]["proba"]
    print(f"\n--- Threshold sweep on {best_name}'s out-of-fold probabilities ---")
    thresholds = np.round(np.arange(0.10, 0.91, 0.05), 2)
    sweep_rows = []
    for t in thresholds:
        preds = (best_proba >= t).astype(int)
        m = full_metrics(y, preds, best_proba)
        sweep_rows.append({"threshold": float(t), **m})
        print(f"t={t:.2f}  acc={m['accuracy']:.3f}  prec={m['precision']:.3f}  "
              f"recall={m['recall']:.3f}  spec={m['specificity']:.3f}  f1={m['f1']:.3f}  "
              f"tp={m['tp']} tn={m['tn']} fp={m['fp']} fn={m['fn']}")

    return oof_results, best_name, sweep_rows, len(df), float(y.mean())


if __name__ == "__main__":
    main()
