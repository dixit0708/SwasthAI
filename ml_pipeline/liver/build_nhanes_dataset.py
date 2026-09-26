"""
SwasthAI — Liver Disease Risk Model — NHANES dataset builder
==============================================================
Builds a screening-style liver disease risk dataset with ZERO lab/blood-test
features, mirroring ml_pipeline/diabetes's BRFSS design: every predictor here
is something a person can answer from memory or a routine physical exam
(age, sex, BMI, waist circumference, alcohol/smoking/activity habits,
previously-diagnosed diabetes/hypertension) — never a value that requires
having already had blood drawn for an LFT panel.

Source: NHANES (National Health and Nutrition Examination Survey), 3 pooled
cycles — 2013-2014 (H), 2015-2016 (I), 2017-2018 (J) — the three consecutive
cycles in which MCQ160L ("Has a doctor ... ever told you that you had any
kind of liver condition?") was fielded. Files must already be downloaded to
data/nhanes_raw/ (see README in that directory).

Target: MCQ160L, self-reported doctor-diagnosed liver condition (Yes/No).
This is the same self-report design the diabetes model's BRFSS target uses,
not a lab-confirmed diagnosis — see reports/dataset_notes.md for the explicit
trade-off discussion.

All variables are merged within each cycle on SEQN (NHANES's per-respondent
ID, unique only within a cycle — never joined across cycles), then the three
cycles are concatenated. Rows are kept only if the respondent is an adult
(20+, the population MCQ160L was asked of) and answered every feature and
the target unambiguously (i.e. not "Refused"/"Don't know"/missing).
"""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "nhanes_raw"
OUT_DIR = Path(__file__).parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CYCLES = {"H": "2013-2014", "I": "2015-2016", "J": "2017-2018"}

# Columns pulled from each source file (SEQN is the join key, always kept).
COLUMNS = {
    "DEMO": ["SEQN", "RIAGENDR", "RIDAGEYR", "RIDRETH1"],
    "BMX": ["SEQN", "BMXBMI", "BMXWAIST"],
    "ALQ": ["SEQN", "ALQ151"],
    "SMQ": ["SEQN", "SMQ020"],
    "DIQ": ["SEQN", "DIQ010"],
    "BPQ": ["SEQN", "BPQ020"],
    "PAQ": ["SEQN", "PAQ665"],
    "HUQ": ["SEQN", "HUQ010"],
    "MCQ": ["SEQN", "MCQ160L"],
}


def load_cycle(letter: str) -> pd.DataFrame:
    frames = {}
    for prefix, cols in COLUMNS.items():
        path = RAW_DIR / f"{prefix}_{letter}.XPT"
        df = pd.read_sas(path, format="xport")
        frames[prefix] = df[cols]

    merged = frames["DEMO"]
    for prefix in ["BMX", "ALQ", "SMQ", "DIQ", "BPQ", "PAQ", "HUQ", "MCQ"]:
        merged = merged.merge(frames[prefix], on="SEQN", how="inner")

    merged["nhanes_cycle"] = CYCLES[letter]
    return merged


def main():
    pooled = pd.concat([load_cycle(letter) for letter in CYCLES], ignore_index=True)
    print(f"Pooled rows across {len(CYCLES)} cycles (all ages, pre-filter): {len(pooled)}")

    # MCQ160L is only asked of adults 20+; restrict to that population so
    # every row could plausibly have answered every question.
    pooled = pooled[pooled["RIDAGEYR"] >= 20]

    # Target: keep only unambiguous Yes(1)/No(2) answers.
    pooled = pooled[pooled["MCQ160L"].isin([1.0, 2.0])]
    pooled["liver_condition"] = (pooled["MCQ160L"] == 1.0).astype(int)

    # Predictors: drop Refused(7)/Don't know(9)/missing for each Yes-No item,
    # keep only unambiguous Yes(1)/No(2) answers, same rule as the target.
    yes_no_cols = ["ALQ151", "SMQ020", "BPQ020", "PAQ665"]
    for col in yes_no_cols:
        pooled = pooled[pooled[col].isin([1.0, 2.0])]

    # DIQ010 has a third valid answer, Borderline(3) — kept as its own state
    # (not merged into Yes or No) since "borderline diabetes" is a real,
    # different self-report a user can give; only Refused(7)/DK(9)/missing
    # are dropped.
    pooled = pooled[pooled["DIQ010"].isin([1.0, 2.0, 3.0])]

    # HUQ010 (self-rated general health) is a 5-point scale; drop
    # Refused(7)/DK(9)/missing same as every other item.
    pooled = pooled[pooled["HUQ010"].isin([1.0, 2.0, 3.0, 4.0, 5.0])]

    # BMI/waist can be missing if the exam component wasn't completed.
    pooled = pooled.dropna(subset=["BMXBMI", "BMXWAIST", "RIAGENDR", "RIDRETH1"])

    # Build the final, human-readable feature frame.
    race_map = {
        1.0: "Mexican American",
        2.0: "Other Hispanic",
        3.0: "Non-Hispanic White",
        4.0: "Non-Hispanic Black",
        5.0: "Other/Multi-Racial",
    }
    general_health_map = {1.0: "Excellent", 2.0: "Very good", 3.0: "Good", 4.0: "Fair", 5.0: "Poor"}

    out = pd.DataFrame({
        "age_years": pooled["RIDAGEYR"].astype(int),
        "sex": pooled["RIAGENDR"].map({1.0: "Male", 2.0: "Female"}),
        "race_ethnicity": pooled["RIDRETH1"].map(race_map),
        "bmi": pooled["BMXBMI"].astype(float),
        "waist_circumference_cm": pooled["BMXWAIST"].astype(float),
        "general_health": pooled["HUQ010"].map(general_health_map),
        "heavy_alcohol_use": pooled["ALQ151"].map({1.0: "Yes", 2.0: "No"}),
        "smoker": pooled["SMQ020"].map({1.0: "Yes", 2.0: "No"}),
        "diabetes_status": pooled["DIQ010"].map({1.0: "Yes", 2.0: "No", 3.0: "Borderline"}),
        "hypertension": pooled["BPQ020"].map({1.0: "Yes", 2.0: "No"}),
        "physical_activity": pooled["PAQ665"].map({1.0: "Yes", 2.0: "No"}),
        "liver_condition": pooled["liver_condition"],
        "nhanes_cycle": pooled["nhanes_cycle"],
    })

    out_path = OUT_DIR / "nhanes_liver_pooled.csv"
    out.to_csv(out_path, index=False)

    print(f"\nFinal rows after filtering to unambiguous answers: {len(out)}")
    print(f"Positive rate (liver_condition=1): {out['liver_condition'].mean():.4f}")
    print(out['nhanes_cycle'].value_counts())
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
