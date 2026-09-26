"""
One-off experiment (not part of the production pipeline): does adding
high_cholesterol and/or replacing `smoker` with the richer `smoking_status`
actually improve the model, or not? Run once, results written to
reports/feature_experiment.md, then decide whether to adopt into
train_nhanes.py — never assumed in advance (AGENTS.md Section 9: never
fabricate or assume a metric improvement).

Same CV methodology as train_nhanes.py (5-fold stratified, scored on
ROC-AUC) for a fair apples-to-apples comparison, using only Logistic
Regression (the winning family in the baseline comparison) to isolate the
effect of the feature change itself rather than re-running the full
3-model comparison for every variant.
"""
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE = Path(__file__).parent
DATA_PATH = BASE / "data" / "processed" / "nhanes_liver_pooled.csv"
RANDOM_STATE = 42

NUMERIC = ["age_years", "bmi", "waist_circumference_cm"]

VARIANTS = {
    "baseline (v1, production)": [
        "sex", "race_ethnicity", "general_health", "heavy_alcohol_use",
        "smoker", "diabetes_status", "hypertension", "physical_activity",
    ],
    "+ high_cholesterol": [
        "sex", "race_ethnicity", "general_health", "heavy_alcohol_use",
        "smoker", "diabetes_status", "hypertension", "physical_activity",
        "high_cholesterol",
    ],
    "smoker -> smoking_status": [
        "sex", "race_ethnicity", "general_health", "heavy_alcohol_use",
        "smoking_status", "diabetes_status", "hypertension", "physical_activity",
    ],
    "both changes": [
        "sex", "race_ethnicity", "general_health", "heavy_alcohol_use",
        "smoking_status", "diabetes_status", "hypertension", "physical_activity",
        "high_cholesterol",
    ],
}


def run_variant(df: pd.DataFrame, categorical_cols: list[str]) -> dict:
    feature_cols = NUMERIC + categorical_cols
    data = df.dropna(subset=feature_cols + ["liver_condition"])
    X = data[feature_cols].values
    y = data["liver_condition"].astype(int)

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), list(range(len(NUMERIC)))),
        ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"),
         list(range(len(NUMERIC), len(feature_cols)))),
    ])
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)),
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_validate(pipeline, X, y, cv=cv, scoring=["roc_auc", "f1", "recall"])
    return {
        "n_rows": len(data),
        "roc_auc": scores["test_roc_auc"].mean(),
        "roc_auc_std": scores["test_roc_auc"].std(),
        "f1": scores["test_f1"].mean(),
        "recall": scores["test_recall"].mean(),
    }


def main():
    df = pd.read_csv(DATA_PATH)

    lines = [
        "# Liver Model Feature Experiment — high_cholesterol / smoking_status",
        "",
        "Logistic Regression only (the winning family from the baseline",
        "comparison), 5-fold stratified CV on the full pooled dataset — same",
        "methodology as `train_nhanes.py`, isolating the effect of the",
        "feature change itself. Run once; numbers below are exactly what",
        "this run produced, not adjusted.",
        "",
        "| Variant | Rows | ROC-AUC (mean +/- std) | F1 | Recall |",
        "|---|---|---|---|---|",
    ]
    print(f"{'Variant':<28} {'Rows':>6} {'ROC-AUC':>18} {'F1':>8} {'Recall':>8}")
    for name, cat_cols in VARIANTS.items():
        result = run_variant(df, cat_cols)
        auc_str = f"{result['roc_auc']:.4f} +/- {result['roc_auc_std']:.4f}"
        print(f"{name:<28} {result['n_rows']:>6} {auc_str:>18} {result['f1']:>8.4f} {result['recall']:>8.4f}")
        lines.append(f"| {name} | {result['n_rows']} | {auc_str} | {result['f1']:.4f} | {result['recall']:.4f} |")

    report_path = BASE / "reports" / "feature_experiment.md"
    # Explicit encoding: Path.write_text() defaults to the platform locale
    # encoding, which is cp1252 on Windows — silently corrupts any em-dash
    # or other non-ASCII character in the report text (confirmed by
    # inspecting the raw bytes of the first run of this script).
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nSaved {report_path}")


if __name__ == "__main__":
    main()
