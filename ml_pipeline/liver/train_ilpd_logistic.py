"""
SwasthAI — Liver Disease Risk Model (Lab-Based / ILPD) — Logistic Regression
candidate, training and finalization.
=============================================================================
Trains and finalizes a Logistic Regression production CANDIDATE on the
canonical UCI ILPD dataset (583 rows, verified authentic and leakage-free
in ml_pipeline/liver/reports/ilpd_model_investigation.md — see that report
for the full provenance and integrity investigation this script builds on).

NOT wired into the backend or frontend by this script. NOT a replacement
for the currently-shipped liver-nhanes-v1 model (ml_pipeline/liver/
train_nhanes.py, untouched by this script). Produces a standalone
candidate artifact only:
  - artifacts/liver_ilpd_logistic_v1.pkl
  - artifacts/liver_ilpd_logistic_metadata_v1.json

Logistic Regression is used because the prior leakage-safe 5-fold
investigation found it outperforming Random Forest and XGBoost by
out-of-fold ROC-AUC (0.745 vs 0.717 vs 0.691) — the opposite pattern from
the rejected liver_lpd dataset, where tree models suspiciously
outperformed Logistic Regression. No hyperparameter search is performed
here (kept simple/reproducible per the task's own instruction); the model
uses sensible, documented defaults with class_weight="balanced" for the
71%/29% imbalance, matching the convention used by every other model in
this project.

Methodology:
  1. Load + verify the raw file (rows/columns/features/target/class
     balance/duplicates/missing values) — printed, not assumed.
  2. Drop exact duplicates before anything else touches the data.
  3. Build a single sklearn Pipeline (median imputer + scaler + one-hot
     encoder -> Logistic Regression) so preprocessing can never differ
     between training and inference.
  4. Stratified 5-fold CV: for each fold, fit a fresh clone of the
     pipeline on that fold's training portion only, predict on the held-out
     fold. Collect per-fold metrics (mean/std) AND out-of-fold predictions
     for every row (each row's prediction always comes from a fold that
     never trained on it).
  5. Sweep thresholds 0.10-0.90 (step 0.01) on the out-of-fold
     probabilities; select a sensitivity-first threshold (lowest threshold
     still clearing ~80% recall — the same convention used by
     liver-nhanes-v1, diabetes-brfss-v2, and diabetes-pima-v1), not
     whichever threshold maximizes accuracy.
  6. Refit the final pipeline on the FULL cleaned dataset (no separate
     held-out test set is carved out here — CV out-of-fold performance is
     already an unbiased estimate on 570 rows; holding out an additional
     test slice would only shrink an already-small dataset further without
     added rigor, since no threshold or model choice touches held-out data
     after this point).
  7. Save the artifact + metadata, compute SHA-256 checksums.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

BASE = Path(__file__).parent
RAW_PATH = BASE / "data" / "raw" / "ilpd_uci_original.csv"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR = BASE / "reports"

RAW_COLS = [
    "age_years", "gender", "total_bilirubin_mg_dl", "direct_bilirubin_mg_dl",
    "alkaline_phosphatase_u_l", "alanine_aminotransferase_u_l",
    "aspartate_aminotransferase_u_l", "total_proteins_g_dl", "albumin_g_dl",
    "albumin_globulin_ratio", "selector_raw",
]
NUMERIC_FEATURES = [c for c in RAW_COLS[:-1] if c != "gender"]
CATEGORICAL_FEATURES = ["gender"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "liver_disease_status"
RANDOM_STATE = 42
N_FOLDS = 5
TARGET_RECALL = 0.80

# "penalty" is deliberately left out of the constructor kwargs below: as of
# scikit-learn 1.8, passing penalty="l2" explicitly triggers a
# FutureWarning (the parameter is being replaced by l1_ratio in 1.10). l2
# is already scikit-learn's default regularization, so omitting it changes
# nothing about the fitted model — it's recorded here purely for the
# metadata/documentation requirement below.
LR_HYPERPARAMETERS = {
    "solver": "lbfgs",
    "penalty": "l2 (scikit-learn default; not passed explicitly to avoid a 1.8+ FutureWarning)",
    "C": 1.0,
    "class_weight": "balanced",
    "max_iter": 1000,
    "random_state": RANDOM_STATE,
}


def build_pipeline():
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
    classifier = LogisticRegression(
        solver="lbfgs", C=1.0, class_weight="balanced",
        max_iter=1000, random_state=RANDOM_STATE,
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


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. Verify dataset (printed, not assumed) ---
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"Canonical ILPD file not found at {RAW_PATH}. Stopping rather than "
            f"substituting another dataset — see task instructions."
        )
    df = pd.read_csv(RAW_PATH, header=None, names=RAW_COLS)
    print(f"Dataset path: {RAW_PATH}")
    print(f"Raw rows: {len(df)}")
    print(f"Raw columns: {len(df.columns)} -> {list(df.columns)}")

    n_dupes = df.duplicated().sum()
    print(f"Duplicate rows: {n_dupes}")
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Rows after duplicate removal: {len(df)}")

    df[TARGET_COLUMN] = df["selector_raw"].map({1: 1, 2: 0})
    df = df.drop(columns=["selector_raw"])
    n_missing_total = int(df[FEATURE_COLUMNS].isna().sum().sum())
    print(f"Missing values (total, across all feature columns): {n_missing_total}")
    print(f"Missing values per column:\n{df[FEATURE_COLUMNS].isna().sum().to_string()}")
    print(f"Final usable row count: {len(df)}")

    print(f"\nFeature names ({len(FEATURE_COLUMNS)}): {FEATURE_COLUMNS}")
    print(f"Target column: {TARGET_COLUMN} (from raw 'Selector': 1=liver patient -> 1, 2=not -> 0)")
    print(f"\nClass distribution:\n{df[TARGET_COLUMN].value_counts().to_string()}")
    print(f"Positive rate: {df[TARGET_COLUMN].mean():.4f}")

    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].astype(int).values

    # --- 2/3/4. Stratified 5-fold CV with a fresh pipeline clone per fold ---
    print(f"\n--- Stratified {N_FOLDS}-fold CV (Logistic Regression, out-of-fold predictions) ---")
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    oof_proba = np.zeros(len(y), dtype=float)
    fold_metrics = []
    base_pipeline = build_pipeline()

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y), start=1):
        pipeline = clone(base_pipeline)
        pipeline.fit(X[train_idx], y[train_idx])
        fold_proba = pipeline.predict_proba(X[val_idx])[:, 1]
        oof_proba[val_idx] = fold_proba

        fold_preds = (fold_proba >= 0.5).astype(int)
        m = full_metrics(y[val_idx], fold_preds, fold_proba)
        fold_metrics.append(m)
        print(f"Fold {fold_idx}: ROC-AUC={m['roc_auc']:.4f}  PR-AUC={m['pr_auc']:.4f}  "
              f"Acc={m['accuracy']:.4f}  Prec={m['precision']:.4f}  Recall={m['recall']:.4f}  "
              f"Spec={m['specificity']:.4f}  F1={m['f1']:.4f}")

    metric_keys = ["roc_auc", "pr_auc", "accuracy", "precision", "recall", "specificity", "f1"]
    cv_mean = {k: float(np.mean([m[k] for m in fold_metrics])) for k in metric_keys}
    cv_std = {k: float(np.std([m[k] for m in fold_metrics])) for k in metric_keys}
    print("\nCV mean +/- std across folds:")
    for k in metric_keys:
        print(f"  {k}: {cv_mean[k]:.4f} +/- {cv_std[k]:.4f}")

    # Aggregate out-of-fold metrics at threshold=0.5, for reference only —
    # the actual production threshold is chosen below from the sweep.
    oof_preds_default = (oof_proba >= 0.5).astype(int)
    oof_metrics_default = full_metrics(y, oof_preds_default, oof_proba)
    print(f"\nAggregate out-of-fold metrics at threshold=0.5 (reference only):")
    print(json.dumps(oof_metrics_default, indent=2))

    # --- 5. Threshold sweep on out-of-fold probabilities ---
    print(f"\n--- Threshold sweep (0.10-0.90, step 0.01) on out-of-fold probabilities ---")
    thresholds = np.round(np.arange(0.10, 0.901, 0.01), 2)
    sweep = []
    for t in thresholds:
        preds = (oof_proba >= t).astype(int)
        m = full_metrics(y, preds, oof_proba)
        sweep.append({"threshold": float(t), **m})

    # Sensitivity-first threshold selection: lowest threshold still clearing
    # TARGET_RECALL — same convention as liver-nhanes-v1 / diabetes-brfss-v2
    # / diabetes-pima-v1. Never chosen by maximizing accuracy.
    selected_threshold = float(thresholds[0])
    for row in sweep:
        if row["recall"] >= TARGET_RECALL:
            selected_threshold = row["threshold"]
        else:
            break
    selected_row = next(r for r in sweep if r["threshold"] == selected_threshold)
    print(f"\nSelected threshold (lowest clearing {TARGET_RECALL:.0%} recall, sensitivity-first "
          f"screening convention): {selected_threshold:.2f}")
    print(json.dumps(selected_row, indent=2))

    # For transparency only — NOT used as the production threshold.
    acc_max_row = max(sweep, key=lambda r: r["accuracy"])
    print(f"\n(Reference only, NOT used) accuracy-maximizing threshold: "
          f"{acc_max_row['threshold']:.2f} -> accuracy {acc_max_row['accuracy']:.4f}, "
          f"recall {acc_max_row['recall']:.4f} — rejected as the production threshold because "
          f"a screening tool that misses this many true cases would not be defensible; see report.")

    # --- 6. Refit final pipeline on the FULL cleaned dataset ---
    final_pipeline = build_pipeline()
    final_pipeline.fit(X, y)

    # --- 7. Save artifact + metadata ---
    pipeline_path = ARTIFACTS_DIR / "liver_ilpd_logistic_v1.pkl"
    import joblib
    joblib.dump(final_pipeline, pipeline_path)

    metadata = {
        "model_name": "liver_risk_model_ilpd_logistic",
        "model_version": "liver-ilpd-logistic-v1",
        "model_status": "candidate — not integrated into SwasthAI backend/frontend",
        "description": "Liver-disease risk/assessment model for informational and educational "
                        "purposes only. Not a medical diagnostic device, not a doctor replacement, "
                        "and not claimed to be clinically proven or 100% accurate.",
        "dataset_name": "ILPD (Indian Liver Patient Dataset)",
        "dataset_source": "UCI Machine Learning Repository, dataset id 225. "
                           "Ramana, B. & Venkateswarlu, N. (2022). https://doi.org/10.24432/C5D02C. "
                           "License: CC BY 4.0.",
        "dataset_rows_original": int(len(df) + n_dupes),
        "dataset_rows_after_duplicate_removal": int(len(df)),
        "duplicate_rows_removed": int(n_dupes),
        "missing_values_total": n_missing_total,
        "feature_names": FEATURE_COLUMNS,
        "target_name": TARGET_COLUMN,
        "target_definition": "Raw 'Selector' column: 1 = liver patient -> mapped to 1, "
                              "2 = not a liver patient -> mapped to 0",
        "preprocessing_steps": [
            "Drop exact duplicate rows (before any split/fold)",
            "ColumnTransformer: numeric features -> SimpleImputer(strategy='median') "
            "-> StandardScaler; gender -> OneHotEncoder(drop='first', handle_unknown='ignore')",
            "All imputer/scaler/encoder statistics fitted only on each fold's training "
            "portion during cross-validation; final pipeline fits once on the full "
            "cleaned dataset for the shipped artifact",
        ],
        "model_type": "LogisticRegression",
        "hyperparameters": LR_HYPERPARAMETERS,
        "cross_validation_method": "StratifiedKFold, out-of-fold predictions",
        "cv_folds": N_FOLDS,
        "cv_metrics_mean": cv_mean,
        "cv_metrics_std": cv_std,
        "out_of_fold_aggregate_metrics_at_0.5": oof_metrics_default,
        "roc_auc": cv_mean["roc_auc"],
        "pr_auc": cv_mean["pr_auc"],
        "accuracy": cv_mean["accuracy"],
        "precision": cv_mean["precision"],
        "recall": cv_mean["recall"],
        "specificity": cv_mean["specificity"],
        "f1": cv_mean["f1"],
        "selected_threshold": selected_threshold,
        "selected_threshold_metrics": selected_row,
        "threshold_selection_rationale": f"Lowest threshold (from a 0.10-0.90 sweep, step 0.01, on "
            f"out-of-fold probabilities) that still clears {TARGET_RECALL:.0%} recall — a "
            f"sensitivity-first choice appropriate for a screening tool, matching the convention "
            f"already used by liver-nhanes-v1, diabetes-brfss-v2, and diabetes-pima-v1 in this "
            f"project. NOT chosen to maximize accuracy (the accuracy-maximizing threshold in this "
            f"sweep was {acc_max_row['threshold']:.2f}, with recall only {acc_max_row['recall']:.4f} "
            f"— rejected as too insensitive for a screening use case).",
        "threshold_sweep_range": {"min": 0.10, "max": 0.90, "step": 0.01},
        "training_date": datetime.now(timezone.utc).isoformat(),
        "random_state": RANDOM_STATE,
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "limitations": [
            "Small dataset (570 usable rows after cleaning) — confidence intervals on these "
            "metrics are wide; a single-digit change in fold composition can shift results "
            "noticeably.",
            "Single-region population (Northeast Andhra Pradesh, India; 441 male / 142 female "
            "in the raw file) — not necessarily generalizable to other populations.",
            "No external clinical validation.",
            "Not a diagnosis: outputs an AI-generated risk indicator only, per AGENTS.md Section 11.",
        ],
        "not_integrated": True,
        "excludes_liver_lpd_dataset": True,
        "independent_of": ["liver-nhanes-v1 (ml_pipeline/liver/train_nhanes.py, untouched)"],
    }

    metadata_path = ARTIFACTS_DIR / "liver_ilpd_logistic_metadata_v1.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    pipeline_sha256 = sha256_of(pipeline_path)
    metadata_sha256 = sha256_of(metadata_path)

    print(f"\nSaved {pipeline_path}")
    print(f"  SHA-256: {pipeline_sha256}")
    print(f"Saved {metadata_path}")
    print(f"  SHA-256: {metadata_sha256}")

    return {
        "df": df, "sweep": sweep, "cv_mean": cv_mean, "cv_std": cv_std,
        "selected_threshold": selected_threshold, "selected_row": selected_row,
        "acc_max_row": acc_max_row, "n_dupes": n_dupes, "n_missing_total": n_missing_total,
        "pipeline_path": pipeline_path, "metadata_path": metadata_path,
        "pipeline_sha256": pipeline_sha256, "metadata_sha256": metadata_sha256,
        "oof_metrics_default": oof_metrics_default,
    }


if __name__ == "__main__":
    main()
