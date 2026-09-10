import json
from pathlib import Path
from typing import Tuple

import joblib

# Codebook ranges for the 21 CDC BRFSS 2015 features this model was trained
# on (ml_pipeline/diabetes/data/raw/README_brfss2015.md is the source of
# truth; ml_pipeline/diabetes/inference_test_brfss.py validates the same
# ranges on the training side). Kept as a second copy here deliberately —
# production inference must not import anything from ml_pipeline/ (AGENTS.md
# Section 24) — so keep the two in sync if the codebook ever changes.
FEATURE_RANGES = {
    "HighBP": {0, 1}, "HighChol": {0, 1}, "CholCheck": {0, 1},
    "Smoker": {0, 1}, "Stroke": {0, 1}, "HeartDiseaseorAttack": {0, 1},
    "PhysActivity": {0, 1}, "Fruits": {0, 1}, "Veggies": {0, 1},
    "HvyAlcoholConsump": {0, 1}, "AnyHealthcare": {0, 1}, "NoDocbcCost": {0, 1},
    "DiffWalk": {0, 1}, "Sex": {0, 1},
    "BMI": (10, 100),
    "GenHlth": (1, 5),
    "MentHlth": (0, 30),
    "PhysHlth": (0, 30),
    "Age": (1, 13),
    "Education": (1, 6),
    "Income": (1, 8),
}

REQUIRED_METADATA_FIELDS = [
    "model_version", "feature_order", "decision_threshold",
    "calibration_method", "target_column",
]


def load_diabetes_model(pipeline_path, metadata_path) -> Tuple[object, dict]:
    """Loads the fitted sklearn Pipeline (StandardScaler + calibrated
    XGBoost) produced by ml_pipeline/diabetes/train_brfss.py, together with
    its metadata.json.

    The decision threshold and feature order live ONLY in metadata.json,
    not inside the pickle — see ml_pipeline/diabetes/reports/evaluation.md.
    This raises clearly on any missing/malformed piece rather than silently
    falling back to a default: a missing threshold is a configuration
    error, not a reason to guess 0.5.
    """
    pipeline_path = Path(pipeline_path)
    metadata_path = Path(metadata_path)

    if not pipeline_path.exists():
        raise FileNotFoundError(f"Diabetes model artifact not found at {pipeline_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Diabetes model metadata not found at {metadata_path}")

    with open(metadata_path) as f:
        metadata = json.load(f)

    missing_fields = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
    if missing_fields:
        raise ValueError(f"Diabetes model metadata is missing required field(s): {missing_fields}")

    feature_order = metadata["feature_order"]
    if not isinstance(feature_order, list) or not feature_order:
        raise ValueError("Diabetes model metadata's 'feature_order' must be a non-empty list")
    unknown_features = [col for col in feature_order if col not in FEATURE_RANGES]
    if unknown_features:
        raise ValueError(
            f"Diabetes model metadata lists feature(s) with no known valid range: {unknown_features}"
        )

    threshold = metadata["decision_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not (0.0 < threshold < 1.0):
        raise ValueError(f"Diabetes model metadata's 'decision_threshold' must be a number in (0, 1), got {threshold!r}")

    pipeline = joblib.load(pipeline_path)

    # Cross-check the artifact and metadata actually agree on feature count
    # — a silent mismatch here would mean predictions are made with
    # misaligned columns.
    scaler = getattr(pipeline, "named_steps", {}).get("scaler")
    n_expected = getattr(scaler, "n_features_in_", None)
    if n_expected is not None and n_expected != len(feature_order):
        raise ValueError(
            f"Diabetes artifact/metadata mismatch: the fitted pipeline expects {n_expected} "
            f"features, but metadata['feature_order'] lists {len(feature_order)}"
        )

    return pipeline, metadata


def validate_features(features: dict, feature_order: list) -> None:
    """Fails safely (KeyError/ValueError) on any missing, non-numeric, or
    out-of-codebook value rather than letting a bad value silently reach
    the model. Extra/unrecognized dict keys are harmlessly ignored, since
    only the keys in feature_order are ever read."""
    missing = [col for col in feature_order if col not in features]
    if missing:
        raise KeyError(f"Missing required feature(s): {missing}")

    for col in feature_order:
        value = features[col]
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Feature '{col}' must be numeric, got {features[col]!r}")

        bounds = FEATURE_RANGES[col]
        if isinstance(bounds, set):
            if value not in bounds:
                raise ValueError(f"Feature '{col}'={value} is not one of the valid values {bounds}")
        else:
            lo, hi = bounds
            if not (lo <= value <= hi):
                raise ValueError(f"Feature '{col}'={value} is outside the valid range [{lo}, {hi}]")


def predict_diabetes(pipeline, metadata: dict, features: dict) -> dict:
    """Returns the calibrated risk probability and the metadata-driven
    threshold decision. Calibration is already baked into the pipeline
    (CalibratedClassifierCV) — this never re-applies any scaling on top of
    predict_proba's output.

    Takes a plain dict-of-named-features, not a pandas DataFrame: production
    inference never needs to import pandas. The feature vector is always
    rebuilt from metadata['feature_order'], so the caller's dict key order
    never matters and can never silently swap two features.
    """
    feature_order = metadata["feature_order"]
    validate_features(features, feature_order)
    row = [[float(features[col]) for col in feature_order]]
    probability = float(pipeline.predict_proba(row)[0][1])
    threshold = metadata["decision_threshold"]
    return {
        "risk_probability": probability,
        "threshold": threshold,
        "is_elevated": probability >= threshold,
    }
