"""
Analysis-only script — does NOT fit, refit, or modify any model.

Loads the already-saved production liver-risk artifact (joblib.load only)
and the processed dataset, reproduces the existing 60/20/20 split
deterministically (identical constants/random_state to train_nhanes.py,
imported directly from it rather than retyped, to guarantee an exact
match), and runs read-only inference (`predict_proba`) on the validation
split to compare candidate decision thresholds.

Methodological note (see reports/threshold_analysis.md for the full
writeup): the validation-set probabilities from the original training run
were computed in-memory to pick the shipped threshold but never persisted
to disk. The shipped artifact itself was refit on train+val, so it isn't a
fully independent holdout for this exact validation subset. Getting a
truly clean train-only-fit validation score would require re-fitting a
model — explicitly out of scope here. This script instead runs the
already-saved, already-fit artifact's inference on the validation split;
every candidate threshold below is compared using that same set of
predictions, so the *relative* trade-off between thresholds is still a
fair comparison even though the absolute numbers likely skew a little
optimistic. No model is fit, refit, or saved by this script.
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from train_nhanes import DATA_PATH, ARTIFACTS_DIR, FEATURE_COLUMNS, TARGET_COLUMN, RANDOM_STATE

PIPELINE_PATH = ARTIFACTS_DIR / "liver_pipeline_nhanes_v1.pkl"
METADATA_PATH = ARTIFACTS_DIR / "liver_metadata_nhanes_v1.json"

TARGET_RECALLS = [0.85, 0.80, 0.75, 0.70, 0.65]


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    total = tp + tn + fp + fn

    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    predicted_positive_rate = (tp + fp) / total if total else 0.0

    return {
        "recall": recall, "specificity": specificity, "precision": precision,
        "f1": f1, "accuracy": accuracy, "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "predicted_positive_rate": predicted_positive_rate,
    }


def nearest_threshold_for_recall(proba: np.ndarray, y_true: np.ndarray, target_recall: float) -> float:
    candidates = np.unique(proba)
    best_threshold = candidates[0]
    best_diff = None
    for t in candidates:
        preds = (proba >= t).astype(int)
        m = compute_metrics(y_true, preds)
        diff = abs(m["recall"] - target_recall)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_threshold = float(t)
    return best_threshold


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

    rows = []
    label = "Current (production)"
    preds = (val_proba >= current_threshold).astype(int)
    m = compute_metrics(y_val, preds)
    rows.append({"label": label, "threshold": current_threshold, **m})

    for target in TARGET_RECALLS:
        t = nearest_threshold_for_recall(val_proba, y_val, target)
        preds = (val_proba >= t).astype(int)
        m = compute_metrics(y_val, preds)
        rows.append({"label": f"~{int(target * 100)}% Recall", "threshold": t, **m})

    print(f"{'Operating Point':<24}{'Thresh':>8}{'Recall':>9}{'Specif.':>9}{'Precis.':>9}{'F1':>8}{'Acc.':>8}{'PredPos%':>10}")
    for r in rows:
        print(f"{r['label']:<24}{r['threshold']:>8.3f}{r['recall']:>9.3f}{r['specificity']:>9.3f}"
              f"{r['precision']:>9.3f}{r['f1']:>8.3f}{r['accuracy']:>8.3f}{r['predicted_positive_rate']*100:>9.1f}%")
        print(f"    TP={r['tp']}  TN={r['tn']}  FP={r['fp']}  FN={r['fn']}")

    print(f"\nn_val = {len(y_val)}, positive rate in val = {y_val.mean():.4f}")

    return rows, len(y_val), float(y_val.mean())


if __name__ == "__main__":
    main()
