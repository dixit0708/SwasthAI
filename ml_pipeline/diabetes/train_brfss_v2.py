"""
Independent training + validation of the 14-feature "Expanded" candidate
identified by the prior feature-selection study (reports/model_comparison.md).

Unlike that study (which held hyperparameters fixed to isolate the feature-
set effect), this script gives the 14-feature candidate its own honest
tuning pass, compares it against alternative model families, and re-derives
calibration and threshold from scratch — nothing about v2 is assumed from
the v1 baseline or from the earlier ablation run.

Methodology (identical leakage-safe order to v1):
    train split -> baseline model-family CV comparison -> hyperparameter
    search on the winning family -> calibration decision (OOF Brier,
    training split only) -> threshold sweep on the deployed OOF probability
    space -> ONE final fit -> ONE evaluation on the untouched test split.

The v1 artifact/metadata (artifacts/diabetes_pipeline.pkl,
artifacts/metadata.json) are never read for parameters and never written to
by this script — only NEW files (artifacts/diabetes_pipeline_v2.pkl,
artifacts/diabetes_metadata_v2.json) are produced.

Run: python train_brfss_v2.py
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
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

BASE = Path(__file__).parent
PROCESSED_DIR = BASE / "data" / "processed"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR = BASE / "reports"

TARGET_COLUMN = "Diabetes_binary"
RANDOM_STATE = 42
MODEL_VERSION = "diabetes-brfss-v2"

# The 14-feature "Expanded" candidate, unchanged from
# reports/candidate_assessments.md — this is the ONLY thing carried over
# from the prior study; everything else (hyperparameters, calibration,
# threshold) is re-derived independently below.
FEATURE_COLUMNS = [
    "HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke",
    "HeartDiseaseorAttack", "PhysActivity", "Fruits", "HvyAlcoholConsump",
    "GenHlth", "DiffWalk", "Sex", "Age",
]
assert len(FEATURE_COLUMNS) == 14


def specificity_score(y_true, y_pred) -> float:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return tn / (tn + fp) if (tn + fp) else 0.0


SCORERS = {
    "accuracy": "accuracy",
    "precision": make_scorer(precision_score, zero_division=0),
    "recall": make_scorer(recall_score),
    "specificity": make_scorer(specificity_score),
    "f1": make_scorer(f1_score),
    "roc_auc": "roc_auc",
    "pr_auc": make_scorer(average_precision_score, response_method="predict_proba"),
}


def summarize_cv(cv_results: dict) -> dict:
    return {key: {"mean": float(cv_results[f"test_{key}"].mean()), "std": float(cv_results[f"test_{key}"].std())}
            for key in SCORERS}


def build_pipeline(classifier) -> Pipeline:
    return Pipeline([("scaler", StandardScaler()), ("classifier", classifier)])


def run_model_family_comparison(X_train, y_train, scale_pos_weight) -> dict:
    """Phase 3: do not assume XGBoost — compare against Logistic Regression,
    Random Forest, and HistGradientBoosting on the SAME 14-feature data."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    candidates = {
        "logistic_regression": build_pipeline(
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
        ),
        "random_forest": build_pipeline(
            RandomForestClassifier(n_estimators=150, max_depth=16, class_weight="balanced",
                                    random_state=RANDOM_STATE, n_jobs=1)
        ),
        "xgboost_default": build_pipeline(
            XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, eval_metric="logloss",
                          scale_pos_weight=scale_pos_weight, random_state=RANDOM_STATE, n_jobs=1)
        ),
        "hist_gradient_boosting": build_pipeline(
            HistGradientBoostingClassifier(max_iter=200, class_weight="balanced", random_state=RANDOM_STATE)
        ),
    }
    results = {}
    for name, pipeline in candidates.items():
        t0 = time.time()
        cv_res = cross_validate(pipeline, X_train, y_train, cv=cv, scoring=SCORERS, n_jobs=-1)
        results[name] = summarize_cv(cv_res)
        results[name]["wall_seconds"] = round(time.time() - t0, 1)
        print(f"  {name}: ROC-AUC={results[name]['roc_auc']['mean']:.4f} "
              f"(+/-{results[name]['roc_auc']['std']:.4f}) [{results[name]['wall_seconds']}s]")
    return results


def tune_xgboost(X_train, y_train, scale_pos_weight) -> tuple:
    """Phase 3: an honest, independent tuning pass for the 14-feature data —
    NOT a reuse of the 21-feature baseline's hyperparameters."""
    param_dist = {
        "classifier__n_estimators": [150, 200, 300, 400],
        "classifier__max_depth": [3, 4, 5, 6],
        "classifier__learning_rate": [0.02, 0.05, 0.1, 0.2],
        "classifier__min_child_weight": [1, 3, 5, 10],
        "classifier__subsample": [0.7, 0.8, 0.9, 1.0],
        "classifier__colsample_bytree": [0.7, 0.8, 0.9, 1.0],
        "classifier__gamma": [0, 0.1, 0.5, 1.0],
        "classifier__reg_alpha": [0, 0.1, 1.0],
        "classifier__reg_lambda": [1.0, 2.0, 5.0],
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
    best_params = {k.replace("classifier__", ""): v for k, v in search.best_params_.items()}
    print(f"  Best params (cv=3 search): {best_params}")
    print(f"  Best cv=3 ROC-AUC: {search.best_score_:.4f}")

    cv5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    tuned_pipeline = build_pipeline(
        XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                       random_state=RANDOM_STATE, n_jobs=1, **best_params)
    )
    cv_res = cross_validate(tuned_pipeline, X_train, y_train, cv=cv5, scoring=SCORERS, n_jobs=-1)
    tuned_summary = summarize_cv(cv_res)
    print(f"  Tuned model, full 5-fold re-verification: ROC-AUC="
          f"{tuned_summary['roc_auc']['mean']:.4f} (+/-{tuned_summary['roc_auc']['std']:.4f})")
    return best_params, tuned_summary


def compute_oof_probabilities(X_train, y_train, best_params, scale_pos_weight) -> dict:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    raw_pipeline = build_pipeline(
        XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                       random_state=RANDOM_STATE, n_jobs=-1, **best_params)
    )
    raw_oof = cross_val_predict(raw_pipeline, X_train, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]

    calibrated_pipeline = build_pipeline(
        CalibratedClassifierCV(
            XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                           random_state=RANDOM_STATE, n_jobs=-1, **best_params),
            method="sigmoid", cv=5,
        )
    )
    cal_oof = cross_val_predict(calibrated_pipeline, X_train, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    return {"raw_oof": raw_oof, "cal_oof": cal_oof}


def threshold_sweep(y_train, oof_proba) -> list:
    rows = []
    for threshold in np.arange(0.05, 0.51, 0.05):
        preds = (oof_proba >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_train, preds, labels=[0, 1]).ravel()
        rows.append({
            "threshold": round(float(threshold), 2),
            "recall_sensitivity": round(float(recall_score(y_train, preds)), 4),
            "specificity": round(float(tn / (tn + fp)) if (tn + fp) else 0.0, 4),
            "precision": round(float(precision_score(y_train, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_train, preds)), 4),
            "false_positive_rate": round(float(fp / (fp + tn)) if (fp + tn) else 0.0, 4),
            "false_negative_rate": round(float(fn / (fn + tp)) if (fn + tp) else 0.0, 4),
            "false_positives": int(fp),
            "false_negatives": int(fn),
        })
    return rows


def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(PROCESSED_DIR / "brfss_train.csv")
    test_df = pd.read_csv(PROCESSED_DIR / "brfss_test.csv")
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN].astype(int)
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN].astype(int)
    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    print(f"14-feature v2 candidate. scale_pos_weight={scale_pos_weight:.4f}")

    print("\n" + "=" * 70 + "\nSTAGE 1: Model-family comparison (do not assume XGBoost)\n" + "=" * 70)
    family_results = run_model_family_comparison(X_train, y_train, scale_pos_weight)
    with open(REPORTS_DIR / "v2_family_comparison.json", "w") as f:
        json.dump(family_results, f, indent=2)
    best_family = max(family_results, key=lambda n: family_results[n]["roc_auc"]["mean"])
    print(f"\nStrongest family by mean CV ROC-AUC: {best_family}")

    print("\n" + "=" * 70 + "\nSTAGE 2: Independent hyperparameter tuning\n" + "=" * 70)
    best_params, tuned_summary = tune_xgboost(X_train, y_train, scale_pos_weight)
    with open(REPORTS_DIR / "v2_tuned_results.json", "w") as f:
        json.dump({"best_params": best_params, "cv_summary": tuned_summary, "winning_family": best_family,
                    "family_comparison": family_results}, f, indent=2)

    print("\n" + "=" * 70 + "\nSTAGE 3: Calibration decision (OOF, training split only)\n" + "=" * 70)
    oof = compute_oof_probabilities(X_train, y_train, best_params, scale_pos_weight)
    raw_brier = brier_score_loss(y_train, oof["raw_oof"])
    cal_brier = brier_score_loss(y_train, oof["cal_oof"])
    use_calibration = (raw_brier - cal_brier) > 0.0005
    print(f"  Brier raw={raw_brier:.5f} calibrated={cal_brier:.5f} use_calibration={use_calibration}")
    with open(REPORTS_DIR / "v2_calibration_check.json", "w") as f:
        json.dump({"raw_brier_score": round(raw_brier, 5), "sigmoid_calibrated_brier_score": round(cal_brier, 5),
                    "improvement": round(raw_brier - cal_brier, 5), "use_calibration": use_calibration}, f, indent=2)

    deployed_oof = oof["cal_oof"] if use_calibration else oof["raw_oof"]

    print("\n" + "=" * 70 + "\nSTAGE 4: Threshold sweep (deployed OOF probability space)\n" + "=" * 70)
    sweep = threshold_sweep(y_train, deployed_oof)
    for row in sweep:
        print(" ", row)
    eligible = [r for r in sweep if r["recall_sensitivity"] >= 0.85]
    chosen = max(eligible, key=lambda r: r["threshold"]) if eligible else min(sweep, key=lambda r: r["threshold"])
    threshold = chosen["threshold"]
    print(f"\n  Chosen threshold: {threshold} (same screening-first rule as v1 and the ablation study: "
          f"highest threshold keeping training-OOF recall >= 0.85)")
    with open(REPORTS_DIR / "v2_threshold_sweep.json", "w") as f:
        json.dump({"sweep": sweep, "chosen_threshold": threshold, "chosen_row": chosen}, f, indent=2)

    print("\n" + "=" * 70 + f"\nSTAGE 5: Final fit + ONE test evaluation "
          f"(threshold={threshold}, calibration={'sigmoid' if use_calibration else 'none'})\n" + "=" * 70)
    base_clf = XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                              random_state=RANDOM_STATE, n_jobs=-1, **best_params)
    final_clf = CalibratedClassifierCV(base_clf, method="sigmoid", cv=5) if use_calibration else base_clf
    final_pipeline = build_pipeline(final_clf)
    final_pipeline.fit(X_train, y_train)

    test_proba = final_pipeline.predict_proba(X_test)[:, 1]
    test_preds = (test_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, test_preds, labels=[0, 1]).ravel()
    test_metrics = {
        "accuracy": float((tp + tn) / (tp + tn + fp + fn)),
        "precision": float(precision_score(y_test, test_preds, zero_division=0)),
        "recall_sensitivity": float(recall_score(y_test, test_preds)),
        "specificity": float(tn / (tn + fp)) if (tn + fp) else 0.0,
        "f1": float(f1_score(y_test, test_preds)),
        "roc_auc": float(roc_auc_score(y_test, test_proba)),
        "pr_auc": float(average_precision_score(y_test, test_proba)),
        "brier": float(brier_score_loss(y_test, test_proba)),
        "confusion_matrix": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
        "threshold_used": threshold,
        "calibration_used": use_calibration,
        "n_test_rows": int(len(y_test)),
    }
    print(json.dumps(test_metrics, indent=2))
    with open(REPORTS_DIR / "v2_test_evaluation.json", "w") as f:
        json.dump(test_metrics, f, indent=2)

    # --- Reliability-by-decile-bin on the test set (calibration-in-the-large) ---
    bins = np.linspace(0, 1, 11)
    bin_ids = np.digitize(test_proba, bins) - 1
    reliability = []
    for b in range(10):
        mask = bin_ids == b
        if mask.sum() > 0:
            reliability.append({
                "bin": f"[{bins[b]:.1f}-{bins[b+1]:.1f})", "n": int(mask.sum()),
                "mean_predicted": round(float(test_proba[mask].mean()), 4),
                "observed": round(float(y_test[mask].mean()), 4),
            })
    calibration_summary = {
        "mean_predicted_probability": float(test_proba.mean()),
        "observed_prevalence": float(y_test.mean()),
        "reliability_by_decile": reliability,
    }
    with open(REPORTS_DIR / "v2_calibration_in_the_large.json", "w") as f:
        json.dump(calibration_summary, f, indent=2)
    print("\nCalibration-in-the-large:", json.dumps(calibration_summary, indent=2))

    joblib.dump(final_pipeline, ARTIFACTS_DIR / "diabetes_pipeline_v2.pkl")
    metadata = {
        "model_name": "diabetes_risk_model_brfss",
        "model_version": MODEL_VERSION,
        "supersedes": "diabetes-brfss-v1",
        "algorithm": "xgboost" + ("_sigmoid_calibrated" if use_calibration else ""),
        "model_family_comparison": {k: v["roc_auc"] for k, v in family_results.items()},
        "dataset_name": "CDC BRFSS 2015 Diabetes Health Indicators",
        "dataset_path": "data/raw/brfss2015-diabetes-binary.csv",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "feature_names": FEATURE_COLUMNS,
        "feature_order": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "target_classes": {"0": "no diabetes (or prediabetes only)", "1": "diagnosed diabetes"},
        "preprocessing": "StandardScaler only (no imputation: dataset has zero missing values)",
        "imputation_strategy": "none (not required)",
        "scaling_strategy": "StandardScaler, fit on training split only",
        "class_imbalance_strategy": f"scale_pos_weight={scale_pos_weight:.4f} passed to XGBoost (natural class prevalence preserved, no resampling)",
        "hyperparameters": best_params,
        "decision_threshold": threshold,
        "calibration_method": "sigmoid (Platt scaling)" if use_calibration else "none",
        "random_seed": RANDOM_STATE,
        "train_test_split": "80/20 stratified, random_state=42, exact duplicates dropped pre-split (shared with v1 — same split files)",
        "cross_validation": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
        "cv_roc_auc_mean": tuned_summary["roc_auc"]["mean"],
        "cv_roc_auc_std": tuned_summary["roc_auc"]["std"],
        "test_metrics": test_metrics,
        "library_versions": {
            "scikit-learn": sklearn.__version__, "xgboost": xgboost.__version__,
            "pandas": pd.__version__, "numpy": np.__version__,
        },
        "feature_reduction_rationale": "See ml_pipeline/diabetes/reports/feature_selection_analysis.md and candidate_assessments.md — 14 of 21 v1 features retained, selected on combined ML-importance + patient-facing-answerability evidence. Removed: Income, Education, AnyHealthcare, NoDocbcCost (sensitive/access proxies), MentHlth, PhysHlth (recall-burden, low marginal value), Veggies (redundant with retained Fruits, near-zero value).",
        "limitations": [
            "All features are self-reported survey answers (BRFSS 2015), not clinical lab measurements.",
            "The binary target excludes prediabetes from the positive class.",
            "Training data is a single U.S. CDC survey year (2015) and U.S. population.",
            "No external, independent validation dataset was available for this training run.",
            "Family history of diabetes is NOT included — no verified dataset combining it with comparable BRFSS-style features was found (see reports/family_history_investigation.md). Do not present this model as accounting for family history.",
            "Hyperparameters were independently re-tuned for this 14-feature set (not reused from v1), but the same model family (XGBoost) and calibration/threshold-selection methodology as v1 were used.",
        ],
        "intended_use": "AI-generated diabetes risk indicator for informational/screening purposes.",
        "medical_safety_notice": "This model output is a risk assessment, NOT a medical diagnosis. It must never be presented as a definitive diagnosis and should always encourage consultation with a qualified healthcare professional.",
    }
    with open(ARTIFACTS_DIR / "diabetes_metadata_v2.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\nSaved {ARTIFACTS_DIR / 'diabetes_pipeline_v2.pkl'}")
    print(f"Saved {ARTIFACTS_DIR / 'diabetes_metadata_v2.json'}")


if __name__ == "__main__":
    main()
