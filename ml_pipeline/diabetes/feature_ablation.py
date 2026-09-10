"""
Feature-selection ablation study for the BRFSS diabetes risk model.

Evaluates reduced feature sets against the SAME leakage-safe methodology
used for the 21-feature baseline (see train_brfss.py / reports/evaluation.md):

    train split -> 5-fold CV (fixed hyperparameters) -> calibration decision
    (OOF Brier, training split only) -> threshold sweep on the deployed
    probability space -> ONE final fit + ONE evaluation on the untouched
    test split.

Two families of candidate sets are evaluated, per reports/feature_selection_analysis.md:
  1. IMPORTANCE-RANKED sets (15/12/10/8/6 features) — pure ML evidence,
     answers "how much discrimination do we lose from raw feature-count
     reduction alone."
  2. PATIENT-FACING sets (Minimal/Balanced/Expanded) — evidence-informed by
     BOTH ML importance AND answerability/screening-literature relevance
     (see reports/candidate_assessments.md), explicitly excluding
     socioeconomic/access items (Income, Education, AnyHealthcare,
     NoDocbcCost) regardless of their ML importance rank.

Hyperparameters are held CONSTANT at the baseline's already-tuned values
across every candidate (see metadata.json) — this isolates the marginal
effect of the feature set itself, not a re-tuning effect. This is a
deliberate, documented simplification of a full ablation, not an oversight.

The baseline (21 features) is NOT retrained here — its already-computed,
already-audited results (reports/evaluation.md, artifacts/metadata.json)
are the reference row. This script only touches NEW candidate feature sets.

Run: python feature_ablation.py
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score, brier_score_loss, confusion_matrix, f1_score,
    make_scorer, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BASE = Path(__file__).parent
PROCESSED_DIR = BASE / "data" / "processed"
REPORTS_DIR = BASE / "reports"
ARTIFACTS_DIR = BASE / "artifacts"

TARGET_COLUMN = "Diabetes_binary"
RANDOM_STATE = 42

with open(ARTIFACTS_DIR / "metadata.json") as f:
    BASELINE_METADATA = json.load(f)
BEST_PARAMS = BASELINE_METADATA["hyperparameters"]

# Combined-rank order from reports/feature_importance.json (average of tree
# gain rank and permutation-importance rank; ties broken by permutation
# rank, the more generalization-relevant of the two) — see
# feature_selection_analysis.md for the full derivation.
IMPORTANCE_RANKED_ORDER = [
    "GenHlth", "HighBP", "BMI", "Age", "HighChol", "CholCheck",
    "HeartDiseaseorAttack", "HvyAlcoholConsump", "Sex", "DiffWalk", "Income",
    "MentHlth", "Stroke", "PhysHlth", "Education", "AnyHealthcare",
    "Veggies", "Smoker", "PhysActivity", "Fruits", "NoDocbcCost",
]

IMPORTANCE_RANKED_SETS = {
    "importance_15": IMPORTANCE_RANKED_ORDER[:15],
    "importance_12": IMPORTANCE_RANKED_ORDER[:12],
    "importance_10": IMPORTANCE_RANKED_ORDER[:10],
    "importance_8": IMPORTANCE_RANKED_ORDER[:8],
    "importance_6": IMPORTANCE_RANKED_ORDER[:6],
}

# Patient-facing candidates — see reports/candidate_assessments.md for the
# question-by-question rationale. Deliberately excludes Income, Education,
# AnyHealthcare, NoDocbcCost (poor patient-facing fit per
# feature_selection_analysis.md) regardless of their ML importance rank.
PATIENT_FACING_SETS = {
    "minimal_7": ["HighBP", "BMI", "Age", "GenHlth", "PhysActivity", "HighChol", "Sex"],
    "balanced_11": [
        "HighBP", "BMI", "Age", "GenHlth", "PhysActivity", "HighChol", "Sex",
        "HeartDiseaseorAttack", "DiffWalk", "Smoker", "HvyAlcoholConsump",
    ],
    "expanded_14": [
        "HighBP", "BMI", "Age", "GenHlth", "PhysActivity", "HighChol", "Sex",
        "HeartDiseaseorAttack", "DiffWalk", "Smoker", "HvyAlcoholConsump",
        "CholCheck", "Stroke", "Fruits",
    ],
}

ALL_CANDIDATES = {**IMPORTANCE_RANKED_SETS, **PATIENT_FACING_SETS}


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


def build_pipeline(scale_pos_weight):
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", XGBClassifier(
            eval_metric="logloss", scale_pos_weight=scale_pos_weight,
            random_state=RANDOM_STATE, n_jobs=-1, **BEST_PARAMS,
        )),
    ])


def summarize_cv(cv_results: dict) -> dict:
    return {key: {"mean": float(cv_results[f"test_{key}"].mean()), "std": float(cv_results[f"test_{key}"].std())}
            for key in SCORERS}


def pick_threshold(y_train, oof_proba) -> dict:
    """Same rule applied uniformly to every candidate (not tuned per model):
    the highest threshold, among {0.05, 0.10, ..., 0.50}, at which recall on
    the training-split OOF predictions is still >= 0.85 — mirroring exactly
    how the 21-feature baseline's 0.10 threshold was chosen (recall 0.858).
    This keeps the comparison fair: every candidate is held to the same
    screening-sensitivity bar, not cherry-picked to look good individually."""
    rows = []
    for threshold in np.arange(0.05, 0.51, 0.05):
        preds = (oof_proba >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_train, preds, labels=[0, 1]).ravel()
        rows.append({
            "threshold": round(float(threshold), 2),
            "recall": float(recall_score(y_train, preds)),
            "specificity": float(tn / (tn + fp)) if (tn + fp) else 0.0,
            "precision": float(precision_score(y_train, preds, zero_division=0)),
            "f1": float(f1_score(y_train, preds)),
        })
    eligible = [r for r in rows if r["recall"] >= 0.85]
    chosen = max(eligible, key=lambda r: r["threshold"]) if eligible else min(rows, key=lambda r: r["threshold"])
    return {"sweep": rows, "chosen_threshold": chosen["threshold"], "chosen_row": chosen}


def evaluate_candidate(name, feature_cols, X_train, y_train, X_test, y_test, scale_pos_weight):
    print(f"\n{'=' * 70}\n{name}  ({len(feature_cols)} features: {feature_cols})\n{'=' * 70}")
    t0 = time.time()
    result = {"name": name, "n_features": len(feature_cols), "features": feature_cols}

    Xtr = X_train[feature_cols]
    Xte = X_test[feature_cols]

    # --- 5-fold CV at default threshold (comparability with baseline table) ---
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_res = cross_validate(build_pipeline(scale_pos_weight), Xtr, y_train, cv=cv, scoring=SCORERS, n_jobs=-1)
    result["cv_default_threshold"] = summarize_cv(cv_res)
    print(f"  CV ROC-AUC={result['cv_default_threshold']['roc_auc']['mean']:.4f} "
          f"PR-AUC={result['cv_default_threshold']['pr_auc']['mean']:.4f}")

    # --- Calibration decision (OOF, training split only) ---
    raw_oof = cross_val_predict(build_pipeline(scale_pos_weight), Xtr, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    calibrated_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", CalibratedClassifierCV(
            XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                           random_state=RANDOM_STATE, n_jobs=-1, **BEST_PARAMS),
            method="sigmoid", cv=5,
        )),
    ])
    cal_oof = cross_val_predict(calibrated_pipeline, Xtr, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    raw_brier = brier_score_loss(y_train, raw_oof)
    cal_brier = brier_score_loss(y_train, cal_oof)
    use_calibration = (raw_brier - cal_brier) > 0.0005
    result["calibration"] = {"raw_brier": raw_brier, "calibrated_brier": cal_brier, "use_calibration": use_calibration}
    print(f"  Brier raw={raw_brier:.5f} calibrated={cal_brier:.5f} use_calibration={use_calibration}")

    deployed_oof = cal_oof if use_calibration else raw_oof
    threshold_result = pick_threshold(y_train, deployed_oof)
    result["threshold_analysis"] = threshold_result
    threshold = threshold_result["chosen_threshold"]
    print(f"  Chosen threshold={threshold} (CV recall={threshold_result['chosen_row']['recall']:.4f}, "
          f"specificity={threshold_result['chosen_row']['specificity']:.4f})")

    # --- Final fit (full training split) + ONE test evaluation ---
    base_clf = XGBClassifier(eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                              random_state=RANDOM_STATE, n_jobs=-1, **BEST_PARAMS)
    final_clf = CalibratedClassifierCV(base_clf, method="sigmoid", cv=5) if use_calibration else base_clf
    final_pipeline = Pipeline([("scaler", StandardScaler()), ("classifier", final_clf)])
    final_pipeline.fit(Xtr, y_train)

    test_proba = final_pipeline.predict_proba(Xte)[:, 1]
    test_preds = (test_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, test_preds, labels=[0, 1]).ravel()
    result["test_metrics"] = {
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
    result["wall_seconds"] = round(time.time() - t0, 1)
    print(f"  TEST ROC-AUC={result['test_metrics']['roc_auc']:.4f} "
          f"recall={result['test_metrics']['recall_sensitivity']:.4f} "
          f"specificity={result['test_metrics']['specificity']:.4f} "
          f"[{result['wall_seconds']}s]")
    return result


def main():
    train_df = pd.read_csv(PROCESSED_DIR / "brfss_train.csv")
    test_df = pd.read_csv(PROCESSED_DIR / "brfss_test.csv")
    y_train = train_df[TARGET_COLUMN].astype(int)
    y_test = test_df[TARGET_COLUMN].astype(int)
    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    print(f"scale_pos_weight={scale_pos_weight:.4f} (held constant across all candidates, "
          f"since class balance is identical regardless of feature columns)")

    all_results = {}
    for name, cols in ALL_CANDIDATES.items():
        all_results[name] = evaluate_candidate(name, cols, train_df, y_train, test_df, y_test, scale_pos_weight)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / "feature_ablation_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nWrote {REPORTS_DIR / 'feature_ablation_results.json'}")


if __name__ == "__main__":
    main()
