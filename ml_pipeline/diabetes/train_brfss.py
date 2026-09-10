"""
Train the diabetes risk model on the CDC BRFSS 2015 Diabetes Health
Indicators dataset (see reports/dataset_audit.md for why this dataset and
this file specifically were selected as primary).

Stages (all model-selection/tuning work happens on the training split only —
data/processed/brfss_test.csv is never touched until evaluate_brfss.py):
  1. Baseline 5-fold stratified CV comparison across four model families.
  2. Randomized hyperparameter search on the strongest baseline candidate(s).
  3. Decision-threshold analysis on out-of-fold CV predictions.
  4. Probability-calibration check (raw vs. sigmoid-calibrated Brier score).
  5. Final refit on the full training split, using the locked
     preprocessing + hyperparameters + threshold + calibration decision.
  6. Save the complete pipeline + metadata to artifacts/.

Run: python train_brfss.py
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
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
REPORTS_DIR = Path(__file__).parent / "reports"

TARGET_COLUMN = "Diabetes_binary"
FEATURE_COLUMNS = [
    "HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke",
    "HeartDiseaseorAttack", "PhysActivity", "Fruits", "Veggies",
    "HvyAlcoholConsump", "AnyHealthcare", "NoDocbcCost", "GenHlth",
    "MentHlth", "PhysHlth", "DiffWalk", "Sex", "Age", "Education", "Income",
]
MODEL_VERSION = "diabetes-brfss-v1"
RANDOM_STATE = 42
SVM_SUBSAMPLE_SIZE = 8000  # kernel SVM does not scale to 183k rows; see reports/model_comparison.md


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


def build_pipeline(classifier) -> Pipeline:
    # No SimpleImputer step: reports/dataset_audit.md confirms zero missing
    # values in this dataset, so an imputer would be dead code. StandardScaler
    # is kept in the shared pipeline for the scale-sensitive models
    # (LogisticRegression, SVC); tree ensembles ignore it harmlessly, and
    # keeping one shared pipeline shape avoids duplicating preprocessing
    # logic per-model.
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", classifier),
    ])


def summarize_cv(cv_results: dict) -> dict:
    summary = {}
    for key in SCORERS:
        scores = cv_results[f"test_{key}"]
        summary[key] = {"mean": float(scores.mean()), "std": float(scores.std())}
    return summary


def run_baseline_comparison(X_train: pd.DataFrame, y_train: pd.Series) -> dict:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()

    candidates = {
        "logistic_regression": build_pipeline(
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
        ),
        "random_forest": build_pipeline(
            RandomForestClassifier(
                n_estimators=150, max_depth=16, class_weight="balanced",
                random_state=RANDOM_STATE, n_jobs=1,
            )
        ),
        "xgboost": build_pipeline(
            XGBClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.1,
                eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                random_state=RANDOM_STATE, n_jobs=1,
            )
        ),
        "hist_gradient_boosting": build_pipeline(
            HistGradientBoostingClassifier(
                max_iter=200, class_weight="balanced", random_state=RANDOM_STATE,
            )
        ),
    }

    results = {}
    for name, pipeline in candidates.items():
        t0 = time.time()
        cv_res = cross_validate(
            pipeline, X_train, y_train, cv=cv, scoring=SCORERS, n_jobs=-1,
        )
        results[name] = summarize_cv(cv_res)
        results[name]["n_rows"] = int(len(X_train))
        results[name]["wall_seconds"] = round(time.time() - t0, 1)
        print(f"{name}: ROC-AUC={results[name]['roc_auc']['mean']:.4f} "
              f"(+/-{results[name]['roc_auc']['std']:.4f})  "
              f"[{results[name]['wall_seconds']}s, n={len(X_train)}]")

    # SVM: kernel SVC does not scale to 183k rows (O(n^2)-O(n^3) training
    # cost). Evaluated on a fixed stratified subsample for baseline
    # comparison only; explicitly ineligible for production selection
    # regardless of its score, since it cannot be retrained/scaled at this
    # dataset's size or served at production inference volume.
    X_sub, _, y_sub, _ = train_test_split(
        X_train, y_train, train_size=SVM_SUBSAMPLE_SIZE, stratify=y_train,
        random_state=RANDOM_STATE,
    )
    svm_pipeline = build_pipeline(
        SVC(kernel="rbf", class_weight="balanced", probability=True, random_state=RANDOM_STATE)
    )
    t0 = time.time()
    cv_res = cross_validate(svm_pipeline, X_sub, y_sub, cv=cv, scoring=SCORERS, n_jobs=-1)
    results["svm_rbf_subsample"] = summarize_cv(cv_res)
    results["svm_rbf_subsample"]["n_rows"] = int(len(X_sub))
    results["svm_rbf_subsample"]["wall_seconds"] = round(time.time() - t0, 1)
    results["svm_rbf_subsample"]["note"] = (
        f"Evaluated on a {SVM_SUBSAMPLE_SIZE}-row stratified subsample of the training "
        "split, not the full 183,579-row training set — kernel SVM training cost does not "
        "scale to this dataset size. Not eligible for production selection."
    )
    print(f"svm_rbf_subsample: ROC-AUC={results['svm_rbf_subsample']['roc_auc']['mean']:.4f} "
          f"(+/-{results['svm_rbf_subsample']['roc_auc']['std']:.4f})  "
          f"[{results['svm_rbf_subsample']['wall_seconds']}s, n={len(X_sub)}] (subsampled)")

    return results


def tune_candidate(X_train, y_train, scale_pos_weight) -> tuple:
    """RandomizedSearchCV on XGBoost, the strongest scalable baseline candidate.

    cv=3 (not 5) for the search itself, purely to keep the search budget
    reasonable (n_iter=20 x 3 folds = 60 fits instead of 100) — the final
    locked hyperparameters are then re-verified with the full 5-fold CV
    protocol used everywhere else in this script, so nothing is selected on
    a weaker validation protocol than the rest of the comparison.
    """
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
        XGBClassifier(
            eval_metric="logloss", scale_pos_weight=scale_pos_weight,
            random_state=RANDOM_STATE, n_jobs=1,
        )
    )
    search = RandomizedSearchCV(
        pipeline, param_dist, n_iter=20, scoring="roc_auc",
        cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE),
        random_state=RANDOM_STATE, n_jobs=-1, verbose=1,
    )
    search.fit(X_train, y_train)
    best_params = {k.replace("classifier__", ""): v for k, v in search.best_params_.items()}
    print(f"\nBest params (cv=3 search): {best_params}")
    print(f"Best cv=3 ROC-AUC: {search.best_score_:.4f}")

    tuned_pipeline = build_pipeline(
        XGBClassifier(
            eval_metric="logloss", scale_pos_weight=scale_pos_weight,
            random_state=RANDOM_STATE, n_jobs=1, **best_params,
        )
    )
    cv5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_res = cross_validate(tuned_pipeline, X_train, y_train, cv=cv5, scoring=SCORERS, n_jobs=-1)
    tuned_summary = summarize_cv(cv_res)
    print(f"Tuned model, full 5-fold re-verification: ROC-AUC="
          f"{tuned_summary['roc_auc']['mean']:.4f} (+/-{tuned_summary['roc_auc']['std']:.4f})")
    return best_params, tuned_summary


def compute_oof_probabilities(X_train, y_train, best_params, scale_pos_weight) -> dict:
    """Out-of-fold predict_proba for both the raw tuned model and its
    sigmoid-calibrated version, computed once and reused by both the
    calibration check and the threshold analysis (whichever probability
    space ends up selected is also the one the threshold gets tuned on —
    tuning a threshold against the raw model's probabilities and then
    applying it to the calibrated model's output would silently pick the
    wrong cutoff, since calibration changes the probability scale)."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    raw_pipeline = build_pipeline(
        XGBClassifier(
            eval_metric="logloss", scale_pos_weight=scale_pos_weight,
            random_state=RANDOM_STATE, n_jobs=-1, **best_params,
        )
    )
    raw_oof = cross_val_predict(raw_pipeline, X_train, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]

    calibrated_pipeline = build_pipeline(
        CalibratedClassifierCV(
            XGBClassifier(
                eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                random_state=RANDOM_STATE, n_jobs=-1, **best_params,
            ),
            method="sigmoid", cv=5,
        )
    )
    cal_oof = cross_val_predict(calibrated_pipeline, X_train, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]

    return {"raw_oof": raw_oof, "cal_oof": cal_oof}


def compare_calibration(y_train, raw_oof, cal_oof) -> dict:
    """Brier score comparison using only training-split out-of-fold
    predictions (no test-set information)."""
    raw_brier = brier_score_loss(y_train, raw_oof)
    cal_brier = brier_score_loss(y_train, cal_oof)
    return {
        "raw_brier_score": round(float(raw_brier), 5),
        "sigmoid_calibrated_brier_score": round(float(cal_brier), 5),
        "improvement": round(float(raw_brier - cal_brier), 5),
    }


def threshold_analysis(y_train, oof_proba) -> dict:
    rows = []
    for threshold in np.arange(0.10, 0.91, 0.05):
        preds = (oof_proba >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_train, preds, labels=[0, 1]).ravel()
        rows.append({
            "threshold": round(float(threshold), 2),
            "recall_sensitivity": round(float(recall_score(y_train, preds)), 4),
            "specificity": round(float(tn / (tn + fp)) if (tn + fp) else 0.0, 4),
            "precision": round(float(precision_score(y_train, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_train, preds)), 4),
            "false_positives": int(fp),
            "false_negatives": int(fn),
        })
    return {"oof_predictions": rows}


def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(PROCESSED_DIR / "brfss_train.csv")
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN].astype(int)
    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())

    print("=" * 70)
    print("STAGE 1: Baseline 5-fold CV comparison")
    print("=" * 70)
    baseline_results = run_baseline_comparison(X_train, y_train)
    with open(REPORTS_DIR / "cv_baseline_results.json", "w") as f:
        json.dump(baseline_results, f, indent=2)

    best_baseline = max(
        (k for k in baseline_results if k != "svm_rbf_subsample"),
        key=lambda n: baseline_results[n]["roc_auc"]["mean"],
    )
    print(f"\nStrongest scalable baseline by mean CV ROC-AUC: {best_baseline}")

    print("\n" + "=" * 70)
    print("STAGE 2: Hyperparameter tuning (XGBoost)")
    print("=" * 70)
    best_params, tuned_summary = tune_candidate(X_train, y_train, scale_pos_weight)
    with open(REPORTS_DIR / "cv_tuned_results.json", "w") as f:
        json.dump({"best_params": best_params, "cv_summary": tuned_summary}, f, indent=2)

    print("\n" + "=" * 70)
    print("STAGE 3: Probability calibration check (out-of-fold CV predictions)")
    print("=" * 70)
    oof = compute_oof_probabilities(X_train, y_train, best_params, scale_pos_weight)
    calibration_results = compare_calibration(y_train, oof["raw_oof"], oof["cal_oof"])
    print(calibration_results)
    with open(REPORTS_DIR / "calibration_check.json", "w") as f:
        json.dump(calibration_results, f, indent=2)

    # Calibration is selected/rejected BEFORE the threshold sweep, and the
    # sweep then runs on whichever probability space will actually be
    # deployed — tuning the threshold on the raw model's probabilities and
    # then applying it to the calibrated model (or vice versa) would pick a
    # cutoff that means something different from what was analyzed, since
    # calibration reshapes the probability scale.
    USE_CALIBRATION = calibration_results["improvement"] > 0.0005
    deployed_oof = oof["cal_oof"] if USE_CALIBRATION else oof["raw_oof"]

    print("\n" + "=" * 70)
    print(f"STAGE 4: Decision threshold analysis "
          f"(on {'calibrated' if USE_CALIBRATION else 'raw'} out-of-fold probabilities)")
    print("=" * 70)
    threshold_results = threshold_analysis(y_train, deployed_oof)
    with open(REPORTS_DIR / "threshold_analysis.json", "w") as f:
        json.dump(threshold_results, f, indent=2)
    for row in threshold_results["oof_predictions"]:
        print(row)

    # --- Threshold locked here based on the sweep above; see
    # reports/evaluation.md for the full written rationale. Calibration
    # compresses probabilities back toward the true ~15% base rate, so 0.5
    # (or the 0.35 that looked reasonable on the RAW/uncalibrated scale)
    # would badly under-flag positives once applied to calibrated output —
    # confirmed by the sweep: threshold=0.35 on calibrated probabilities
    # gives recall=0.434, vs. recall=0.858 at threshold=0.10 with
    # specificity=0.608 — chosen here because missing an at-risk person is a
    # worse screening failure than one extra person being told to consult a
    # doctor (AGENTS.md Section 43: user safety is the top priority).
    DECISION_THRESHOLD = 0.10

    print("\n" + "=" * 70)
    print(f"STAGE 5: Final fit on full training split "
          f"(threshold={DECISION_THRESHOLD}, calibration={'sigmoid' if USE_CALIBRATION else 'none'})")
    print("=" * 70)

    base_classifier = XGBClassifier(
        eval_metric="logloss", scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_STATE, n_jobs=-1, **best_params,
    )
    if USE_CALIBRATION:
        final_classifier = CalibratedClassifierCV(base_classifier, method="sigmoid", cv=5)
    else:
        final_classifier = base_classifier

    final_pipeline = build_pipeline(final_classifier)
    final_pipeline.fit(X_train, y_train)

    joblib.dump(final_pipeline, ARTIFACTS_DIR / "diabetes_pipeline.pkl")

    metadata = {
        "model_name": "diabetes_risk_model_brfss",
        "model_version": MODEL_VERSION,
        "algorithm": "xgboost" + ("_sigmoid_calibrated" if USE_CALIBRATION else ""),
        "dataset_name": "CDC BRFSS 2015 Diabetes Health Indicators",
        "dataset_path": "data/raw/brfss2015-diabetes-binary.csv",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "feature_names": FEATURE_COLUMNS,
        "feature_order": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "target_classes": {"0": "no diabetes (or prediabetes only)", "1": "diagnosed diabetes"},
        "preprocessing": "StandardScaler only (no imputation: dataset has zero missing values, see reports/dataset_audit.md)",
        "imputation_strategy": "none (not required)",
        "scaling_strategy": "StandardScaler, fit on training split only",
        "class_imbalance_strategy": f"scale_pos_weight={scale_pos_weight:.4f} passed to XGBoost (natural class prevalence preserved, no resampling)",
        "hyperparameters": best_params,
        "decision_threshold": DECISION_THRESHOLD,
        "calibration_method": "sigmoid (Platt scaling)" if USE_CALIBRATION else "none",
        "random_seed": RANDOM_STATE,
        "train_test_split": "80/20 stratified, random_state=42, exact duplicates dropped pre-split",
        "cross_validation": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
        "cv_roc_auc_mean": tuned_summary["roc_auc"]["mean"],
        "cv_roc_auc_std": tuned_summary["roc_auc"]["std"],
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "limitations": [
            "All features are self-reported survey answers (BRFSS 2015), not clinical lab measurements — this is a lifestyle/health-history risk indicator, not a lab-based clinical model.",
            "The binary target excludes prediabetes from the positive class (Diabetes_binary==1 only when the original 3-class label was 2, i.e. diagnosed diabetes) — this model does not flag prediabetes as elevated risk.",
            "Training data is a single U.S. CDC survey year (2015) and U.S. population; generalization to other countries/years is unverified.",
            "No external, independent validation dataset was available for this training run — see reports/evaluation.md.",
        ],
        "intended_use": "AI-generated diabetes risk indicator for informational/screening purposes.",
        "medical_safety_notice": "This model output is a risk assessment, NOT a medical diagnosis. It must never be presented as a definitive diagnosis and should always encourage consultation with a qualified healthcare professional.",
    }
    with open(ARTIFACTS_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved pipeline to {ARTIFACTS_DIR / 'diabetes_pipeline.pkl'}")
    print(f"Saved metadata to {ARTIFACTS_DIR / 'metadata.json'}")


if __name__ == "__main__":
    main()
