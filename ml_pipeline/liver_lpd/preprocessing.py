"""
SwasthAI — Liver Disease Risk Model (Lab-Based / LPD) — dataset preparation
============================================================================
Cleans the raw "Liver Patient Dataset (LPD)" CSV (data/raw/README.md has
provenance) into a leakage-checked, documented processed CSV for
train.py. This is the deliberate "I have my lab report" counterpart to
ml_pipeline/liver/train_nhanes.py (lab-free), reusing the exact same
feature-naming convention as the retired ml_pipeline/liver/train.py
(liver-ilpd-v1) since it's the same underlying panel (Total Bilirubin,
Direct Bilirubin, Alkaline Phosphatase, ALT, AST, Total Proteins, Albumin,
A/G Ratio, Age, Gender), just a much larger (and messier) source file.

Runs the AGENTS.md Section 7 checklist explicitly and prints every number
so nothing here is asserted without evidence:
  - missing values (per column)
  - duplicates (found: 11,323 exact full-row duplicates out of 30,691 —
    see data/raw/README.md; dropped BEFORE any split, never just before
    reporting metrics, so no duplicate row can land in two different
    splits)
  - invalid records (out-of-range age, unrecognized gender values)
  - class imbalance
  - basic outlier/range summary per numeric column (reported, not
    stripped — see reports/evaluation.md for why)
"""
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent
RAW_PATH = BASE / "data" / "raw" / "liver_patient_dataset_lpd.csv"
PROCESSED_PATH = BASE / "data" / "processed" / "liver_lpd_processed.csv"

COLUMN_RENAME = {
    "Age of the patient": "age_years",
    "Gender of the patient": "gender",
    "Total Bilirubin": "total_bilirubin_mg_dl",
    "Direct Bilirubin": "direct_bilirubin_mg_dl",
    "\xa0Alkphos Alkaline Phosphotase": "alkaline_phosphatase_u_l",
    "\xa0Sgpt Alamine Aminotransferase": "alanine_aminotransferase_u_l",
    "Sgot Aspartate Aminotransferase": "aspartate_aminotransferase_u_l",
    "Total Protiens": "total_proteins_g_dl",
    "\xa0ALB Albumin": "albumin_g_dl",
    "A/G Ratio Albumin and Globulin Ratio": "albumin_globulin_ratio",
    "Result": "liver_disease_status",
}

FEATURE_COLUMNS = [
    "age_years", "gender", "total_bilirubin_mg_dl", "direct_bilirubin_mg_dl",
    "alkaline_phosphatase_u_l", "alanine_aminotransferase_u_l",
    "aspartate_aminotransferase_u_l", "total_proteins_g_dl", "albumin_g_dl",
    "albumin_globulin_ratio",
]
TARGET_COLUMN = "liver_disease_status"


def main():
    df = pd.read_csv(RAW_PATH, encoding="latin1")
    df = df.rename(columns=COLUMN_RENAME)
    missing_expected = [c for c in COLUMN_RENAME.values() if c not in df.columns]
    if missing_expected:
        raise ValueError(f"Raw file is missing expected column(s) after rename: {missing_expected}")

    print(f"Raw rows: {len(df)}")

    # --- Duplicates (checked BEFORE any cleaning, on the raw column set) ---
    n_dupes = df.duplicated().sum()
    print(f"Exact full-row duplicates: {n_dupes} ({n_dupes / len(df):.1%})")
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Rows after dropping duplicates: {len(df)}")

    # --- Missing values ---
    print("\nMissing values per column (post-dedup):")
    print(df[FEATURE_COLUMNS + [TARGET_COLUMN]].isna().sum().to_string())

    # --- Target mapping: raw encodes 1=liver patient, 2=not a liver patient ---
    df[TARGET_COLUMN] = df[TARGET_COLUMN].map({1: 1, 2: 0})
    n_bad_target = df[TARGET_COLUMN].isna().sum()
    if n_bad_target:
        print(f"\nDropping {n_bad_target} row(s) with an unrecognized target value")
        df = df.dropna(subset=[TARGET_COLUMN])

    # --- Gender: standardize casing, drop unrecognized values ---
    df["gender"] = df["gender"].astype(str).str.strip().str.title()
    valid_gender = {"Male", "Female"}
    n_bad_gender = (~df["gender"].isin(valid_gender)).sum()
    print(f"\nRows with unrecognized/missing gender: {n_bad_gender}")

    # --- Age: drop clearly invalid values (<=0 or >120) ---
    n_bad_age = ((df["age_years"] <= 0) | (df["age_years"] > 120) | df["age_years"].isna()).sum()
    print(f"Rows with invalid age (<=0, >120, or missing): {n_bad_age}")

    # --- Drop any row missing a required feature or an invalid categorical ---
    df = df[df["gender"].isin(valid_gender)]
    df = df.dropna(subset=FEATURE_COLUMNS)
    df = df[(df["age_years"] > 0) & (df["age_years"] <= 120)]
    print(f"\nRows after dropping missing/invalid: {len(df)}")

    # --- Basic range summary (reported, not stripped as outliers — real
    # liver-disease patients can have extreme lab values; a hardcoded upper
    # cutoff would risk removing exactly the cases this model exists to
    # catch, which AGENTS.md Section 9 would call artificially improving
    # metrics by discarding the hard examples) ---
    print("\nNumeric feature ranges (post-cleaning):")
    numeric_cols = [c for c in FEATURE_COLUMNS if c != "gender"]
    print(df[numeric_cols].describe().T[["min", "25%", "50%", "75%", "max"]].to_string())

    print("\nGender distribution:")
    print(df["gender"].value_counts().to_string())

    print("\nClass balance (liver_disease_status):")
    print(df[TARGET_COLUMN].value_counts().to_string())
    print(f"Positive rate: {df[TARGET_COLUMN].mean():.4f}")

    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)
    df = df[FEATURE_COLUMNS + [TARGET_COLUMN]]

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)
    print(f"\nSaved cleaned dataset -> {PROCESSED_PATH} ({len(df)} rows)")


if __name__ == "__main__":
    main()
