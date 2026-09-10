"""
Fresh-process inference smoke test + robustness checks for the BRFSS
diabetes risk pipeline artifact.

Mirrors the calling convention already used in production
(backend/app/ai/models/diabetes_model.py): the model is always called
through a dict-of-named-features -> FEATURE_ORDER-positional-list helper,
never with a raw positional list, so a caller cannot silently swap two
features by getting the order wrong.

Run: python inference_test_brfss.py
"""
import json
from pathlib import Path

import joblib

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

# Valid codebook ranges per data/raw/README_brfss2015.md. Anything outside
# these is not a value BRFSS's survey instrument can produce, so it is
# rejected rather than silently fed to the model.
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


def load_artifact():
    pipeline = joblib.load(ARTIFACTS_DIR / "diabetes_pipeline.pkl")
    with open(ARTIFACTS_DIR / "metadata.json") as f:
        metadata = json.load(f)
    return pipeline, metadata


def validate_features(features: dict, feature_order: list) -> None:
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


def predict_diabetes_risk(pipeline, metadata: dict, features: dict) -> dict:
    feature_order = metadata["feature_order"]
    validate_features(features, feature_order)
    row = [[float(features[col]) for col in feature_order]]
    probability = float(pipeline.predict_proba(row)[0][1])
    predicted_class = int(probability >= metadata["decision_threshold"])
    return {"risk_probability": probability, "predicted_class": predicted_class}


SAMPLE_LOWER_RISK = {
    "HighBP": 0, "HighChol": 0, "CholCheck": 1, "BMI": 22, "Smoker": 0,
    "Stroke": 0, "HeartDiseaseorAttack": 0, "PhysActivity": 1, "Fruits": 1,
    "Veggies": 1, "HvyAlcoholConsump": 0, "AnyHealthcare": 1, "NoDocbcCost": 0,
    "GenHlth": 1, "MentHlth": 0, "PhysHlth": 0, "DiffWalk": 0, "Sex": 0,
    "Age": 3, "Education": 6, "Income": 7,
}

SAMPLE_HIGHER_RISK = {
    "HighBP": 1, "HighChol": 1, "CholCheck": 1, "BMI": 38, "Smoker": 1,
    "Stroke": 0, "HeartDiseaseorAttack": 1, "PhysActivity": 0, "Fruits": 0,
    "Veggies": 0, "HvyAlcoholConsump": 0, "AnyHealthcare": 1, "NoDocbcCost": 0,
    "GenHlth": 4, "MentHlth": 10, "PhysHlth": 15, "DiffWalk": 1, "Sex": 1,
    "Age": 10, "Education": 3, "Income": 3,
}


def main():
    pipeline, metadata = load_artifact()
    feature_order = metadata["feature_order"]
    print(f"Loaded artifact: {metadata['model_name']} v{metadata['model_version']} ({metadata['algorithm']})")
    print(f"Feature order ({len(feature_order)}): {feature_order}")
    print(f"Decision threshold: {metadata['decision_threshold']}")

    print("\n--- Lower-risk sample ---")
    result_low = predict_diabetes_risk(pipeline, metadata, SAMPLE_LOWER_RISK)
    print(result_low)
    assert 0.0 <= result_low["risk_probability"] <= 1.0
    assert result_low["risk_probability"] == result_low["risk_probability"]  # not NaN
    assert result_low["predicted_class"] in (0, 1)

    print("\n--- Higher-risk sample ---")
    result_high = predict_diabetes_risk(pipeline, metadata, SAMPLE_HIGHER_RISK)
    print(result_high)
    assert 0.0 <= result_high["risk_probability"] <= 1.0
    assert result_high["risk_probability"] == result_high["risk_probability"]
    assert result_high["predicted_class"] in (0, 1)

    assert result_high["risk_probability"] > result_low["risk_probability"], (
        "Sanity check failed: the hand-built higher-risk profile scored lower risk "
        "than the lower-risk profile."
    )
    print(f"\nOK: higher-risk sample scored higher risk "
          f"({result_high['risk_probability']:.4f} > {result_low['risk_probability']:.4f})")

    print("\n--- Missing feature (should raise KeyError, fail safe) ---")
    incomplete = dict(SAMPLE_LOWER_RISK)
    del incomplete["BMI"]
    try:
        predict_diabetes_risk(pipeline, metadata, incomplete)
        raise AssertionError("Expected KeyError for missing feature, got a prediction instead")
    except KeyError as e:
        print(f"OK: raised KeyError as expected: {e}")

    print("\n--- Non-numeric feature value (should raise ValueError, fail safe) ---")
    invalid_type = dict(SAMPLE_LOWER_RISK)
    invalid_type["BMI"] = "not-a-number"
    try:
        predict_diabetes_risk(pipeline, metadata, invalid_type)
        raise AssertionError("Expected ValueError for non-numeric feature, got a prediction instead")
    except ValueError as e:
        print(f"OK: raised ValueError as expected: {e}")

    print("\n--- Out-of-codebook categorical value (should raise ValueError, fail safe) ---")
    invalid_category = dict(SAMPLE_LOWER_RISK)
    invalid_category["Sex"] = 2  # only 0/1 are valid
    try:
        predict_diabetes_risk(pipeline, metadata, invalid_category)
        raise AssertionError("Expected ValueError for out-of-codebook Sex value, got a prediction instead")
    except ValueError as e:
        print(f"OK: raised ValueError as expected: {e}")

    print("\n--- Out-of-range ordinal value (should raise ValueError, fail safe) ---")
    invalid_range = dict(SAMPLE_LOWER_RISK)
    invalid_range["GenHlth"] = 99
    try:
        predict_diabetes_risk(pipeline, metadata, invalid_range)
        raise AssertionError("Expected ValueError for out-of-range GenHlth value, got a prediction instead")
    except ValueError as e:
        print(f"OK: raised ValueError as expected: {e}")

    print("\n--- Extra/unexpected dict key (should be silently ignored, not corrupt the prediction) ---")
    extra_key = dict(SAMPLE_LOWER_RISK)
    extra_key["SomeUnknownField"] = 12345
    result_extra = predict_diabetes_risk(pipeline, metadata, extra_key)
    assert result_extra["risk_probability"] == result_low["risk_probability"], (
        "An unrecognized extra key changed the prediction — it should have been ignored."
    )
    print(f"OK: extra key ignored, prediction unchanged ({result_extra['risk_probability']:.4f})")

    print("\n--- Same feature dict, different key insertion order (should give an identical prediction) ---")
    reordered = {k: SAMPLE_HIGHER_RISK[k] for k in reversed(list(SAMPLE_HIGHER_RISK.keys()))}
    assert list(reordered.keys()) != list(SAMPLE_HIGHER_RISK.keys()), "Test setup error: keys were not actually reordered"
    result_reordered = predict_diabetes_risk(pipeline, metadata, reordered)
    assert result_reordered["risk_probability"] == result_high["risk_probability"], (
        "Reordering the input dict's keys changed the prediction — feature lookup must be by name, not position."
    )
    print(f"OK: insertion-order-shuffled dict gave an identical prediction ({result_reordered['risk_probability']:.4f})")

    print("\n--- Wrong feature order passed directly to the raw pipeline (documented risk, not caught) ---")
    correct_row = [[float(SAMPLE_HIGHER_RISK[c]) for c in feature_order]]
    shuffled_order = feature_order[1:] + feature_order[:1]
    wrong_row = [[float(SAMPLE_HIGHER_RISK[c]) for c in shuffled_order]]
    correct_proba = float(pipeline.predict_proba(correct_row)[0][1])
    wrong_proba = float(pipeline.predict_proba(wrong_row)[0][1])
    print(f"Correct-order probability: {correct_proba:.4f}  Shuffled-order probability: {wrong_proba:.4f}")
    print(
        "NOTE: the raw pipeline accepts a plain positional list (no pandas dependency in "
        "production, matching backend/app/ai/models/diabetes_model.py) and CANNOT detect a "
        "silently reordered feature list on its own — this is why predict_diabetes_risk() above "
        "is the only sanctioned call path: it always rebuilds the positional list from "
        "metadata['feature_order'], so order mistakes can only happen if that mapping itself "
        "is edited incorrectly, not per-request."
    )

    print("\n--- Threshold is metadata-driven, not hardcoded (critical regression check) ---")
    low_metadata = dict(metadata, decision_threshold=max(0.01, result_high["risk_probability"] - 0.01))
    high_metadata = dict(metadata, decision_threshold=min(0.99, result_high["risk_probability"] + 0.2))
    result_low_threshold = predict_diabetes_risk(pipeline, low_metadata, SAMPLE_HIGHER_RISK)
    result_high_threshold = predict_diabetes_risk(pipeline, high_metadata, SAMPLE_HIGHER_RISK)
    assert result_low_threshold["predicted_class"] == 1, "Expected elevated at a threshold below the sample's own probability"
    assert result_high_threshold["predicted_class"] == 0, "Expected not-elevated at a threshold above the sample's own probability"
    assert result_low_threshold["risk_probability"] == result_high_threshold["risk_probability"], (
        "Only the threshold changed between these two calls — the probability itself must be identical."
    )
    print("OK: predicted_class tracks metadata['decision_threshold'], not a fixed 0.5 cutoff")

    print("\n--- No family-history field unless the trained model actually uses one ---")
    family_history_like = [f for f in feature_order if "family" in f.lower() or "pedigree" in f.lower()]
    assert not family_history_like, (
        f"metadata['feature_order'] appears to reference a family-history-style field {family_history_like} "
        "but this model was never trained with one — see reports/family_history_investigation.md. "
        "Never claim family history is used unless it is genuinely a trained-on feature."
    )
    print(f"OK: no family-history-style field present in feature_order ({len(feature_order)} features, all BRFSS lifestyle/history items)")

    print("\nAll inference tests passed.")


if __name__ == "__main__":
    main()
