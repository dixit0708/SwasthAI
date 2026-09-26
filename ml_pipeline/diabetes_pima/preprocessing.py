"""
SwasthAI — Diabetes Risk Model (Lab-Based / Pima) — dataset builder
======================================================================
Independent of ml_pipeline/diabetes (BRFSS, lab-free) and ml_pipeline/liver:
separate data source, separate population, separate trained artifact,
never merged with either of them.

Source: Pima Indians Diabetes Database (NIDDK / UCI ML Repository, Smith
et al. 1988) — see data/raw/README.md for full provenance.

This is the "I have recent lab results" counterpart to the lab-free BRFSS
model: it requires an actual glucose reading, blood pressure, and skinfold
measurement, unlike diabetes-brfss-v2. Six features are used —
Pregnancies, Glucose, BloodPressure, SkinThickness, BMI, Age — dropping
Insulin (48.7% missing in the raw data, the least reliable column by far)
and DiabetesPedigreeFunction (a derived, hard-to-self-report score based
on family history).

Only converts the known physiologically-impossible zero placeholders to
NaN here. Imputation itself deliberately happens inside train.py's sklearn
Pipeline (SimpleImputer fit on the training fold only) — never in this
file — so missing-value statistics can never leak from test rows into
training, unlike some published re-uploads of this dataset that impute
before splitting.
"""

from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).parent / "data" / "raw" / "pima_indians_diabetes.csv"
OUT_DIR = Path(__file__).parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLUMNS = ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "BMI", "Age"]
# Physiologically impossible as a literal 0 — the dataset's well-documented
# missing-value placeholder. Pregnancies and Age are NOT included: 0 is a
# genuine valid value for Pregnancies, and Age has no zero rows anyway.
ZERO_AS_MISSING_COLUMNS = ["Glucose", "BloodPressure", "SkinThickness", "BMI"]


def main():
    df = pd.read_csv(RAW_PATH)
    print(f"Raw rows: {len(df)}")

    out = df[FEATURE_COLUMNS + ["Outcome"]].copy()
    for col in ZERO_AS_MISSING_COLUMNS:
        n_zero = (out[col] == 0).sum()
        out.loc[out[col] == 0, col] = pd.NA
        print(f"{col}: marked {n_zero} zero values as missing ({n_zero / len(out):.1%})")

    duplicates = out.duplicated().sum()
    if duplicates:
        print(f"Dropping {duplicates} exact duplicate rows (leakage prevention)")
        out = out.drop_duplicates()

    out_path = OUT_DIR / "pima_processed.csv"
    out.to_csv(out_path, index=False)

    print(f"\nFinal rows: {len(out)}")
    print(f"Positive rate (Outcome=1): {out['Outcome'].mean():.4f}")
    print(f"Missing values remaining per column (to be imputed in train.py, train-fold-only):")
    print(out[FEATURE_COLUMNS].isna().sum())
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
