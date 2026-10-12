"""
Analysis-only script — does NOT fit, refit, or modify any model.

Full decision-threshold sweep (0.10 to 0.90, step 0.01) of the already-shipped
production liver-risk artifact, scored on the validation split only. Reuses
the exact same split reproduction and `compute_metrics` logic as
`threshold_analysis.py` (imported, not retyped) so the two analyses are
directly comparable and consistent. No `.fit()` call occurs anywhere here;
this script only calls `joblib.load` and `predict_proba`.

Purpose: report accuracy (plus precision/recall/specificity/F1/confusion
counts) across the full threshold range, and flag which thresholds reach
80%/85%/90% accuracy and which threshold maximizes accuracy. The validation
set's positive-class prevalence is reported alongside every accuracy number
because this dataset is heavily imbalanced (~5% positive) — a classifier
that predicts "no liver condition" for almost everyone can reach ~95%
accuracy trivially, which is not the same thing as a clinically useful
screening tool. See reports/accuracy_threshold_sweep.md for the full
write-up and that caveat spelled out against the actual numbers below.
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from train_nhanes import DATA_PATH, ARTIFACTS_DIR, FEATURE_COLUMNS, TARGET_COLUMN, RANDOM_STATE
from threshold_analysis import compute_metrics

PIPELINE_PATH = ARTIFACTS_DIR / "liver_pipeline_nhanes_v1.pkl"
METADATA_PATH = ARTIFACTS_DIR / "liver_metadata_nhanes_v1.json"

THRESHOLDS = np.round(np.arange(0.10, 0.9001, 0.01), 2)
ACCURACY_TARGETS = [0.80, 0.85, 0.90]


def main():
    with open(METADATA_PATH) as f:
        metadata = json.load(f)
    current_threshold = metadata["decision_threshold"]

    # Load the already-fit production pipeline — inference only, no .fit().
    pipeline = joblib.load(PIPELINE_PATH)

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].astype(int).values

    # Identical split logic/constants to train_nhanes.py (imported, not
    # retyped) so this reproduces the exact same train/val/test partition
    # the shipped model's threshold was originally chosen against.
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=RANDOM_STATE, stratify=y_trainval
    )
    # X_test/y_test deliberately unused beyond this point in this script.

    val_proba = pipeline.predict_proba(X_val)[:, 1]
    prevalence = float(y_val.mean())

    rows = []
    for t in THRESHOLDS:
        preds = (val_proba >= t).astype(int)
        m = compute_metrics(y_val, preds)
        rows.append({"threshold": float(t), **m})

    max_acc_row = max(rows, key=lambda r: r["accuracy"])
    max_acc_thresholds = [r["threshold"] for r in rows if r["accuracy"] == max_acc_row["accuracy"]]

    target_hits = {}
    for target in ACCURACY_TARGETS:
        hits = [r["threshold"] for r in rows if r["accuracy"] >= target]
        target_hits[target] = hits

    print(f"n_val = {len(y_val)}, positive prevalence in val = {prevalence:.4f} ({int(y_val.sum())} positive cases)")
    print(f"Current production threshold: {current_threshold}\n")
    print(f"{'Thresh':>7}{'Acc.':>8}{'Prec.':>8}{'Recall':>8}{'Specif.':>9}{'F1':>8}{'TP':>6}{'TN':>6}{'FP':>6}{'FN':>6}{'PredPos%':>10}")
    for r in rows:
        print(f"{r['threshold']:>7.2f}{r['accuracy']:>8.3f}{r['precision']:>8.3f}{r['recall']:>8.3f}"
              f"{r['specificity']:>9.3f}{r['f1']:>8.3f}{r['tp']:>6}{r['tn']:>6}{r['fp']:>6}{r['fn']:>6}"
              f"{r['predicted_positive_rate']*100:>9.1f}%")

    print(f"\nMax-accuracy threshold(s): {max_acc_thresholds} -> accuracy {max_acc_row['accuracy']:.4f}")
    for target in ACCURACY_TARGETS:
        hits = target_hits[target]
        if hits:
            print(f"Thresholds reaching >={int(target*100)}% accuracy: {hits[0]:.2f} to {hits[-1]:.2f} ({len(hits)} threshold(s))")
        else:
            print(f"Thresholds reaching >={int(target*100)}% accuracy: none in [0.10, 0.90]")

    return rows, prevalence, len(y_val), int(y_val.sum()), max_acc_thresholds, target_hits


if __name__ == "__main__":
    main()
