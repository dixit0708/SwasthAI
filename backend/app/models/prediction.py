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

    A candidate v2 (general_health removed) was trained and evaluated —
    see ml_pipeline/liver/reports/v2_general_health_removal.md — but NOT
    adopted: it had a real, measured cost (ROC-AUC 0.748->0.719, false
    positives up ~7pp), and the same removal caused a much larger
    regression on the sibling diabetes model, so the decision was reverted
    for both models for consistency. general_health remains in production.

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


class DiabetesPimaPredictionInput(BaseModel):
    """6-feature contract for diabetes-pima-v1, trained on the Pima Indians
    Diabetes Database (NIDDK/UCI, Smith et al. 1988) — see
    ml_pipeline/diabetes_pima/reports/evaluation.md.

    INDEPENDENT of DiabetesPredictionInput (diabetes-brfss-v2) above: a
    second, separate model. This is the "I have recent lab results"
    counterpart to the lab-free BRFSS model — it requires an actual
    glucose reading, blood pressure, and skinfold measurement, not
    something answerable from memory. Offered as the alternative path for
    users who already have labs, routed to from the same UI entry point as
    the lab-free assessment.

    Trained on a narrow population (female, Pima Indian heritage, age
    21+) — see the evaluation report before presenting this model's output
    as equally applicable to every user.

    extra="forbid" rejects any field not listed here at the HTTP layer.
    """
    model_config = ConfigDict(extra="forbid")

    pregnancies: int = Field(ge=0, le=20, description="Number of times pregnant")
    glucose: float = Field(
        ge=40.0, le=300.0, description="Plasma glucose concentration, 2-hour oral glucose tolerance test, mg/dL"
    )
    blood_pressure: float = Field(ge=20.0, le=200.0, description="Diastolic blood pressure, mmHg")
    skin_thickness: float = Field(ge=5.0, le=100.0, description="Triceps skinfold thickness, mm")
    bmi: float = Field(ge=10.0, le=80.0, description="Body mass index")
    age: int = Field(ge=18, le=120, description="Age in years")


class LiverIlpdPredictionInput(BaseModel):
    """10-feature, lab-based contract for liver-ilpd-logistic-v1, trained on
    the canonical UCI ILPD (Indian Liver Patient Dataset, 583 rows) — see
    ml_pipeline/liver/reports/ilpd_final_model_report.md for the full
    methodology and cross-validated metrics.

    INDEPENDENT of LiverPredictionInput above (liver-nhanes-v1, lab-free):
    a second, separate model. This is the "I have my lab report"
    counterpart — it requires an actual Liver Function Test (LFT) panel,
    not something answerable from memory. Explicitly NOT built from the
    rejected 30,691-row "LPD" dataset (see
    ml_pipeline/liver_lpd/reports/data_integrity_investigation.md), whose
    labels showed strong evidence of being synthetically/rule-generated.

    Every numeric field except age may be submitted as null: the
    underlying pipeline's SimpleImputer (median, fit at training time on
    the full cleaned 570-row dataset) is designed to supply a missing
    individual lab value — this is a validated pipeline capability, not a
    silent fallback for malformed input. A present-but-invalid value
    (wrong type, out of range) is still rejected, and a required field
    that is entirely absent from the request still fails validation.

    Trained on a narrow, single-region population (Northeast Andhra
    Pradesh, India; 441 male / 142 female in the raw file, 570 usable rows
    after cleaning) — see the final model report before presenting this
    model's output as equally applicable to every user.

    extra="forbid" rejects any field not listed here at the HTTP layer —
    in particular, a client can never submit the target column (Selector),
    an internal training field, a model metadata field, or an arbitrary
    additional clinical variable this model was not trained on.
    """
    model_config = ConfigDict(extra="forbid")

    age: int = Field(ge=1, le=120, description="Age in years")
    gender: Literal["Male", "Female"] = Field(description="Gender")
    total_bilirubin: Optional[float] = Field(None, ge=0.1, le=100.0, description="Total Bilirubin, mg/dL")
    direct_bilirubin: Optional[float] = Field(None, ge=0.05, le=30.0, description="Direct Bilirubin, mg/dL")
    alkaline_phosphatase: Optional[float] = Field(
        None, ge=20.0, le=3000.0, description="Alkaline Phosphatase, U/L"
    )
    alt_sgpt: Optional[float] = Field(
        None, ge=5.0, le=3000.0, description="Alanine Aminotransferase (ALT/SGPT), U/L"
    )
    ast_sgot: Optional[float] = Field(
        None, ge=5.0, le=6000.0, description="Aspartate Aminotransferase (AST/SGOT), U/L"
    )
    total_proteins: Optional[float] = Field(None, ge=2.0, le=12.0, description="Total Proteins, g/dL")
    albumin: Optional[float] = Field(None, ge=0.5, le=7.0, description="Albumin, g/dL")
    albumin_globulin_ratio: Optional[float] = Field(
        None, ge=0.1, le=4.0, description="Albumin/Globulin Ratio"
    )

