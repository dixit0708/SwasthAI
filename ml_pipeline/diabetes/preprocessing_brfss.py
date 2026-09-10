"""
Preprocessing for the CDC BRFSS 2015 Diabetes Health Indicators dataset.

Responsibilities (same leakage-prevention pattern as preprocessing.py, the
Pima pipeline's preprocessing script):
  - load the raw, untouched primary dataset (see data/raw/README_brfss2015.md
    for why this file, not the other two, was chosen as primary)
  - run and report data-quality checks
  - drop exact duplicate rows BEFORE splitting (this dataset has no
    zero-as-missing placeholder issue like Pima does, so there is no
    missing-value marking step here — every 0 is a genuine survey answer)
  - split into train/test before any statistic-fitting step
  - write the two splits and a dataset-statistics summary to data/processed/

Run: python preprocessing_brfss.py
"""
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

RAW_PATH = Path(__file__).parent / "data" / "raw" / "brfss2015-diabetes-binary.csv"
PROCESSED_DIR = Path(__file__).parent / "data" / "processed"

TARGET_COLUMN = "Diabetes_binary"
FEATURE_COLUMNS = [
    "HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke",
    "HeartDiseaseorAttack", "PhysActivity", "Fruits", "Veggies",
    "HvyAlcoholConsump", "AnyHealthcare", "NoDocbcCost", "GenHlth",
    "MentHlth", "PhysHlth", "DiffWalk", "Sex", "Age", "Education", "Income",
]

TEST_SIZE = 0.2
RANDOM_STATE = 42


def load_raw() -> pd.DataFrame:
    return pd.read_csv(RAW_PATH)


def run_quality_checks(df: pd.DataFrame) -> dict:
    checks = {}

    checks["row_count"] = int(len(df))
    checks["null_count"] = int(df.isna().sum().sum())
    checks["duplicate_rows"] = int(df.duplicated().sum())

    checks["invalid_negative_values"] = {
        col: int((df[col] < 0).sum()) for col in FEATURE_COLUMNS
    }

    checks["label_distribution"] = df[TARGET_COLUMN].value_counts().to_dict()
    checks["label_values_valid"] = bool(df[TARGET_COLUMN].isin([0, 1]).all())
    checks["label_nulls"] = int(df[TARGET_COLUMN].isna().sum())

    q1, q3 = df["BMI"].quantile(0.25), df["BMI"].quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    checks["bmi_outlier_count_iqr"] = int(((df["BMI"] < lower) | (df["BMI"] > upper)).sum())

    return checks


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df = load_raw()
    checks = run_quality_checks(df)

    # Drop exact duplicate rows before splitting — see
    # data/raw/README_brfss2015.md for why this dataset has many legitimate
    # duplicate rows (low-cardinality survey columns, large sample), and why
    # they are still dropped pre-split to prevent train/test leakage.
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    checks["duplicates_dropped"] = before - len(df)

    train_df, test_df = train_test_split(
        df, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=df[TARGET_COLUMN]
    )

    train_df.to_csv(PROCESSED_DIR / "brfss_train.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "brfss_test.csv", index=False)

    checks["train_rows"] = int(len(train_df))
    checks["test_rows"] = int(len(test_df))
    checks["train_label_distribution"] = train_df[TARGET_COLUMN].value_counts().to_dict()
    checks["test_label_distribution"] = test_df[TARGET_COLUMN].value_counts().to_dict()

    with open(PROCESSED_DIR / "brfss_dataset_stats.json", "w") as f:
        json.dump(checks, f, indent=2, default=str)

    print(json.dumps(checks, indent=2, default=str))
    print(f"\nWrote {len(train_df)} train rows and {len(test_df)} test rows to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
