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
    """10-feature Indian Liver Patient Dataset (ILPD) contract for liver-ilpd-v1.

    Features are the actual column names from Indian_Liver_Patient_549_Clean_Dataset.xlsx
    (cleaned ILPD). All values are in the units shown in the column names.

    extra="forbid" rejects any field not listed here at the HTTP layer, preventing
    accidental submission of the target column or other unexpected fields.
    """
    model_config = ConfigDict(extra="forbid")

    age_years: int = Field(ge=1, le=120, description="Patient age in years")
    gender: Literal["Male", "Female"] = Field(description="Patient gender")
    total_bilirubin_mg_dl: float = Field(
        ge=0.1, le=100.0,
        description="Total bilirubin in mg/dL (normal range: 0.2–1.2 mg/dL)"
    )
    direct_bilirubin_mg_dl: float = Field(
        ge=0.0, le=50.0,
        description="Direct (conjugated) bilirubin in mg/dL (normal: 0.0–0.3 mg/dL)"
    )
    alkaline_phosphatase_u_l: int = Field(
        ge=10, le=5000,
        description="Alkaline Phosphatase enzyme level in U/L (normal: 44–147 U/L)"
    )
    alanine_aminotransferase_u_l: int = Field(
        ge=1, le=10000,
        description="Alanine Aminotransferase (ALT/SGPT) in U/L (normal: 7–56 U/L)"
    )
    aspartate_aminotransferase_u_l: int = Field(
        ge=1, le=10000,
        description="Aspartate Aminotransferase (AST/SGOT) in U/L (normal: 10–40 U/L)"
    )
    total_proteins_g_dl: float = Field(
        ge=1.0, le=12.0,
        description="Total protein concentration in g/dL (normal: 6.0–8.3 g/dL)"
    )
    albumin_g_dl: float = Field(
        ge=0.5, le=6.0,
        description="Albumin in g/dL (normal: 3.5–5.0 g/dL)"
    )
    albumin_globulin_ratio: float = Field(
        ge=0.1, le=10.0,
        description="Albumin/Globulin ratio (normal: 1.0–2.5)"
    )

