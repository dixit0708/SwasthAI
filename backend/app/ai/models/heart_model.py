"""
Production loader and inference helper for the Heart Disease Risk model
(heart-cdc2022-v2-smote — see ml_pipeline/heart/artifacts/heart_metadata.json).

Mirrors the structure of diabetes_model.py:
  - load_heart_model()   -> (pipeline, metadata)
  - predict_heart()      -> {risk_probability, threshold, is_elevated}

The feature-encoding dictionaries here are an intentional copy of those in
ml_pipeline/heart/preprocessing.py.  Production inference must NOT import
from ml_pipeline/ (AGENTS.md §13); keeping the copy in sync is the
developer's responsibility when the preprocessing encoding ever changes.

Threshold note: the model was trained on SMOTE-balanced data (50% positive).
The decision_threshold in metadata has been corrected to 0.10 for the real-
world test distribution (~8.84% positive) to maintain recall >= 0.80, which
is the clinically appropriate operating point for a cardiac screening tool.
"""
import json
from pathlib import Path
from typing import Tuple

import joblib

# ---------------------------------------------------------------------------
# Encoding maps — must stay in sync with ml_pipeline/heart/preprocessing.py
# ---------------------------------------------------------------------------
_SEX_MAP = {"Female": 0, "Male": 1}

_GENERAL_HEALTH_MAP = {
    "Poor": 1, "Fair": 2, "Good": 3, "Very good": 4, "Excellent": 5,
}

_AGE_CATEGORY_MAP = {
    "Age 18 to 24": 1,  "Age 25 to 29": 2,  "Age 30 to 34": 3,
    "Age 35 to 39": 4,  "Age 40 to 44": 5,  "Age 45 to 49": 6,
    "Age 50 to 54": 7,  "Age 55 to 59": 8,  "Age 60 to 64": 9,
    "Age 65 to 69": 10, "Age 70 to 74": 11, "Age 75 to 79": 12,
    "Age 80 or older": 13,
}

_SMOKER_STATUS_MAP = {
    "Never smoked": 0,
    "Former smoker": 1,
    "Current smoker - now smokes some days": 2,
    "Current smoker - now smokes every day": 3,
}

_LAST_CHECKUP_MAP = {
    "Within past year (anytime less than 12 months ago)":       0,
    "Within past 2 years (1 year but less than 2 years ago)":  1,
    "Within past 5 years (2 years but less than 5 years ago)": 2,
    "5 or more years ago":                                      3,
}

_REMOVED_TEETH_MAP = {
    "None of them": 0, "1 to 5": 1, "6 or more, but not all": 2, "All": 3,
}

# Features whose raw string value is "Yes" → 1, anything else → 0
_BINARY_YES_NO = {
    "PhysicalActivities", "HadStroke", "HadAsthma", "HadCOPD",
    "HadDepressiveDisorder", "HadKidneyDisease", "HadArthritis",
    "DifficultyWalking", "DifficultyConcentrating", "DifficultyErrands",
    "AlcoholDrinkers", "ChestScan", "HighRiskLastYear",
}

# Authoritative feature order — matches metadata feature_order exactly
FEATURE_ORDER = [
    "Sex", "AgeCategory", "BMI", "GeneralHealth",
    "PhysicalHealthDays", "MentalHealthDays", "SleepHours",
    "PhysicalActivities", "HadStroke", "HadAsthma", "HadCOPD",
    "HadDepressiveDisorder", "HadKidneyDisease", "HadArthritis",
    "HadDiabetes", "DifficultyWalking", "DifficultyConcentrating",
    "DifficultyErrands", "SmokerStatus", "AlcoholDrinkers",
    "ChestScan", "HighRiskLastYear", "RemovedTeeth", "LastCheckupTime",
]

REQUIRED_METADATA_FIELDS = [
    "model_version", "feature_order", "decision_threshold",
    "calibration_method", "target_column",
]


def load_heart_model(pipeline_path, metadata_path) -> Tuple[object, dict]:
    """Load the fitted sklearn Pipeline and its metadata JSON.

    Raises clearly on any missing or malformed piece rather than guessing
    defaults (same contract as load_diabetes_model).
    """
    pipeline_path = Path(pipeline_path)
    metadata_path = Path(metadata_path)

    if not pipeline_path.exists():
        raise FileNotFoundError(
            f"Heart disease model artifact not found at {pipeline_path}"
        )
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Heart disease model metadata not found at {metadata_path}"
        )

    with open(metadata_path) as f:
        metadata = json.load(f)

    missing = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
    if missing:
        raise ValueError(
            f"Heart model metadata is missing required field(s): {missing}"
        )

    feature_order = metadata["feature_order"]
    if not isinstance(feature_order, list) or not feature_order:
        raise ValueError("Heart model metadata's 'feature_order' must be a non-empty list")

    threshold = metadata["decision_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) \
            or not (0.0 < threshold < 1.0):
        raise ValueError(
            f"Heart model metadata's 'decision_threshold' must be a number in (0, 1), "
            f"got {threshold!r}"
        )

    pipeline = joblib.load(pipeline_path)

    # Cross-check artifact vs metadata feature count
    scaler = getattr(pipeline, "named_steps", {}).get("scaler")
    n_expected = getattr(scaler, "n_features_in_", None)
    if n_expected is not None and n_expected != len(feature_order):
        raise ValueError(
            f"Heart artifact/metadata mismatch: fitted pipeline expects {n_expected} "
            f"features but metadata['feature_order'] lists {len(feature_order)}"
        )

    return pipeline, metadata


def encode_heart_features(raw: dict) -> dict:
    """Convert the raw string-valued dict (as received from the API request)
    into the integer/float dict the model was trained on.

    raw keys use the preprocessing.py column names (PascalCase, e.g. 'Sex',
    'AgeCategory', 'HadStroke'), NOT the Pydantic snake_case field names.
    The service layer is responsible for that mapping before calling here.

    Raises ValueError on any unrecognised categorical value so the caller
    gets a 422-equivalent error rather than a silent NaN reaching the model.
    """
    encoded: dict = {}

    # Sex
    sex_val = raw["Sex"]
    if sex_val not in _SEX_MAP:
        raise ValueError(f"Unrecognised Sex value: {sex_val!r}")
    encoded["Sex"] = _SEX_MAP[sex_val]

    # AgeCategory
    age_val = raw["AgeCategory"]
    if age_val not in _AGE_CATEGORY_MAP:
        raise ValueError(f"Unrecognised AgeCategory value: {age_val!r}")
    encoded["AgeCategory"] = _AGE_CATEGORY_MAP[age_val]

    # BMI / continuous
    encoded["BMI"] = float(raw["BMI"])

    # GeneralHealth
    gh_val = raw["GeneralHealth"]
    if gh_val not in _GENERAL_HEALTH_MAP:
        raise ValueError(f"Unrecognised GeneralHealth value: {gh_val!r}")
    encoded["GeneralHealth"] = _GENERAL_HEALTH_MAP[gh_val]

    # Continuous numeric
    encoded["PhysicalHealthDays"] = float(raw["PhysicalHealthDays"])
    encoded["MentalHealthDays"]   = float(raw["MentalHealthDays"])
    encoded["SleepHours"]         = float(raw["SleepHours"])

    # Binary Yes/No features
    for col in _BINARY_YES_NO:
        val = raw[col]
        encoded[col] = 1 if val == "Yes" else 0

    # HadDiabetes: only "Yes" → 1; everything else (No, pre-diabetes, pregnancy) → 0
    encoded["HadDiabetes"] = 1 if raw["HadDiabetes"] == "Yes" else 0

    # SmokerStatus
    sm_val = raw["SmokerStatus"]
    if sm_val not in _SMOKER_STATUS_MAP:
        raise ValueError(f"Unrecognised SmokerStatus value: {sm_val!r}")
    encoded["SmokerStatus"] = _SMOKER_STATUS_MAP[sm_val]

    # RemovedTeeth
    rt_val = raw["RemovedTeeth"]
    if rt_val not in _REMOVED_TEETH_MAP:
        raise ValueError(f"Unrecognised RemovedTeeth value: {rt_val!r}")
    encoded["RemovedTeeth"] = _REMOVED_TEETH_MAP[rt_val]

    # LastCheckupTime
    lc_val = raw["LastCheckupTime"]
    if lc_val not in _LAST_CHECKUP_MAP:
        raise ValueError(f"Unrecognised LastCheckupTime value: {lc_val!r}")
    encoded["LastCheckupTime"] = _LAST_CHECKUP_MAP[lc_val]

    return encoded


def predict_heart(pipeline, metadata: dict, raw_features: dict) -> dict:
    """Run inference.  raw_features uses preprocessing.py PascalCase keys
    with original string values; this function encodes them then builds
    the feature vector in metadata['feature_order'] order.

    Returns {risk_probability, threshold, is_elevated}.
    Never re-applies calibration on top of predict_proba — it is already
    baked into the pipeline (CalibratedClassifierCV).

    Uses a named pandas DataFrame so the StandardScaler (fitted with named
    columns) does not emit feature-name warnings and receives features in
    the exact column order it was trained on.
    """
    import pandas as pd  # local import — avoids adding a top-level dep for one call

    encoded = encode_heart_features(raw_features)
    feature_order = metadata["feature_order"]

    # Verify all expected features are present after encoding
    missing = [col for col in feature_order if col not in encoded]
    if missing:
        raise KeyError(f"Encoded feature dict is missing: {missing}")

    # Build a single-row DataFrame with named columns matching the training schema
    row_df = pd.DataFrame(
        [[float(encoded[col]) for col in feature_order]],
        columns=feature_order,
    )

    # Debug: log the feature vector at DEBUG level so uvicorn stdout shows it
    # only when --log-level debug is explicitly requested.
    import logging
    _log = logging.getLogger(__name__)
    _log.debug("heart inference input:\n%s", row_df.to_string())

    probability = float(pipeline.predict_proba(row_df)[0][1])
    threshold = metadata["decision_threshold"]
    return {
        "risk_probability": probability,
        "threshold":        threshold,
        "is_elevated":      probability >= threshold,
    }

