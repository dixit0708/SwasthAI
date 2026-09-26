from typing import Literal, Optional

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



# ---------------------------------------------------------------------------
# Heart Disease Risk — 24-feature CDC 2022 contract
# (ml_pipeline/heart/artifacts/heart_metadata.json is the authoritative source
#  for feature_order and decision_threshold; this schema's field names mirror
#  the preprocessing.py encoding keys 1-to-1 so the service layer can build
#  the feature vector without any secondary name mapping).
# ---------------------------------------------------------------------------

class HeartPredictionInput(BaseModel):
    """24-feature CDC BRFSS 2022 contract for heart-cdc2022-v1.

    All categorical inputs are accepted as the raw human-readable strings
    that the frontend dropdowns will send; the service layer encodes them
    into the integer representation the model was trained on using the same
    mapping dictionaries copied from ml_pipeline/heart/preprocessing.py.

    extra="forbid" ensures the target columns (HadHeartAttack, HadAngina,
    HeartDiseaseRisk) and any unexpected field cannot be submitted.
    """
    model_config = ConfigDict(extra="forbid")

    # ---- Demographics ----
    sex: Literal["Female", "Male"] = Field(
        description="Biological sex"
    )
    age_category: Literal[
        "Age 18 to 24", "Age 25 to 29", "Age 30 to 34", "Age 35 to 39",
        "Age 40 to 44", "Age 45 to 49", "Age 50 to 54", "Age 55 to 59",
        "Age 60 to 64", "Age 65 to 69", "Age 70 to 74", "Age 75 to 79",
        "Age 80 or older",
    ] = Field(description="5-year age band")

    # ---- Body metrics ----
    bmi: float = Field(ge=10.0, le=100.0, description="Body mass index (kg/m²)")

    # ---- General health ----
    general_health: Optional[Literal["Poor", "Fair", "Good", "Very good", "Excellent"]] = Field(
        default="Good", description="Self-rated general health"
    )
    physical_health_days: float = Field(
        ge=0, le=30,
        description="Days of poor physical health in the past 30 days",
    )
    mental_health_days: float = Field(
        ge=0, le=30,
        description="Days of poor mental health in the past 30 days",
    )
    sleep_hours: float = Field(
        ge=1, le=24,
        description="Average hours of sleep per 24-hour period",
    )

    # ---- Lifestyle ----
    physical_activities: Literal["Yes", "No"] = Field(
        description="Physical activity or exercise outside of work in the past 30 days"
    )
    smoker_status: Literal[
        "Never smoked",
        "Former smoker",
        "Current smoker - now smokes some days",
        "Current smoker - now smokes every day",
    ] = Field(description="Smoking status")
    alcohol_drinkers: Literal["Yes", "No"] = Field(
        description="Had at least one drink of alcohol in the past 30 days"
    )

    # ---- Medical history ----
    had_stroke: Literal["Yes", "No"] = Field(description="Ever told you had a stroke")
    had_asthma: Literal["Yes", "No"] = Field(description="Ever told you had asthma")
    had_copd: Literal["Yes", "No"] = Field(
        description="Ever told you had COPD, emphysema, or chronic bronchitis"
    )
    had_depressive_disorder: Literal["Yes", "No"] = Field(
        description="Ever told you had a depressive disorder"
    )
    had_kidney_disease: Literal["Yes", "No"] = Field(
        description="Ever told you had kidney disease (excluding kidney stones/bladder infection)"
    )
    had_arthritis: Literal["Yes", "No"] = Field(
        description="Ever told you had some form of arthritis, rheumatoid arthritis, gout, or lupus"
    )
    had_diabetes: Literal["Yes", "No", "Yes, but only during pregnancy (female)",
                           "No, pre-diabetes or borderline diabetes"] = Field(
        description="Ever told you had diabetes (Yes encodes to 1; all other responses encode to 0)"
    )

    # ---- Functional difficulties ----
    difficulty_walking: Literal["Yes", "No"] = Field(
        description="Serious difficulty walking or climbing stairs"
    )
    difficulty_concentrating: Literal["Yes", "No"] = Field(
        description="Difficulty concentrating, remembering, or making decisions"
    )
    difficulty_errands: Literal["Yes", "No"] = Field(
        description="Difficulty doing errands alone such as shopping or visiting a doctor"
    )

    # ---- Preventive / other ----
    chest_scan: Literal["Yes", "No"] = Field(
        description="Ever had a CT or CAT scan of your chest area"
    )
    high_risk_last_year: Literal["Yes", "No"] = Field(
        description="HIV high-risk behaviour in the past 12 months"
    )
    removed_teeth: Literal[
        "None of them", "1 to 5", "6 or more, but not all", "All"
    ] = Field(description="How many of your permanent teeth have been removed")
    last_checkup_time: Literal[
        "Within past year (anytime less than 12 months ago)",
        "Within past 2 years (1 year but less than 2 years ago)",
        "Within past 5 years (2 years but less than 5 years ago)",
        "5 or more years ago",
    ] = Field(description="About how long has it been since your last routine checkup")


class HeartRiskPredictionOut(BaseModel):
    """Response contract for /predict/heart.  Mirrors RiskPredictionOut but
    uses heart-specific risk_level literals so the frontend can distinguish
    the two endpoints unambiguously.

    Clinical overlay fields are included when the clinical rule engine applies
    a floor above the raw model probability.  They are always present in the
    response (None / [] / False when no overlay fired) so the frontend can
    conditionally surface a clinical context notice to the user.
    """
    risk_level: Literal["screening_negative", "screening_elevated"]
    risk_probability: float          # adjusted probability (after overlay)
    threshold: float
    is_elevated: bool
    message: str
    model_version: str
    disclaimer: str

    # ---- Clinical overlay fields (always present, None/[] when no overlay) ----
    model_probability: Optional[float] = None    # raw XGBoost score pre-overlay
    clinical_tier: Optional[int] = None          # None, 1, or 2
    clinical_flags: Optional[list] = None        # human-readable rule descriptions
    overlay_applied: Optional[bool] = None       # True only if floor was binding

class HeartClinicalInput(BaseModel):
    """8-feature CDC NHANES clinical contract."""
    model_config = ConfigDict(extra="forbid")
    age: float = Field(ge=18, le=120, description="Age in years")
    systolic_bp: float = Field(ge=60, le=250, description="Systolic blood pressure (mmHg)")
    diastolic_bp: float = Field(ge=30, le=150, description="Diastolic blood pressure (mmHg)")
    total_cholesterol: float = Field(ge=50, le=600, description="Total cholesterol (mg/dL)")
    hdl_cholesterol: float = Field(ge=10, le=200, description="HDL cholesterol (mg/dL)")
    fasting_glucose: float = Field(ge=40, le=500, description="Fasting glucose (mg/dL)")
    pulse: float = Field(ge=30, le=200, description="60-sec heart rate (bpm)")
    bmi: float = Field(ge=10, le=100, description="Body Mass Index (kg/m^2)")

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


