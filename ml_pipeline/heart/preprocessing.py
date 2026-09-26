"""
Preprocessing for the CDC 2022 Heart Disease dataset (heart_2022_no_nans.csv).

Responsibilities:
  - Load the cleaned dataset (NaN rows already removed)
  - Build the composite target: HeartDiseaseRisk
      HadHeartAttack == 'Yes' OR HadAngina == 'Yes'  ->  1, else 0
  - Run and log data-quality checks
  - Encode all features and document mappings
  - Drop exact duplicate rows BEFORE splitting (leakage prevention)
  - Stratified 80/20 split
  - Write train/test CSVs + stats JSON to data/processed/

Encoding decisions:
  Binary Yes/No cols  -> Yes=1, No=0
  Sex                 -> Female=0, Male=1
  GeneralHealth       -> Poor=1 Fair=2 Good=3 Very good=4 Excellent=5
  AgeCategory         -> chronological integer 1-13
  SmokerStatus        -> Never=0 Former=1 Some days=2 Every day=3
  LastCheckupTime     -> <1yr=0  1-2yr=1  2-5yr=2  5+yr=3
  RemovedTeeth        -> None=0  1-5=1  6+notAll=2  All=3
  HadDiabetes         -> Yes=1  everything else=0

Run: python preprocessing.py
"""
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

RAW_PATH     = Path(__file__).parent / "data" / "heart_2022_no_nans.csv"
PROCESSED_DIR = Path(__file__).parent / "data" / "processed"

TARGET_COLUMN = "HeartDiseaseRisk"
RANDOM_STATE  = 42
TEST_SIZE     = 0.2

FEATURE_COLUMNS = [
    "Sex",
    "AgeCategory",
    "BMI",
    "GeneralHealth",
    "PhysicalHealthDays",
    "MentalHealthDays",
    "SleepHours",
    "PhysicalActivities",
    "HadStroke",
    "HadAsthma",
    "HadCOPD",
    "HadDepressiveDisorder",
    "HadKidneyDisease",
    "HadArthritis",
    "HadDiabetes",
    "DifficultyWalking",
    "DifficultyConcentrating",
    "DifficultyErrands",
    "SmokerStatus",
    "AlcoholDrinkers",
    "ChestScan",
    "HighRiskLastYear",
    "RemovedTeeth",
    "LastCheckupTime",
]

GENERAL_HEALTH_MAP = {
    "Poor": 1, "Fair": 2, "Good": 3, "Very good": 4, "Excellent": 5,
}

AGE_CATEGORY_MAP = {
    "Age 18 to 24": 1,  "Age 25 to 29": 2,  "Age 30 to 34": 3,
    "Age 35 to 39": 4,  "Age 40 to 44": 5,  "Age 45 to 49": 6,
    "Age 50 to 54": 7,  "Age 55 to 59": 8,  "Age 60 to 64": 9,
    "Age 65 to 69": 10, "Age 70 to 74": 11, "Age 75 to 79": 12,
    "Age 80 or older": 13,
}

SMOKER_STATUS_MAP = {
    "Never smoked": 0,
    "Former smoker": 1,
    "Current smoker - now smokes some days": 2,
    "Current smoker - now smokes every day": 3,
}

LAST_CHECKUP_MAP = {
    "Within past year (anytime less than 12 months ago)":        0,
    "Within past 2 years (1 year but less than 2 years ago)":   1,
    "Within past 5 years (2 years but less than 5 years ago)":  2,
    "5 or more years ago":                                       3,
}

REMOVED_TEETH_MAP = {
    "None of them": 0, "1 to 5": 1, "6 or more, but not all": 2, "All": 3,
}

BINARY_YES_NO_COLS = [
    "PhysicalActivities", "HadStroke", "HadAsthma", "HadCOPD",
    "HadDepressiveDisorder", "HadKidneyDisease", "HadArthritis",
    "DifficultyConcentrating", "DifficultyWalking", "DifficultyErrands",
    "AlcoholDrinkers", "ChestScan", "HighRiskLastYear",
]


def build_target(df: pd.DataFrame) -> pd.Series:
    """HeartDiseaseRisk = 1 if HadHeartAttack OR HadAngina == 'Yes'."""
    return ((df["HadHeartAttack"] == "Yes") | (df["HadAngina"] == "Yes")).astype(int)


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in BINARY_YES_NO_COLS:
        if col in df.columns:
            df[col] = (df[col] == "Yes").astype(int)
    df["Sex"]            = (df["Sex"] == "Male").astype(int)
    df["GeneralHealth"]  = df["GeneralHealth"].map(GENERAL_HEALTH_MAP)
    df["AgeCategory"]    = df["AgeCategory"].map(AGE_CATEGORY_MAP)
    df["SmokerStatus"]   = df["SmokerStatus"].map(SMOKER_STATUS_MAP)
    df["LastCheckupTime"] = df["LastCheckupTime"].map(LAST_CHECKUP_MAP)
    df["RemovedTeeth"]   = df["RemovedTeeth"].map(REMOVED_TEETH_MAP)
    # HadDiabetes: only explicit "Yes" -> 1; pre-diabetes/pregnancy -> 0
    df["HadDiabetes"]    = (df["HadDiabetes"] == "Yes").astype(int)
    return df


def run_quality_checks(df_raw: pd.DataFrame, df_enc: pd.DataFrame,
                       target: pd.Series) -> dict:
    checks: dict = {}
    checks["raw_row_count"]     = int(len(df_raw))
    checks["null_count_raw"]    = int(df_raw.isna().sum().sum())
    checks["duplicate_rows_raw"] = int(df_raw.duplicated().sum())
    checks["target_distribution"] = {
        "0_no_risk":           int((target == 0).sum()),
        "1_heart_disease_risk": int((target == 1).sum()),
        "positive_rate_pct":   round(float(target.mean() * 100), 2),
    }
    checks["hadheartattack_yes"] = int((df_raw["HadHeartAttack"] == "Yes").sum())
    checks["hadangina_yes"]      = int((df_raw["HadAngina"] == "Yes").sum())
    checks["both_yes"]           = int(
        ((df_raw["HadHeartAttack"] == "Yes") & (df_raw["HadAngina"] == "Yes")).sum()
    )
    checks["encoded_nulls"] = {col: int(df_enc[col].isna().sum()) for col in FEATURE_COLUMNS}
    checks["bmi_stats"] = {
        "min":  round(float(df_enc["BMI"].min()), 2),
        "max":  round(float(df_enc["BMI"].max()), 2),
        "mean": round(float(df_enc["BMI"].mean()), 2),
        "q25":  round(float(df_enc["BMI"].quantile(0.25)), 2),
        "q75":  round(float(df_enc["BMI"].quantile(0.75)), 2),
    }
    return checks


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading dataset …")
    df_raw = pd.read_csv(RAW_PATH)
    print(f"  Raw shape: {df_raw.shape}")

    target = build_target(df_raw)
    df_raw[TARGET_COLUMN] = target

    print("Encoding features …")
    df_enc = encode_features(df_raw)

    checks = run_quality_checks(df_raw, df_enc, target)
    print(f"  Positive rate: {checks['target_distribution']['positive_rate_pct']}%")

    df_model = df_enc[FEATURE_COLUMNS + [TARGET_COLUMN]].copy()

    before = len(df_model)
    df_model = df_model.drop_duplicates().reset_index(drop=True)
    checks["duplicates_dropped"] = before - len(df_model)
    checks["post_dedup_rows"]    = int(len(df_model))
    print(f"  Dropped {checks['duplicates_dropped']} duplicates; {len(df_model)} rows remain.")

    train_df, test_df = train_test_split(
        df_model, test_size=TEST_SIZE, random_state=RANDOM_STATE,
        stratify=df_model[TARGET_COLUMN],
    )
    checks["train_rows"] = int(len(train_df))
    checks["test_rows"]  = int(len(test_df))
    checks["train_label_distribution"] = (
        train_df[TARGET_COLUMN].value_counts().sort_index().to_dict()
    )
    checks["test_label_distribution"] = (
        test_df[TARGET_COLUMN].value_counts().sort_index().to_dict()
    )

    train_df.to_csv(PROCESSED_DIR / "heart_train.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "heart_test.csv",  index=False)

    with open(PROCESSED_DIR / "heart_dataset_stats.json", "w") as f:
        json.dump(checks, f, indent=2, default=str)

    print(json.dumps(checks, indent=2, default=str))
    print(f"\nWrote {len(train_df)} train rows + {len(test_df)} test rows to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
