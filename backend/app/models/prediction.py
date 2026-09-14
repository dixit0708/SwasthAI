from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DiabetesPredictionInput(BaseModel):
    """14-feature CDC BRFSS 2015 contract for diabetes-brfss-v2 — see
    ml_pipeline/diabetes/reports/candidate_assessments.md for why this
    reduced feature set was chosen over the original 21-feature v1 model
    (still preserved, untouched, as ml_pipeline/diabetes/artifacts/
    diabetes_pipeline.pkl + metadata.json) and
    ml_pipeline/diabetes/artifacts/diabetes_metadata_v2.json for the
    trained model's authoritative feature_order. Field names are the BRFSS
    column names in snake_case; values/ranges match exactly what the model
    was trained and validated on.

    This is an in-place update to the existing /predict/diabetes contract
    rather than a parallel v2 route: there is exactly one consumer (this
    repo's own frontend, updated in the same change), so versioned URL
    routing would add complexity with no compatibility benefit. The
    response's model_version field (sourced from metadata, never
    hardcoded) is what actually distinguishes v1 from v2 outputs.

    extra="forbid" rejects any field not listed here at the HTTP layer —
    in particular, a client can never submit the target column
    (Diabetes_binary/Diabetes_012), a family-history field (not supported
    by this model — see reports/family_history_investigation.md), or any
    other unexpected field.
    """
    model_config = ConfigDict(extra="forbid")

    sex: Literal[0, 1] = Field(description="0 = female, 1 = male")
    age: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] = Field(
        description="13-band BRFSS age category (1=18-24 ... 13=80+) — NOT raw age in years"
    )
    bmi: float = Field(ge=10, le=100, description="Body mass index")
    high_bp: Literal[0, 1] = Field(description="Ever told you have high blood pressure")
    high_chol: Literal[0, 1] = Field(description="Ever told you have high cholesterol")
    chol_check: Literal[0, 1] = Field(description="Cholesterol check within the past 5 years")
    heart_disease_or_attack: Literal[0, 1] = Field(description="Coronary heart disease or myocardial infarction")
    phys_activity: Literal[0, 1] = Field(description="Physical activity in past 30 days (excluding job)")
    fruits: Literal[0, 1] = Field(description="Consumes fruit 1 or more times per day")
    hvy_alcohol_consump: Literal[0, 1] = Field(description="Heavy alcohol consumption")
    stroke: Literal[0, 1] = Field(description="Ever told you had a stroke")
    gen_hlth: Literal[1, 2, 3, 4, 5] = Field(description="Self-rated general health: 1=excellent ... 5=poor")
    diff_walk: Literal[0, 1] = Field(description="Serious difficulty walking or climbing stairs")
    smoker: Literal[0, 1] = Field(description="Smoked at least 100 cigarettes in your lifetime")


class RiskPredictionOut(BaseModel):
    risk_level: Literal["screening_negative", "screening_elevated"]
    risk_probability: float
    threshold: float
    is_elevated: bool
    message: str
    model_version: str
    disclaimer: str


class LiverPredictionInput(BaseModel):
    """11-feature, lab-free contract for liver-nhanes-v1, trained on pooled
    NHANES 2013-2014/2015-2016/2017-2018 survey and exam data — see
    ml_pipeline/liver/reports/evaluation_nhanes.md.

    Every field here is something a person can answer from memory or a
    routine physical exam (age, sex, BMI, waist circumference, self-rated
    general health, alcohol/smoking/activity habits, previously-diagnosed
    diabetes/hypertension). None of them require an LFT/blood panel — this
    model is meant to run *before* a lab visit, as a "should you get one"
    screen, unlike the retired liver-ilpd-v1 contract (which required the
    LFT panel itself as input, preserved untouched on disk as the baseline
    at ml_pipeline/liver/artifacts/liver_pipeline.pkl + liver_metadata.json).

    extra="forbid" rejects any field not listed here at the HTTP layer, preventing
    accidental submission of the target column or other unexpected fields.
    """
    model_config = ConfigDict(extra="forbid")

    age_years: int = Field(ge=20, le=120, description="Age in years (model trained on adults 20+)")
    sex: Literal["Male", "Female"] = Field(description="Sex")
    race_ethnicity: Literal[
        "Mexican American", "Other Hispanic", "Non-Hispanic White",
        "Non-Hispanic Black", "Other/Multi-Racial",
    ] = Field(description="Race/ethnicity (NHANES categories)")
    bmi: float = Field(ge=10.0, le=100.0, description="Body mass index")
    waist_circumference_cm: float = Field(ge=30.0, le=250.0, description="Waist circumference in cm")
    general_health: Literal["Excellent", "Very good", "Good", "Fair", "Poor"] = Field(
        description="Self-rated general health"
    )
    heavy_alcohol_use: Literal["Yes", "No"] = Field(
        description="Ever had 4/5 or more alcoholic drinks almost every day in any one year"
    )
    smoker: Literal["Yes", "No"] = Field(description="Smoked at least 100 cigarettes in your lifetime")
    diabetes_status: Literal["Yes", "No", "Borderline"] = Field(
        description="Ever told by a doctor that you have diabetes"
    )
    hypertension: Literal["Yes", "No"] = Field(description="Ever told by a doctor that you have high blood pressure")
    physical_activity: Literal["Yes", "No"] = Field(
        description="Do moderate-intensity recreational physical activity for at least 10 minutes continuously"
    )

