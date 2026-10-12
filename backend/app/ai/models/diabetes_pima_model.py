"""
SwasthAI — Diabetes Risk Model (Lab-Based / Pima) — Production Loader & Inference
====================================================================================
Mirrors the architecture of backend/app/ai/models/liver_model.py exactly.

Loads the sklearn Pipeline (SimpleImputer + StandardScaler + sigmoid-
calibrated logistic regression) produced by ml_pipeline/diabetes_pima/train.py,
together with its diabetes_pima_metadata_v1.json, and exposes
predict_diabetes_pima() for the predict endpoint.

This is the deliberate "I have recent lab results" counterpart to
diabetes_model.py (diabetes-brfss-v2, lab-free): a separate dataset (Pima
Indians Diabetes Database — NIDDK/UCI, Smith et al. 1988), a separate
trained artifact, never merged or blended with any other diabetes model in
this project. See ml_pipeline/diabetes_pima/reports/evaluation.md for full
rationale, including the narrow training population (female, Pima Indian
heritage, age 21+) that must be disclosed alongside any prediction.

predict_diabetes_pima() accepts a plain dict of raw named features (no
pandas import needed in production), rebuilds the feature row in the exact
order metadata["feature_order"] specifies, and calls
pipeline.predict_proba(). The pipeline's own SimpleImputer handles any
missing individual field the caller could not supply (validate_features
below still requires every field be present in the dict, but callers may
pass None for values they don't have).
"""

import json
from pathlib import Path
from typing import Tuple

import joblib

# ── Valid ranges (used for input validation) ─────────────────────────────────
# Derived from the training dataset (Pima) plus reasonable extensions.
# These exist to reject clearly impossible inputs at the API layer before
# they reach the model — they are not used for preprocessing.
FEATURE_RANGES = {
    "Pregnancies": (0, 20),
    "Glucose": (40.0, 300.0),
    "BloodPressure": (20.0, 200.0),
    "SkinThickness": (5.0, 100.0),
    "BMI": (10.0, 80.0),
    "Age": (18, 120),
}

REQUIRED_METADATA_FIELDS = [
    "model_version", "feature_order", "decision_threshold",
    "model_algorithm", "target_column",
]


def load_diabetes_pima_model(pipeline_path, metadata_path) -> Tuple[object, dict]:
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
        raise FileNotFoundError(f"Diabetes (Pima) model artifact not found at {pipeline_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Diabetes (Pima) model metadata not found at {metadata_path}")

    with open(metadata_path) as f:
        metadata = json.load(f)

    missing_fields = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
    if missing_fields:
        raise ValueError(f"Diabetes (Pima) model metadata is missing required field(s): {missing_fields}")

    feature_order = metadata["feature_order"]
    if not isinstance(feature_order, list) or not feature_order:
        raise ValueError("Diabetes (Pima) model metadata's 'feature_order' must be a non-empty list")

    unknown_features = [col for col in feature_order if col not in FEATURE_RANGES]
    if unknown_features:
        raise ValueError(
            f"Diabetes (Pima) model metadata lists feature(s) with no known valid range: {unknown_features}"
        )

    threshold = metadata["decision_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not (0.0 < threshold < 1.0):
        raise ValueError(
            f"Diabetes (Pima) model metadata's 'decision_threshold' must be a number in (0, 1), "
            f"got {threshold!r}"
        )

    pipeline = joblib.load(pipeline_path)
    return pipeline, metadata


def validate_features(features: dict, feature_order: list) -> None:
    """
    Validates all required features are present and within known clinical
    bounds. Raises KeyError on missing features, ValueError on out-of-range
    or non-numeric values.

    Extra/unrecognized dict keys are harmlessly ignored.
    """
    missing = [col for col in feature_order if col not in features]
    if missing:
        raise KeyError(f"Missing required feature(s): {missing}")

    for col in feature_order:
        value = features[col]
        lo, hi = FEATURE_RANGES[col]

        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Feature '{col}' must be numeric, got {value!r}")

        if not (lo <= value <= hi):
            raise ValueError(
                f"Feature '{col}'={value} is outside the valid range [{lo}, {hi}]"
            )


def predict_diabetes_pima(pipeline, metadata: dict, features: dict) -> dict:
    """
    Returns the calibrated risk probability and the metadata-driven threshold
    decision for a single patient input.

    Accepts a plain dict of named features (not a pandas DataFrame) —
    production inference never needs to import pandas. The feature vector is
    always rebuilt from metadata['feature_order'], so the caller's dict key
    order can never silently swap two features.
    """
    feature_order = metadata["feature_order"]
    validate_features(features, feature_order)

    # Build a single-row 2D list with columns in exact feature order
    # (The pipeline was trained with column indices, so it accepts this directly)
    row = [[features[col] for col in feature_order]]

    proba_arr = pipeline.predict_proba(row)[0]
    probability = float(proba_arr[1])  # probability of class 1 (diabetes)
    threshold = metadata["decision_threshold"]

    return {
        "risk_probability": probability,
        "threshold": threshold,
        "is_elevated": probability >= threshold,
    }
