"""
SwasthAI — Liver Disease Risk Model — Production Loader & Inference
====================================================================
Mirrors the architecture of backend/app/ai/models/diabetes_model.py exactly.

Loads the complete sklearn Pipeline (ColumnTransformer preprocessing +
Logistic Regression classifier) produced by ml_pipeline/liver/train_nhanes.py,
together with its liver_metadata_nhanes_v1.json, and exposes predict_liver()
for the predict endpoint.

Deliberately lab-free: every feature this model uses (age, sex, BMI, waist
circumference, self-rated general health, alcohol/smoking/activity habits,
previously-diagnosed diabetes/hypertension) is something a person can answer
from memory or a routine physical exam — never a value from an LFT panel. A
model that requires lab results as input has no triage value (by the time
you have the labs, a clinician reading them already tells you the answer);
this one is meant to run *before* a lab visit, to help decide whether one is
worth getting. See ml_pipeline/liver/reports/evaluation_nhanes.md for the
full rationale and honest performance limitations.

predict_liver() accepts a plain dict of raw named features (no pandas import
needed in production), rebuilds the feature row in the exact order
metadata["feature_order"] specifies, and calls pipeline.predict_proba().
"""

import json
from pathlib import Path
from typing import Tuple

import joblib
import numpy as np

# ── Valid ranges (used for input validation) ─────────────────────────────────
# Derived from the training dataset (NHANES 2013-2018) plus reasonable
# extensions. These exist to reject clearly impossible inputs at the API
# layer before they reach the model — they are not used for preprocessing.
FEATURE_RANGES = {
    "age_years": (20, 120),
    "bmi": (10.0, 100.0),
    "waist_circumference_cm": (30.0, 250.0),
    "sex": {"Male", "Female"},
    "race_ethnicity": {
        "Mexican American", "Other Hispanic", "Non-Hispanic White",
        "Non-Hispanic Black", "Other/Multi-Racial",
    },
    "general_health": {"Excellent", "Very good", "Good", "Fair", "Poor"},
    "heavy_alcohol_use": {"Yes", "No"},
    "smoker": {"Yes", "No"},
    "diabetes_status": {"Yes", "No", "Borderline"},
    "hypertension": {"Yes", "No"},
    "physical_activity": {"Yes", "No"},
}

REQUIRED_METADATA_FIELDS = [
    "model_version", "feature_order", "decision_threshold",
    "model_algorithm", "target_column",
]


def load_liver_model(pipeline_path, metadata_path) -> Tuple[object, dict]:
    """
    Loads the fitted sklearn Pipeline and its metadata.json.

    Validates that:
      - Both files exist
      - Metadata contains all required fields
      - The decision threshold is a valid probability
      - All features in metadata are known

    Raises clearly on any missing/malformed piece — a configuration error
    here should fail loudly at startup, never silently at prediction time.
    """
    pipeline_path = Path(pipeline_path)
    metadata_path = Path(metadata_path)

    if not pipeline_path.exists():
        raise FileNotFoundError(f"Liver model artifact not found at {pipeline_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Liver model metadata not found at {metadata_path}")

    with open(metadata_path) as f:
        metadata = json.load(f)

    missing_fields = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
    if missing_fields:
        raise ValueError(f"Liver model metadata is missing required field(s): {missing_fields}")

    feature_order = metadata["feature_order"]
    if not isinstance(feature_order, list) or not feature_order:
        raise ValueError("Liver model metadata's 'feature_order' must be a non-empty list")

    unknown_features = [col for col in feature_order if col not in FEATURE_RANGES]
    if unknown_features:
        raise ValueError(
            f"Liver model metadata lists feature(s) with no known valid range: {unknown_features}"
        )

    threshold = metadata["decision_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not (0.0 < threshold < 1.0):
        raise ValueError(
            f"Liver model metadata's 'decision_threshold' must be a number in (0, 1), "
            f"got {threshold!r}"
        )

    pipeline = joblib.load(pipeline_path)
    return pipeline, metadata


def validate_features(features: dict, feature_order: list) -> None:
    """
    Validates all required features are present and within known clinical
    bounds. Raises KeyError on missing features, ValueError on out-of-range
    or non-numeric values.

    Gender is validated as a string set membership check (not numeric).
    Extra/unrecognized dict keys are harmlessly ignored.
    """
    missing = [col for col in feature_order if col not in features]
    if missing:
        raise KeyError(f"Missing required feature(s): {missing}")

    for col in feature_order:
        value = features[col]
        bounds = FEATURE_RANGES[col]

        if isinstance(bounds, set):
            # Categorical validation (gender)
            if value not in bounds:
                raise ValueError(
                    f"Feature '{col}'={value!r} must be one of {sorted(bounds)}"
                )
        else:
            # Numeric validation
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"Feature '{col}' must be numeric, got {value!r}")

            lo, hi = bounds
            if not (lo <= value <= hi):
                raise ValueError(
                    f"Feature '{col}'={value} is outside the valid range [{lo}, {hi}]"
                )


def predict_liver(pipeline, metadata: dict, features: dict) -> dict:
    """
    Returns the calibrated risk probability and the metadata-driven threshold
    decision for a single patient input.

    Accepts a plain dict of named features (not a pandas DataFrame) —
    production inference never needs to import pandas. The feature vector is
    always rebuilt from metadata['feature_order'], so the caller's dict key
    order can never silently swap two features.

    gender is passed as a string ("Male"/"Female") — the Pipeline's
    OneHotEncoder handles the encoding internally.
    """
    feature_order = metadata["feature_order"]
    validate_features(features, feature_order)

    # Build a single-row 2D list with columns in exact feature order
    # (The pipeline was trained with column indices, so it accepts this directly)
    row = [[features[col] for col in feature_order]]

    proba_arr = pipeline.predict_proba(row)[0]
    probability = float(proba_arr[1])  # probability of class 1 (liver disease)
    threshold = metadata["decision_threshold"]

    return {
        "risk_probability": probability,
        "threshold": threshold,
        "is_elevated": probability >= threshold,
    }
