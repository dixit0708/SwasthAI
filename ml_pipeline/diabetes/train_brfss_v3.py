"""
diabetes-brfss-v3: identical methodology to v2 (train_brfss_v2.py), with one
change — GenHlth (self-rated general health) removed from the feature set
by explicit product decision, not a data-quality finding. See
reports/v3_general_health_removal.md for the before/after comparison this
produced.

Everything else is intentionally unchanged from v2's approach: same model-
family comparison, same independent hyperparameter search, same OOF
calibration decision, same screening-first threshold-selection rule
(highest threshold keeping training-OOF recall >= 0.85), same train/test
split files. Nothing here assumes v2's chosen family, hyperparameters,
calibration decision, or threshold — all re-derived independently on the
13-feature data, exactly as v2 did relative to v1.

The v2 artifact/metadata (artifacts/diabetes_pipeline_v2.pkl,
artifacts/diabetes_metadata_v2.json) are never read for parameters and
never written to by this script — only NEW files
(artifacts/diabetes_pipeline_v3.pkl, artifacts/diabetes_metadata_v3.json)
are produced. v1 and v2 remain on disk, untouched, as historical baselines.

Run: python train_brfss_v3.py
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
MODEL_VERSION = "diabetes-brfss-v3"

# The v2 "Expanded" 14-feature candidate, minus GenHlth (self-rated general
# health) — removed by explicit product decision. 13 features remain.
FEATURE_COLUMNS = [
    "HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke",
    "HeartDiseaseorAttack", "PhysActivity", "Fruits", "HvyAlcoholConsump",
    "DiffWalk", "Sex", "Age",
]
assert len(FEATURE_COLUMNS) == 13
assert "GenHlth" not in FEATURE_COLUMNS


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
    print(f"13-feature v3 candidate (GenHlth removed). scale_pos_weight={scale_pos_weight:.4f}")

    print("\n" + "=" * 70 + "\nSTAGE 1: Model-family comparison (do not assume XGBoost)\n" + "=" * 70)
    family_results = run_model_family_comparison(X_train, y_train, scale_pos_weight)
    with open(REPORTS_DIR / "v3_family_comparison.json", "w") as f:
        json.dump(family_results, f, indent=2)
    best_family = max(family_results, key=lambda n: family_results[n]["roc_auc"]["mean"])
    print(f"\nStrongest family by mean CV ROC-AUC: {best_family}")

    print("\n" + "=" * 70 + "\nSTAGE 2: Independent hyperparameter tuning\n" + "=" * 70)
    best_params, tuned_summary = tune_xgboost(X_train, y_train, scale_pos_weight)
    with open(REPORTS_DIR / "v3_tuned_results.json", "w") as f:
        json.dump({"best_params": best_params, "cv_summary": tuned_summary, "winning_family": best_family,
                    "family_comparison": family_results}, f, indent=2)

    print("\n" + "=" * 70 + "\nSTAGE 3: Calibration decision (OOF, training split only)\n" + "=" * 70)
    oof = compute_oof_probabilities(X_train, y_train, best_params, scale_pos_weight)
    raw_brier = brier_score_loss(y_train, oof["raw_oof"])
    cal_brier = brier_score_loss(y_train, oof["cal_oof"])
    use_calibration = (raw_brier - cal_brier) > 0.0005
    print(f"  Brier raw={raw_brier:.5f} calibrated={cal_brier:.5f} use_calibration={use_calibration}")
    with open(REPORTS_DIR / "v3_calibration_check.json", "w") as f:
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
    print(f"\n  Chosen threshold: {threshold} (same screening-first rule as v1/v2: "
          f"highest threshold keeping training-OOF recall >= 0.85)")
    with open(REPORTS_DIR / "v3_threshold_sweep.json", "w") as f:
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
    with open(REPORTS_DIR / "v3_test_evaluation.json", "w") as f:
        json.dump(test_metrics, f, indent=2)

    joblib.dump(final_pipeline, ARTIFACTS_DIR / "diabetes_pipeline_v3.pkl")
    metadata = {
        "model_name": "diabetes_risk_model_brfss",
        "model_version": MODEL_VERSION,
        "supersedes": "diabetes-brfss-v2",
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
        "train_test_split": "80/20 stratified, random_state=42, exact duplicates dropped pre-split (shared with v1/v2 — same split files)",
        "cross_validation": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
        "cv_roc_auc_mean": tuned_summary["roc_auc"]["mean"],
        "cv_roc_auc_std": tuned_summary["roc_auc"]["std"],
        "test_metrics": test_metrics,
        "library_versions": {
            "scikit-learn": sklearn.__version__, "xgboost": xgboost.__version__,
            "pandas": pd.__version__, "numpy": np.__version__,
        },
        "feature_reduction_rationale": "GenHlth (self-rated general health) removed from the v2 14-feature "
            "set by explicit product decision (not a data-quality or leakage finding — GenHlth passed every "
            "integrity check applied to v2's features). See reports/v3_general_health_removal.md for the "
            "honest before/after metric comparison this produced.",
        "limitations": [
            "All features are self-reported survey answers (BRFSS 2015), not clinical lab measurements.",
            "The binary target excludes prediabetes from the positive class.",
            "Training data is a single U.S. CDC survey year (2015) and U.S. population.",
            "No external, independent validation dataset was available for this training run.",
            "Family history of diabetes is NOT included — see reports/family_history_investigation.md.",
            "GenHlth (self-rated general health) was a feature in v2 and is intentionally excluded here — "
            "see reports/v3_general_health_removal.md for the resulting performance change.",
            "Hyperparameters were independently re-tuned for this 13-feature set (not reused from v2), but "
            "the same model family (XGBoost) and calibration/threshold-selection methodology as v1/v2 were used.",
        ],
        "intended_use": "AI-generated diabetes risk indicator for informational/screening purposes.",
        "medical_safety_notice": "This model output is a risk assessment, NOT a medical diagnosis. It must never be presented as a definitive diagnosis and should always encourage consultation with a qualified healthcare professional.",
    }
    with open(ARTIFACTS_DIR / "diabetes_metadata_v3.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\nSaved {ARTIFACTS_DIR / 'diabetes_pipeline_v3.pkl'}")
    print(f"Saved {ARTIFACTS_DIR / 'diabetes_metadata_v3.json'}")


if __name__ == "__main__":
    main()
