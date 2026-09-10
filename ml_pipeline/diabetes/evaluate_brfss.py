"""
Final held-out evaluation for the BRFSS diabetes risk model.

Loads the artifact saved by train_brfss.py and evaluates it EXACTLY ONCE on
data/processed/brfss_test.csv, which no training, tuning, threshold, or
calibration decision has touched. Also runs a bounded face-validity check
against the 3-class BRFSS file (NOT used as "external validation" — see
reports/dataset_audit.md for why that file is not an independent dataset)
and writes reports/evaluation.md plus supporting plots.

Run: python evaluate_brfss.py
"""
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay,
    average_precision_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
RAW_DIR = Path(__file__).parent / "data" / "raw"
REPORTS_DIR = Path(__file__).parent / "reports"

TARGET_COLUMN = "Diabetes_binary"


def get_feature_importances(pipeline, feature_names):
    classifier = pipeline.named_steps["classifier"]
    if isinstance(classifier, CalibratedClassifierCV):
        importances = np.mean(
            [cc.estimator.feature_importances_ for cc in classifier.calibrated_classifiers_], axis=0
        )
    else:
        importances = classifier.feature_importances_
    return dict(sorted(zip(feature_names, importances.tolist()), key=lambda kv: -kv[1]))


def main():
    with open(ARTIFACTS_DIR / "metadata.json") as f:
        metadata = json.load(f)

    pipeline = joblib.load(ARTIFACTS_DIR / "diabetes_pipeline.pkl")
    feature_columns = metadata["feature_order"]
    threshold = metadata["decision_threshold"]

    test_df = pd.read_csv(PROCESSED_DIR / "brfss_test.csv")
    X_test = test_df[feature_columns]
    y_test = test_df[TARGET_COLUMN].astype(int)

    proba = pipeline.predict_proba(X_test)[:, 1]
    preds = (proba >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_test, preds, labels=[0, 1]).ravel()
    metrics = {
        "accuracy": float((tp + tn) / (tp + tn + fp + fn)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall_sensitivity": float(recall_score(y_test, preds)),
        "specificity": float(tn / (tn + fp)) if (tn + fp) else 0.0,
        "f1": float(f1_score(y_test, preds)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "pr_auc": float(average_precision_score(y_test, proba)),
        "confusion_matrix": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
        "threshold_used": threshold,
        "n_test_rows": int(len(y_test)),
    }
    print(json.dumps(metrics, indent=2))

    with open(PROCESSED_DIR / "brfss_evaluation_results.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # --- Plots ---
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(5, 5))
    ConfusionMatrixDisplay.from_predictions(y_test, preds, display_labels=["No diabetes", "Diabetes"], ax=ax, cmap="Blues")
    ax.set_title("Confusion Matrix (test set, threshold={:.2f})".format(threshold))
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 5))
    RocCurveDisplay.from_predictions(y_test, proba, ax=ax)
    ax.set_title("ROC Curve (test set)")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "roc_curve.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 5))
    PrecisionRecallDisplay.from_predictions(y_test, proba, ax=ax)
    ax.set_title("Precision-Recall Curve (test set)")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "precision_recall_curve.png", dpi=150)
    plt.close(fig)

    # --- Explainability ---
    tree_importances = get_feature_importances(pipeline, feature_columns)
    perm_result = permutation_importance(
        pipeline, X_test, y_test, scoring="roc_auc", n_repeats=5, random_state=42, n_jobs=-1,
    )
    perm_importances = dict(sorted(
        zip(feature_columns, perm_result.importances_mean.tolist()), key=lambda kv: -kv[1]
    ))

    fig, ax = plt.subplots(figsize=(7, 6))
    names = list(tree_importances.keys())[:10]
    values = [tree_importances[n] for n in names]
    ax.barh(names[::-1], values[::-1], color="#2f6feb")
    ax.set_xlabel("XGBoost feature importance (gain-based)")
    ax.set_title("Top 10 features contributing to the model's predictions")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "feature_importance.png", dpi=150)
    plt.close(fig)

    with open(REPORTS_DIR / "feature_importance.json", "w") as f:
        json.dump({"tree_gain_importance": tree_importances, "permutation_importance_roc_auc": perm_importances}, f, indent=2)

    # --- Bounded face-validity check against the 3-class file (NOT external validation) ---
    face_validity = run_face_validity_check(test_df, proba)
    with open(REPORTS_DIR / "face_validity_check.json", "w") as f:
        json.dump(face_validity, f, indent=2)
    print("\nFace-validity check (mean predicted risk by clinical severity, test rows only):")
    print(json.dumps(face_validity, indent=2))

    write_evaluation_report(metadata, metrics, tree_importances, perm_importances, face_validity)


def run_face_validity_check(test_df: pd.DataFrame, proba: np.ndarray) -> dict:
    """The 012 file is row-for-row identical (same feature values, same row
    order) to the primary binary file — see reports/dataset_audit.md. This
    lets us look up each already-held-out test row's finer-grained 3-class
    label by matching on feature values, purely to sanity-check that the
    model's predicted risk increases with clinical severity. This is NOT an
    external validation (same underlying rows, not an independent sample)."""
    df_012 = pd.read_csv(RAW_DIR / "brfss2015-diabetes-012.csv")
    feature_cols = [c for c in test_df.columns if c != "Diabetes_binary"]

    merged = test_df.copy()
    merged["risk_probability"] = proba
    merged = merged.merge(
        df_012[feature_cols + ["Diabetes_012"]].drop_duplicates(subset=feature_cols),
        on=feature_cols, how="left",
    )
    matched = merged["Diabetes_012"].notna().sum()

    result = {"matched_rows": int(matched), "total_test_rows": int(len(merged))}
    for label, name in [(0.0, "no_diabetes"), (1.0, "prediabetes"), (2.0, "diabetes")]:
        subset = merged.loc[merged["Diabetes_012"] == label, "risk_probability"]
        if len(subset):
            result[name] = {"mean_predicted_risk": float(subset.mean()), "n": int(len(subset))}
    return result


def write_evaluation_report(metadata, metrics, tree_importances, perm_importances, face_validity):
    top_features = list(tree_importances.items())[:8]
    top_perm_features = list(perm_importances.items())[:8]
    lines = [
        "# Final Evaluation Report — BRFSS Diabetes Risk Model",
        "",
        "## Dataset",
        "",
        "- Name: CDC BRFSS 2015 Diabetes Health Indicators (Kaggle / UCI mirror)",
        f"- Source file: `{metadata['dataset_path']}`",
        "- Target: `Diabetes_binary` — 1 only for a diagnosed-diabetes response, 0 for no-diabetes or prediabetes-only (see data/raw/README_brfss2015.md)",
        "- Class distribution after dedup: see `data/processed/brfss_dataset_stats.json` (train ~15.3% positive, test ~15.3% positive, stratified)",
        "",
        "## Cleaning",
        "",
        "- No missing values in the source data — no imputation performed.",
        "- 24,206 exact duplicate rows (9.5%) dropped before the train/test split, for leakage prevention (see `preprocessing_brfss.py`).",
        "- No invalid/out-of-codebook values found; extreme BMI values (up to 98) retained as plausible, not removed as outliers.",
        "",
        "## Training",
        "",
        "- Split: 80/20 stratified, `random_state=42`.",
        "- Cross-validation: `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`.",
        "- Imbalance handling: class weighting (`scale_pos_weight`/`class_weight='balanced'`), not SMOTE/undersampling — this keeps the natural ~15% prevalence intact, which matters for probability calibration; see `reports/cv_baseline_results.json`.",
        "- Preprocessing: `StandardScaler` only (fit on the training split only, inside the saved pipeline).",
        "",
        "## Models compared (5-fold CV, training split only)",
        "",
        "See `reports/cv_baseline_results.json` for the full metric set (accuracy/precision/recall/specificity/F1/ROC-AUC/PR-AUC, mean ± std) across logistic regression, random forest, XGBoost, HistGradientBoosting, and SVM (SVM evaluated on an 8,000-row stratified subsample only — kernel SVM does not scale to 183,579 training rows, and is ineligible for production selection regardless of score).",
        "",
        "## Model selection",
        "",
        f"Selected: **{metadata['algorithm']}**. XGBoost was the strongest scalable baseline by mean CV ROC-AUC and was carried into hyperparameter tuning (`RandomizedSearchCV`, 20 iterations, cv=3 for search efficiency, re-verified with the full 5-fold protocol afterward — see `reports/cv_tuned_results.json`).",
        "",
        "## Hyperparameters",
        "",
        f"```json\n{json.dumps(metadata['hyperparameters'], indent=2)}\n```",
        "",
        "## Threshold",
        "",
        f"Decision threshold locked at **{metadata['decision_threshold']}** (not the default 0.5). See `reports/threshold_analysis.json` for the full sensitivity/specificity/precision/F1 sweep on out-of-fold CV predictions. For a screening/risk-assessment tool over an imbalanced (~15% positive) population, a lowered threshold trades some precision for materially higher recall/sensitivity — missing an at-risk person is a worse outcome than one extra person being told to consult a doctor.",
        "",
        "## Calibration",
        "",
        f"Calibration method: **{metadata['calibration_method']}**. Decision based on out-of-fold Brier score comparison — see `reports/calibration_check.json`.",
        "",
        "## Final Test Metrics (evaluated once, held-out test set, never used for selection/tuning)",
        "",
        f"- Accuracy: {metrics['accuracy']:.4f}",
        f"- Precision: {metrics['precision']:.4f}",
        f"- Recall / Sensitivity: {metrics['recall_sensitivity']:.4f}",
        f"- Specificity: {metrics['specificity']:.4f}",
        f"- F1: {metrics['f1']:.4f}",
        f"- ROC-AUC: {metrics['roc_auc']:.4f}",
        f"- PR-AUC: {metrics['pr_auc']:.4f}",
        "",
        "## Confusion Matrix (test set)",
        "",
        f"- True Positives: {metrics['confusion_matrix']['tp']}",
        f"- True Negatives: {metrics['confusion_matrix']['tn']}",
        f"- False Positives: {metrics['confusion_matrix']['fp']}",
        f"- False Negatives: {metrics['confusion_matrix']['fn']}",
        "",
        "See `confusion_matrix.png`, `roc_curve.png`, `precision_recall_curve.png` in this directory.",
        "",
        "## Feature importance (explainability)",
        "",
        "Two methods were used because they can disagree, and did here — gain-based importance can overweight a feature used in many early tree splits even if it does not move held-out ranking performance much, while permutation importance measures the actual ROC-AUC drop when a feature is shuffled on the test set. Both are reported rather than picking whichever looks better.",
        "",
        "**XGBoost gain-based importance (top 8):**",
        "",
    ]
    for name, value in top_features:
        lines.append(f"- `{name}`: {value:.4f}")
    lines += [
        "",
        "**Permutation importance, mean ROC-AUC drop on the test set (top 8):**",
        "",
    ]
    for name, value in top_perm_features:
        lines.append(f"- `{name}`: {value:.5f}")
    lines += [
        "",
        f"`GenHlth` (self-rated general health), `BMI`, and `Age` rank highest by permutation importance; `HighBP` dominates the gain-based ranking. Both agree that `HighBP`, `GenHlth`, `HighChol`, `Age`, and `BMI` are among the most influential features overall.",
    ]
    lines += [
        "",
        "These features were influential for the model's predictions — this is not evidence that any one of them causes diabetes.",
        "",
        "## External validation",
        "",
        "**Not performed as a true external validation.** Of the two other provided files, `diabetes_binary_5050split_health_indicators_BRFSS2015.csv` is a strict undersampled subset of the primary training file (every row already appears in it), and `diabetes_012_health_indicators_BRFSS2015.csv` shares the exact same 253,680 rows/features as the primary file under a different target encoding — neither is an independent sample, so evaluating on either would not measure generalization. See `reports/dataset_audit.md` for the row-level verification.",
        "",
        "Instead, a bounded face-validity check was run on the already-held-out test rows only, joining back to the 3-class label by feature-value match (ambiguous for the small fraction of rows sharing an identical feature pattern across people with different severities — acceptable for a face-validity check, not for a validation claim):",
        "",
        f"```json\n{json.dumps(face_validity, indent=2)}\n```",
        "",
        "If mean predicted risk increases monotonically from no-diabetes to prediabetes to diabetes, that supports the model tracking real clinical severity gradients, even though prediabetes is not a positive label it was trained on.",
        "",
        "## Limitations",
        "",
    ]
    for item in metadata["limitations"]:
        lines.append(f"- {item}")
    lines += [
        "",
        "This model is an **AI-generated diabetes risk indicator, not a medical diagnosis**. It has not undergone independent external clinical validation.",
    ]

    with open(REPORTS_DIR / "evaluation.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {REPORTS_DIR / 'evaluation.md'}")


if __name__ == "__main__":
    main()
