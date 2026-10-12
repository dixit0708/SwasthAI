"""
SwasthAI — Liver Disease Risk Model (Lab-Based / ILPD, Logistic Regression)
— Production Loader & Inference
=============================================================================
Mirrors the architecture of backend/app/ai/models/liver_model.py and
diabetes_pima_model.py. Loads the LOCKED sklearn Pipeline (median imputer +
scaler + one-hot encoder + Logistic Regression, all bundled together)
produced by ml_pipeline/liver/train_ilpd_logistic.py, together with its
liver_ilpd_logistic_metadata_v1.json, and exposes predict_liver_ilpd() for
the predict endpoint.

This artifact is LOCKED per an explicit integration task: it must never be
retrained, refit, or have its preprocessing/threshold changed by this
file. load_liver_ilpd_model() verifies the artifact and metadata against
their known-good SHA-256 checksums (recorded at training time in
ml_pipeline/liver/reports/ilpd_final_model_report.md) before ever loading
them — if either file has drifted from what was validated and
inference-tested, this fails loudly at startup rather than silently
serving predictions from an unverified artifact.

This is the deliberate "I have my lab report" counterpart to
liver_model.py (liver-nhanes-v1, lab-free) — a separate dataset (the
canonical UCI ILPD, not the rejected 30,691-row "LPD" file — see
ml_pipeline/liver_lpd/reports/data_integrity_investigation.md for why that
one was rejected), a separate trained artifact, never merged or blended
with liver-nhanes-v1's output. See
ml_pipeline/liver/reports/ilpd_final_model_report.md for the full
methodology, cross-validated metrics, and honest limitations (small
dataset, single-region population) that must be disclosed alongside any
prediction.

predict_liver_ilpd() accepts a plain dict of raw named features (no
pandas import needed in production), rebuilds the feature row in the exact
order metadata["feature_names"] specifies, and calls
pipeline.predict_proba(). The pipeline's own SimpleImputer handles a caller
passing None for a numeric value it doesn't have; validate_features()
below still requires every field be present as a dict key.
"""

import hashlib
import json
from pathlib import Path
from typing import Tuple

import joblib

# Recorded at training time (ml_pipeline/liver/train_ilpd_logistic.py) and
# re-verified in ml_pipeline/liver/reports/ilpd_final_model_report.md
# Section 17. This artifact is locked: these hashes must never be updated
# to match a newer file — if they stop matching, the artifact has drifted
# and must be re-validated (retrained, re-evaluated, re-locked) before use,
# not silently accepted.
EXPECTED_PIPELINE_SHA256 = "551e957e0ff027dc07f48b8e6756a0ca00043b828e32950c1598ecab0eafb6db"
EXPECTED_METADATA_SHA256 = "10885b0bdb69ec1100191bbb5f52ee33a1823309b0ebe0dade171d213340339a"

# ── Valid ranges (used for input validation) ─────────────────────────────
# Derived from the training dataset's actual min/max (canonical UCI ILPD,
# 583 rows) plus reasonable clinical extension. These exist to reject
# clearly impossible inputs at the API layer before they reach the model —
# they are not used for preprocessing.
FEATURE_RANGES = {
    "age_years": (1, 120),
    "total_bilirubin_mg_dl": (0.1, 100.0),
    "direct_bilirubin_mg_dl": (0.05, 30.0),
    "alkaline_phosphatase_u_l": (20.0, 3000.0),
    "alanine_aminotransferase_u_l": (5.0, 3000.0),
    "aspartate_aminotransferase_u_l": (5.0, 6000.0),
    "total_proteins_g_dl": (2.0, 12.0),
    "albumin_g_dl": (0.5, 7.0),
    "albumin_globulin_ratio": (0.1, 4.0),
    "gender": {"Male", "Female"},
}

# This artifact's metadata uses its own key names (feature_names,
# selected_threshold, model_type, target_name) rather than the
# feature_order/decision_threshold/model_algorithm/target_column
# convention used by liver_model.py / diabetes_pima_model.py — the
# metadata file is locked and must not be edited to match that other
# convention, so this loader reads it as-is.
REQUIRED_METADATA_FIELDS = [
    "model_version", "feature_names", "selected_threshold",
    "model_type", "target_name",
]


class ArtifactIntegrityError(Exception):
    """Raised when a locked model artifact or its metadata does not match
    its known-good checksum. Never caught silently — an integrity failure
    here must stop startup, not degrade to a missing-model 503."""


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_liver_ilpd_model(pipeline_path, metadata_path) -> Tuple[object, dict]:
    """
    Verifies the locked artifact + metadata checksums, then loads the
    fitted sklearn Pipeline and metadata.json.

    Validates that:
      - Both files exist
      - Both files match their locked SHA-256 checksum (raises
        ArtifactIntegrityError otherwise — this model must never load a
        drifted or substituted file)
      - Metadata contains all required fields
      - The decision threshold is a valid probability
      - All features in metadata are known

    Raises clearly on any missing/malformed/mismatched piece — a
    configuration error here should fail loudly at startup, never silently
    at prediction time.
    """
    pipeline_path = Path(pipeline_path)
    metadata_path = Path(metadata_path)

    if not pipeline_path.exists():
        raise FileNotFoundError(f"Liver (ILPD) model artifact not found at {pipeline_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Liver (ILPD) model metadata not found at {metadata_path}")

    actual_pipeline_sha256 = _sha256_of(pipeline_path)
    if actual_pipeline_sha256 != EXPECTED_PIPELINE_SHA256:
        raise ArtifactIntegrityError(
            f"Liver (ILPD) model artifact checksum mismatch at {pipeline_path}: "
            f"expected {EXPECTED_PIPELINE_SHA256}, got {actual_pipeline_sha256}. "
            f"This artifact is locked — refusing to load a file that does not match "
            f"the validated, inference-tested version."
        )

    actual_metadata_sha256 = _sha256_of(metadata_path)
    if actual_metadata_sha256 != EXPECTED_METADATA_SHA256:
        raise ArtifactIntegrityError(
            f"Liver (ILPD) model metadata checksum mismatch at {metadata_path}: "
            f"expected {EXPECTED_METADATA_SHA256}, got {actual_metadata_sha256}. "
            f"This metadata is locked — refusing to load a file that does not match "
            f"the validated, inference-tested version."
        )

    with open(metadata_path) as f:
        metadata = json.load(f)

    missing_fields = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
    if missing_fields:
        raise ValueError(f"Liver (ILPD) model metadata is missing required field(s): {missing_fields}")

    feature_order = metadata["feature_names"]
    if not isinstance(feature_order, list) or not feature_order:
        raise ValueError("Liver (ILPD) model metadata's 'feature_names' must be a non-empty list")

    unknown_features = [col for col in feature_order if col not in FEATURE_RANGES]
    if unknown_features:
        raise ValueError(
            f"Liver (ILPD) model metadata lists feature(s) with no known valid range: {unknown_features}"
        )

    threshold = metadata["selected_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not (0.0 < threshold < 1.0):
        raise ValueError(
            f"Liver (ILPD) model metadata's 'selected_threshold' must be a number in (0, 1), "
            f"got {threshold!r}"
        )

    pipeline = joblib.load(pipeline_path)
    return pipeline, metadata


def validate_features(features: dict, feature_order: list) -> None:
    """
    Validates all required features are present and within known clinical
    bounds. Raises KeyError on missing features, ValueError on out-of-range
    or non-numeric values.

    A numeric field may be explicitly passed as None — the pipeline's own
    SimpleImputer (fit at training time on the full 570-row cleaned
    dataset, see ml_pipeline/liver/train_ilpd_logistic.py) is designed to
    handle a missing individual value; None is converted to NaN and passed
    through rather than rejected. This does NOT relax validation for a
    genuinely malformed request — a missing dict KEY still raises KeyError,
    and a present-but-invalid value (wrong type, out of range) still raises
    ValueError. Only an explicit, intentional "I don't have this value" is
    accepted for numeric fields.

    gender is validated as a string set membership check and does not
    support a missing-value pathway (the dataset's own missing values were
    all numeric — see ilpd_final_model_report.md Section 5 — so there is no
    validated missing-gender behavior to preserve).

    Extra/unrecognized dict keys are harmlessly ignored by this function,
    but the API layer's Pydantic model (extra="forbid") rejects them before
    execution ever reaches here.
    """
    missing = [col for col in feature_order if col not in features]
    if missing:
        raise KeyError(f"Missing required feature(s): {missing}")

    for col in feature_order:
        value = features[col]
        bounds = FEATURE_RANGES[col]

        if isinstance(bounds, set):
            if value not in bounds:
                raise ValueError(f"Feature '{col}'={value!r} must be one of {sorted(bounds)}")
            continue

        if value is None:
            continue  # supported missing-value case — pipeline's imputer handles it

        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Feature '{col}' must be numeric or null, got {value!r}")

        lo, hi = bounds
        if not (lo <= value <= hi):
            raise ValueError(f"Feature '{col}'={value} is outside the valid range [{lo}, {hi}]")


def predict_liver_ilpd(pipeline, metadata: dict, features: dict) -> dict:
    """
    Returns the risk probability and the metadata-driven threshold decision
    for a single patient input.

    Accepts a plain dict of named features (not a pandas DataFrame) —
    production inference never needs to import pandas. The feature vector
    is always rebuilt from metadata['feature_names'], so the caller's dict
    key order can never silently swap two features — this is enforced
    structurally, not just by convention (see backend/tests/
    test_liver_ilpd_inference.py for a scrambled-key-order regression test).

    A None value for a numeric feature is passed through as NaN, letting
    the pipeline's own SimpleImputer (median, fit at training time) supply
    it — this is a deliberate, validated behavior, not a silent fallback.
    """
    feature_order = metadata["feature_names"]
    validate_features(features, feature_order)

    row = [[
        (float("nan") if features[col] is None else features[col])
        for col in feature_order
    ]]

    proba_arr = pipeline.predict_proba(row)[0]
    probability = float(proba_arr[1])  # probability of class 1 (liver disease)
    threshold = metadata["selected_threshold"]

    return {
        "risk_probability": probability,
        "threshold": threshold,
        "is_elevated": probability >= threshold,
    }
