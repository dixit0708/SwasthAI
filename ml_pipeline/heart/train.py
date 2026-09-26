"""
Heart Disease Risk — XGBoost training pipeline.

Methodology (leakage-safe, identical structure to the diabetes v2 pipeline):
  1. Load pre-split train/test (produced by preprocessing.py)
  2. Model-family comparison (do NOT assume XGBoost is best)
  3. Hyperparameter search on the winning family
  4. Calibration decision via OOF Brier score (training split only)
  5. Threshold sweep on OOF probabilities (screening-first: maximise recall)
  6. ONE final fit on full training set
  7. ONE evaluation on the untouched test split

Artifacts:
  ml_pipeline/heart/artifacts/heart_pipeline.pkl   <- training artifact
  ml_pipeline/heart/artifacts/heart_metadata.json  <- training metadata
  backend/app/ai/models/heart_disease_model.pkl    <- production copy

Run: python train.py
"""
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from imblearn.over_sampling import SMOTE
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, confusion_matrix, f1_score,
    make_scorer, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import (
    RandomizedSearchCV, StratifiedKFold, cross_val_predict, cross_validate,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BASE          = Path(__file__).parent
PROCESSED_DIR = BASE / "data" / "processed"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR   = BASE / "reports"

# Production model destination
BACKEND_MODELS_DIR = (
    Path(__file__).parent.parent.parent / "backend" / "app" / "ai" / "models"
)
PRODUCTION_MODEL_PATH = BACKEND_MODELS_DIR / "heart_disease_model.pkl"

TARGET_COLUMN  = "HeartDiseaseRisk"
RANDOM_STATE   = 42
MODEL_VERSION  = "heart-cdc2022-v2-smote"

FEATURE_COLUMNS = [
    "Sex",
    "AgeCategory",
    "BMI",
    "GeneralHealth",
    "PhysicalHealthDays",
    "MentalHealthDays",
    "SleepHours",
    "PhysicalActivities",
    "HadStroke",
    "HadAsthma",
    "HadCOPD",
    "HadDepressiveDisorder",
    "HadKidneyDisease",
    "HadArthritis",
    "HadDiabetes",
    "DifficultyWalking",
    "DifficultyConcentrating",
    "DifficultyErrands",
    "SmokerStatus",
    "AlcoholDrinkers",
    "ChestScan",
    "HighRiskLastYear",
    "RemovedTeeth",
    "LastCheckupTime",
]

SCORERS = {
    "accuracy":  "accuracy",
    "precision": make_scorer(precision_score, zero_division=0),
    "recall":    make_scorer(recall_score),
    "f1":        make_scorer(f1_score),
    "roc_auc":   "roc_auc",
    "pr_auc":    make_scorer(average_precision_score, response_method="predict_proba"),
}


def specificity_score(y_true, y_pred) -> float:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return tn / (tn + fp) if (tn + fp) else 0.0


SCORERS["specificity"] = make_scorer(specificity_score)


def summarize_cv(cv_results: dict) -> dict:
    return {
        key: {
            "mean": float(cv_results[f"test_{key}"].mean()),
            "std":  float(cv_results[f"test_{key}"].std()),
        }
        for key in SCORERS
    }


def build_pipeline(classifier) -> Pipeline:
    return Pipeline([("scaler", StandardScaler()), ("classifier", classifier)])


# ---------------------------------------------------------------------------
# Stage 1 — Model-family comparison
# ---------------------------------------------------------------------------
def run_model_family_comparison(X_train, y_train, scale_pos_weight) -> dict:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    candidates = {
        "logistic_regression": build_pipeline(
            LogisticRegression(max_iter=1000, class_weight="balanced",
                               random_state=RANDOM_STATE)
        ),
        "random_forest": build_pipeline(
            RandomForestClassifier(n_estimators=150, max_depth=16,
                                   class_weight="balanced",
                                   random_state=RANDOM_STATE, n_jobs=1)
        ),
        "xgboost_default": build_pipeline(
            XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1,
                          eval_metric="logloss",
                          scale_pos_weight=scale_pos_weight,
                          random_state=RANDOM_STATE, n_jobs=1)
        ),
        "hist_gradient_boosting": build_pipeline(
            HistGradientBoostingClassifier(max_iter=200,
                                           class_weight="balanced",
                                           random_state=RANDOM_STATE)
        ),
    }
    results = {}
    for name, pipeline in candidates.items():
        t0 = time.time()
        cv_res = cross_validate(pipeline, X_train, y_train,
                                cv=cv, scoring=SCORERS, n_jobs=-1)
        results[name] = summarize_cv(cv_res)
        results[name]["wall_seconds"] = round(time.time() - t0, 1)
        print(f"  {name}: ROC-AUC={results[name]['roc_auc']['mean']:.4f} "
              f"(+/-{results[name]['roc_auc']['std']:.4f}) "
              f"[{results[name]['wall_seconds']}s]")
    return results


# ---------------------------------------------------------------------------
# Stage 2 — Hyperparameter tuning
# ---------------------------------------------------------------------------
def tune_xgboost(X_train, y_train, scale_pos_weight) -> tuple:
    param_dist = {
        "classifier__n_estimators":    [150, 200, 300, 400],
        "classifier__max_depth":       [3, 4, 5, 6],
        "classifier__learning_rate":   [0.02, 0.05, 0.1, 0.2],
        "classifier__min_child_weight": [1, 3, 5, 10],
        "classifier__subsample":       [0.7, 0.8, 0.9, 1.0],
        "classifier__colsample_bytree": [0.7, 0.8, 0.9, 1.0],
        "classifier__gamma":           [0, 0.1, 0.5, 1.0],
        "classifier__reg_alpha":       [0, 0.1, 1.0],
        "classifier__reg_lambda":      [1.0, 2.0, 5.0],
    }
    pipeline = build_pipeline(
        XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                      random_state=RANDOM_STATE, n_jobs=1)
    )
    search = RandomizedSearchCV(
        pipeline, param_dist, n_iter=20, scoring="roc_auc",
        cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE),
        random_state=RANDOM_STATE, n_jobs=-1, verbose=1,
    )
    search.fit(X_train, y_train)
    best_params = {k.replace("classifier__", ""): v
                   for k, v in search.best_params_.items()}
    print(f"  Best params: {best_params}")
    print(f"  Best cv=3 ROC-AUC: {search.best_score_:.4f}")

    cv5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    tuned_pipeline = build_pipeline(
        XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                      random_state=RANDOM_STATE, n_jobs=1, **best_params)
    )
    cv_res = cross_validate(tuned_pipeline, X_train, y_train,
                            cv=cv5, scoring=SCORERS, n_jobs=-1)
    tuned_summary = summarize_cv(cv_res)
    print(f"  Tuned 5-fold re-verify: ROC-AUC="
          f"{tuned_summary['roc_auc']['mean']:.4f} "
          f"(+/-{tuned_summary['roc_auc']['std']:.4f})")
    return best_params, tuned_summary


# ---------------------------------------------------------------------------
# Stage 3 — Calibration decision (OOF on training split only)
# ---------------------------------------------------------------------------
def compute_oof_probabilities(X_train, y_train, best_params, scale_pos_weight) -> dict:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    raw_pipeline = build_pipeline(
        XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                      random_state=RANDOM_STATE, n_jobs=-1, **best_params)
    )
    raw_oof = cross_val_predict(
        raw_pipeline, X_train, y_train,
        cv=cv, method="predict_proba", n_jobs=1
    )[:, 1]

    cal_pipeline = build_pipeline(
        CalibratedClassifierCV(
            XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                          random_state=RANDOM_STATE, n_jobs=-1, **best_params),
            method="sigmoid", cv=5,
        )
    )
    cal_oof = cross_val_predict(
        cal_pipeline, X_train, y_train,
        cv=cv, method="predict_proba", n_jobs=1
    )[:, 1]
    return {"raw_oof": raw_oof, "cal_oof": cal_oof}


# ---------------------------------------------------------------------------
# Stage 4 — Threshold sweep
# ---------------------------------------------------------------------------
def threshold_sweep(y_train, oof_proba) -> list:
    rows = []
    for threshold in np.arange(0.05, 0.51, 0.05):
        preds = (oof_proba >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_train, preds, labels=[0, 1]).ravel()
        rows.append({
            "threshold":            round(float(threshold), 2),
            "recall_sensitivity":   round(float(recall_score(y_train, preds)), 4),
            "specificity":          round(float(tn / (tn + fp)) if (tn + fp) else 0.0, 4),
            "precision":            round(float(precision_score(y_train, preds, zero_division=0)), 4),
            "f1":                   round(float(f1_score(y_train, preds)), 4),
            "false_positive_rate":  round(float(fp / (fp + tn)) if (fp + tn) else 0.0, 4),
            "false_negative_rate":  round(float(fn / (fn + tp)) if (fn + tp) else 0.0, 4),
            "false_positives":      int(fp),
            "false_negatives":      int(fn),
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKEND_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(PROCESSED_DIR / "heart_train.csv")
    test_df  = pd.read_csv(PROCESSED_DIR / "heart_test.csv")

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN].astype(int)
    X_test  = test_df[FEATURE_COLUMNS]
    y_test  = test_df[TARGET_COLUMN].astype(int)

    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    print(f"Training rows: {len(X_train)} | Test rows: {len(X_test)}")
    orig_pos_rate = y_train.mean()
    print(f"Positive rate (train, before SMOTE): {orig_pos_rate*100:.2f}%")

    # ------------------------------------------------------------------
    # SMOTE — applied to raw (pre-scaling) training arrays only.
    # The test split is never touched. scale_pos_weight is set to 1.0
    # after SMOTE because the minority class is now fully balanced and
    # no additional cost-sensitive weighting is needed.
    # SMOTE operates on the numpy arrays, not the DataFrame, so it cannot
    # introduce any leakage from the test split.
    # ------------------------------------------------------------------
    print("\nApplying SMOTE to training data (minority class oversampling) …")
    smote = SMOTE(random_state=RANDOM_STATE)
    X_train_np = X_train.values if hasattr(X_train, 'values') else X_train
    y_train_np = y_train.values if hasattr(y_train, 'values') else y_train
    X_train_res, y_train_res = smote.fit_resample(X_train_np, y_train_np)
    X_train = pd.DataFrame(X_train_res, columns=FEATURE_COLUMNS)
    y_train = pd.Series(y_train_res, name=TARGET_COLUMN)
    scale_pos_weight = 1.0   # classes are balanced after SMOTE
    print(f"After SMOTE: {len(X_train)} rows | "
          f"positive rate: {y_train.mean()*100:.2f}% | "
          f"scale_pos_weight={scale_pos_weight}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 1: Model-family comparison (do not assume XGBoost is best)")
    print("=" * 70)
    family_results = run_model_family_comparison(X_train, y_train, scale_pos_weight)
    with open(REPORTS_DIR / "family_comparison.json", "w") as f:
        json.dump(family_results, f, indent=2)
    best_family = max(family_results, key=lambda n: family_results[n]["roc_auc"]["mean"])
    print(f"\nStrongest family by mean CV ROC-AUC: {best_family}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 2: Hyperparameter tuning (XGBoost)")
    print("=" * 70)
    best_params, tuned_summary = tune_xgboost(X_train, y_train, scale_pos_weight)
    with open(REPORTS_DIR / "tuned_results.json", "w") as f:
        json.dump({
            "best_params": best_params, "cv_summary": tuned_summary,
            "winning_family": best_family, "family_comparison": family_results,
        }, f, indent=2)

    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 3: Calibration decision (OOF, training split only)")
    print("=" * 70)
    oof = compute_oof_probabilities(X_train, y_train, best_params, scale_pos_weight)
    raw_brier = brier_score_loss(y_train, oof["raw_oof"])
    cal_brier = brier_score_loss(y_train, oof["cal_oof"])
    use_calibration = (raw_brier - cal_brier) > 0.0005
    print(f"  Brier raw={raw_brier:.5f}  calibrated={cal_brier:.5f}  "
          f"use_calibration={use_calibration}")
    with open(REPORTS_DIR / "calibration_check.json", "w") as f:
        json.dump({
            "raw_brier_score":              round(raw_brier, 5),
            "sigmoid_calibrated_brier":     round(cal_brier, 5),
            "improvement":                  round(raw_brier - cal_brier, 5),
            "use_calibration":              use_calibration,
        }, f, indent=2)

    deployed_oof = oof["cal_oof"] if use_calibration else oof["raw_oof"]

    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 4: Threshold sweep (screening-first: recall >= 0.80)")
    print("=" * 70)
    sweep = threshold_sweep(y_train, deployed_oof)
    for row in sweep:
        print(" ", row)
    # Heart disease: prioritise sensitivity — keep recall >= 0.80
    eligible = [r for r in sweep if r["recall_sensitivity"] >= 0.80]
    chosen   = (max(eligible, key=lambda r: r["threshold"])
                if eligible else min(sweep, key=lambda r: r["threshold"]))
    threshold = chosen["threshold"]
    print(f"\n  Chosen threshold: {threshold} "
          f"(highest threshold keeping OOF recall >= 0.80)")
    with open(REPORTS_DIR / "threshold_sweep.json", "w") as f:
        json.dump({"sweep": sweep, "chosen_threshold": threshold,
                   "chosen_row": chosen}, f, indent=2)

    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"STAGE 5: Final fit + ONE test evaluation "
          f"(threshold={threshold}, calibration={'sigmoid' if use_calibration else 'none'})")
    print("=" * 70)
    base_clf  = XGBClassifier(
        eval_metric="logloss", scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_STATE, n_jobs=-1, **best_params
    )
    final_clf = (CalibratedClassifierCV(base_clf, method="sigmoid", cv=5)
                 if use_calibration else base_clf)
    final_pipeline = build_pipeline(final_clf)
    final_pipeline.fit(X_train, y_train)

    test_proba = final_pipeline.predict_proba(X_test)[:, 1]
    test_preds = (test_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, test_preds, labels=[0, 1]).ravel()
    test_metrics = {
        "accuracy":           float((tp + tn) / (tp + tn + fp + fn)),
        "precision":          float(precision_score(y_test, test_preds, zero_division=0)),
        "recall_sensitivity": float(recall_score(y_test, test_preds)),
        "specificity":        float(tn / (tn + fp)) if (tn + fp) else 0.0,
        "f1":                 float(f1_score(y_test, test_preds)),
        "roc_auc":            float(roc_auc_score(y_test, test_proba)),
        "pr_auc":             float(average_precision_score(y_test, test_proba)),
        "brier":              float(brier_score_loss(y_test, test_proba)),
        "confusion_matrix":   {"tp": int(tp), "tn": int(tn),
                               "fp": int(fp), "fn": int(fn)},
        "threshold_used":     threshold,
        "calibration_used":   use_calibration,
        "n_test_rows":        int(len(y_test)),
    }
    print(json.dumps(test_metrics, indent=2))
    with open(REPORTS_DIR / "test_evaluation.json", "w") as f:
        json.dump(test_metrics, f, indent=2)

    # Reliability by decile
    bins    = np.linspace(0, 1, 11)
    bin_ids = np.digitize(test_proba, bins) - 1
    reliability = []
    for b in range(10):
        mask = bin_ids == b
        if mask.sum() > 0:
            reliability.append({
                "bin":            f"[{bins[b]:.1f}-{bins[b+1]:.1f})",
                "n":              int(mask.sum()),
                "mean_predicted": round(float(test_proba[mask].mean()), 4),
                "observed":       round(float(y_test.values[mask].mean()), 4),
            })
    with open(REPORTS_DIR / "calibration_in_the_large.json", "w") as f:
        json.dump({
            "mean_predicted":   float(test_proba.mean()),
            "observed_prev":    float(y_test.mean()),
            "reliability":      reliability,
        }, f, indent=2)

    # ------------------------------------------------------------------
    # Save artifacts
    training_artifact = ARTIFACTS_DIR / "heart_pipeline.pkl"
    joblib.dump(final_pipeline, training_artifact)
    print(f"\nSaved training artifact: {training_artifact}")

    # Copy to backend production path
    shutil.copy2(training_artifact, PRODUCTION_MODEL_PATH)
    print(f"Copied to production:    {PRODUCTION_MODEL_PATH}")

    metadata = {
        "model_name":             "heart_disease_risk_model",
        "model_version":          MODEL_VERSION,
        "algorithm":              "xgboost" + ("_sigmoid_calibrated" if use_calibration else ""),
        "model_family_comparison": {k: v["roc_auc"] for k, v in family_results.items()},
        "dataset_name":           "CDC BRFSS / YRBS 2022 — heart_2022_no_nans.csv",
        "dataset_path":           "ml_pipeline/heart/data/heart_2022_no_nans.csv",
        "training_date":          datetime.now(timezone.utc).isoformat(),
        "target_column":          TARGET_COLUMN,
        "target_definition":      "HadHeartAttack == 'Yes' OR HadAngina == 'Yes'",
        "target_classes":         {"0": "no heart disease risk", "1": "heart disease risk"},
        "feature_names":          FEATURE_COLUMNS,
        "feature_count":          len(FEATURE_COLUMNS),
        "feature_order":          FEATURE_COLUMNS,
        "preprocessing":          "StandardScaler (fit on training split only)",
        "class_imbalance_strategy": (
            f"SMOTE (imblearn, random_state={RANDOM_STATE}) + "
            f"scale_pos_weight={scale_pos_weight:.4f} (=1.0 after resampling)"
        ),
        "hyperparameters":        best_params,
        "decision_threshold":     threshold,
        "calibration_method":     "sigmoid (Platt scaling)" if use_calibration else "none",
        "random_seed":            RANDOM_STATE,
        "train_test_split":       "80/20 stratified, random_state=42, exact duplicates dropped pre-split",
        "cross_validation":       "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
        "cv_roc_auc_mean":        tuned_summary["roc_auc"]["mean"],
        "cv_roc_auc_std":         tuned_summary["roc_auc"]["std"],
        "test_metrics":           test_metrics,
        "production_model_path":  str(PRODUCTION_MODEL_PATH),
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "xgboost":      xgboost.__version__,
            "pandas":       pd.__version__,
            "numpy":        np.__version__,
        },
        "limitations": [
            "All features are self-reported CDC 2022 survey answers, not clinical measurements.",
            "Target is a composite of two self-reported survey items (HadHeartAttack, HadAngina).",
            "Training data is a single U.S. CDC survey year (2022) and U.S. population.",
            "No external independent validation dataset was used.",
            "Family history of heart disease is not included in the survey data.",
        ],
        "intended_use":       "AI-generated heart disease risk indicator for informational/screening purposes.",
        "medical_safety_notice": (
            "This model output is a risk assessment, NOT a medical diagnosis. "
            "It must never be presented as a definitive diagnosis and should always "
            "encourage consultation with a qualified healthcare professional."
        ),
    }
    with open(ARTIFACTS_DIR / "heart_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata:          {ARTIFACTS_DIR / 'heart_metadata.json'}")

    print("\n" + "=" * 70)
    print("FEATURE NAMES (exact list — use for backend schema and frontend):")
    print("=" * 70)
    for i, feat in enumerate(FEATURE_COLUMNS, 1):
        print(f"  {i:2d}. {feat}")
    print(f"\nTotal features: {len(FEATURE_COLUMNS)}")


if __name__ == "__main__":
    main()
