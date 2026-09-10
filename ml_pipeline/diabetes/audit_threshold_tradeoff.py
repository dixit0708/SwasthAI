"""
Pre-integration audit addendum: extends the threshold trade-off sweep in
train_brfss.py to include 0.05 (the original sweep started at 0.10), and
adds accuracy/false-positive-rate/false-negative-rate columns per the audit
checklist. Uses ONLY training-split out-of-fold predictions (never the
final test set) with the exact hyperparameters already locked in
artifacts/metadata.json — no retraining, no change to the selected model,
calibration method, or production decision threshold (still 0.10).

This is an audit-time diagnostic addition. The original
reports/threshold_analysis.json (0.10-0.90) remains as the historical
record of what was actually run to make the 0.10 decision; this script's
output is saved separately.

Run: python audit_threshold_tradeoff.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BASE = Path(__file__).parent
PROCESSED_DIR = BASE / "data" / "processed"
ARTIFACTS_DIR = BASE / "artifacts"
REPORTS_DIR = BASE / "reports"
RANDOM_STATE = 42


def main():
    with open(ARTIFACTS_DIR / "metadata.json") as f:
        metadata = json.load(f)

    feature_order = metadata["feature_order"]
    best_params = metadata["hyperparameters"]

    train_df = pd.read_csv(PROCESSED_DIR / "brfss_train.csv")
    X_train = train_df[feature_order]
    y_train = train_df[metadata["target_column"]].astype(int)
    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", CalibratedClassifierCV(
            XGBClassifier(
                eval_metric="logloss", scale_pos_weight=scale_pos_weight,
                random_state=RANDOM_STATE, n_jobs=-1, **best_params,
            ),
            method="sigmoid", cv=5,
        )),
    ])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cal_oof = cross_val_predict(pipeline, X_train, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]

    rows = []
    for threshold in np.arange(0.05, 0.51, 0.05):
        preds = (cal_oof >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_train, preds, labels=[0, 1]).ravel()
        rows.append({
            "threshold": round(float(threshold), 2),
            "accuracy": round(float((tp + tn) / (tp + tn + fp + fn)), 4),
            "recall_sensitivity": round(float(recall_score(y_train, preds)), 4),
            "specificity": round(float(tn / (tn + fp)) if (tn + fp) else 0.0, 4),
            "precision": round(float(precision_score(y_train, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_train, preds)), 4),
            "false_positive_rate": round(float(fp / (fp + tn)) if (fp + tn) else 0.0, 4),
            "false_negative_rate": round(float(fn / (fn + tp)) if (fn + tp) else 0.0, 4),
            "false_positives": int(fp),
            "false_negatives": int(fn),
        })
        print(rows[-1])

    with open(REPORTS_DIR / "threshold_tradeoff_audit.json", "w") as f:
        json.dump({
            "note": "Audit-time addendum to threshold_analysis.json, extended down to 0.05 with "
                     "accuracy/FPR/FNR columns added. Computed on training-split out-of-fold "
                     "predictions only (StratifiedKFold(5), same random_state=42, same locked "
                     "hyperparameters as the deployed model) — the final test set was not used. "
                     "Production decision threshold remains 0.10, unchanged by this audit.",
            "rows": rows,
        }, f, indent=2)
    print(f"\nWrote {REPORTS_DIR / 'threshold_tradeoff_audit.json'}")

    # Reproducibility check: the 0.10-0.50 rows here should exactly match
    # reports/threshold_analysis.json (same seed, same data, same params).
    with open(REPORTS_DIR / "threshold_analysis.json") as f:
        original = {r["threshold"]: r for r in json.load(f)["oof_predictions"]}
    mismatches = []
    for row in rows:
        orig = original.get(row["threshold"])
        if orig and (orig["recall_sensitivity"] != row["recall_sensitivity"] or orig["specificity"] != row["specificity"]):
            mismatches.append((row["threshold"], orig, row))
    print(f"\nReproducibility check against original threshold_analysis.json: "
          f"{'MATCH' if not mismatches else 'MISMATCH'} ({len(mismatches)} mismatched thresholds)")
    if mismatches:
        for t, o, r in mismatches:
            print(f"  threshold={t}: original={o} audit_rerun={r}")


if __name__ == "__main__":
    main()
