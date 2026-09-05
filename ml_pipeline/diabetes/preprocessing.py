"""
Preprocessing for the Pima Indians Diabetes dataset.

Responsibilities (per AGENTS.md Section 7-8):
  - load the raw, untouched dataset and assign real column names
  - run and report data-quality checks (missing values, duplicates,
    invalid records, class imbalance, outliers, label quality)
  - mark the dataset's known biologically-impossible zeros as missing
    (NOT impute them here — imputation is fit inside the model pipeline
    in train.py, using the training split only, to avoid leakage)
  - split into train/test BEFORE any statistic-fitting step
  - write the two splits and a dataset-statistics summary to data/processed/

Run: python preprocessing.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

RAW_PATH = Path(__file__).parent / "data" / "raw" / "pima-diabetes-raw.csv"
PROCESSED_DIR = Path(__file__).parent / "data" / "processed"

COLUMNS = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin",
    "BMI", "DiabetesPedigreeFunction", "Age", "Outcome",
]

# These columns use 0 as a placeholder for "not measured" in this dataset —
# see data/raw/README.md. 0 is not a real value for any of them.
ZERO_AS_MISSING_COLUMNS = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]

TEST_SIZE = 0.2
RANDOM_STATE = 42


def load_raw() -> pd.DataFrame:
    return pd.read_csv(RAW_PATH, header=None, names=COLUMNS)


def run_quality_checks(df: pd.DataFrame) -> dict:
    checks = {}

    checks["row_count"] = int(len(df))
    checks["duplicate_rows"] = int(df.duplicated().sum())

    zero_counts = {col: int((df[col] == 0).sum()) for col in ZERO_AS_MISSING_COLUMNS}
    checks["placeholder_zero_counts"] = zero_counts
    checks["placeholder_zero_pct"] = {
        col: round(100 * count / len(df), 1) for col, count in zero_counts.items()
    }

    checks["invalid_negative_values"] = {
        col: int((df[col] < 0).sum()) for col in COLUMNS if col != "Outcome"
    }

    checks["label_distribution"] = df["Outcome"].value_counts().to_dict()
    checks["label_values_valid"] = bool(df["Outcome"].isin([0, 1]).all())
    checks["label_nulls"] = int(df["Outcome"].isna().sum())

    outlier_counts = {}
    for col in [c for c in COLUMNS if c != "Outcome"]:
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_counts[col] = int(((df[col] < lower) | (df[col] > upper)).sum())
    checks["outlier_counts_iqr"] = outlier_counts

    return checks


def mark_missing(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ZERO_AS_MISSING_COLUMNS:
        df.loc[df[col] == 0, col] = np.nan
    return df


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df = load_raw()
    checks = run_quality_checks(df)

    # Drop exact duplicate rows before splitting — duplicates that straddle
    # the train/test split would otherwise leak test rows into training.
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    checks["duplicates_dropped"] = before - len(df)

    df = mark_missing(df)

    train_df, test_df = train_test_split(
        df, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=df["Outcome"]
    )

    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)

    checks["train_rows"] = int(len(train_df))
    checks["test_rows"] = int(len(test_df))
    checks["train_label_distribution"] = train_df["Outcome"].value_counts().to_dict()
    checks["test_label_distribution"] = test_df["Outcome"].value_counts().to_dict()

    with open(PROCESSED_DIR / "dataset_stats.json", "w") as f:
        json.dump(checks, f, indent=2, default=str)

    print(json.dumps(checks, indent=2, default=str))
    print(f"\nWrote {len(train_df)} train rows and {len(test_df)} test rows to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
