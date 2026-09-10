"""
Fresh-process inference smoke test + robustness checks for the
diabetes-brfss-v2 (14-feature) pipeline artifact.

Mirrors inference_test_brfss.py's structure for the v1 (21-feature)
artifact — see that file for the original, more extensively-commented
version. This one additionally asserts the feature count is exactly 14
and that none of the fields removed from v1 (income, education,
healthcare access, mental/physical health days, vegetables) leak back in.

Run: python inference_test_brfss_v2.py
"""
import json
from pathlib import Path

import joblib

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

FEATURE_RANGES = {
    "HighBP": {0, 1}, "HighChol": {0, 1}, "CholCheck": {0, 1},
    "Smoker": {0, 1}, "Stroke": {0, 1}, "HeartDiseaseorAttack": {0, 1},
    "PhysActivity": {0, 1}, "Fruits": {0, 1}, "HvyAlcoholConsump": {0, 1},
    "DiffWalk": {0, 1}, "Sex": {0, 1},
    "BMI": (10, 100),
    "GenHlth": (1, 5),
    "Age": (1, 13),
}

REMOVED_FROM_V1 = ["Veggies", "AnyHealthcare", "NoDocbcCost", "MentHlth", "PhysHlth", "Education", "Income"]


def load_artifact():
    pipeline = joblib.load(ARTIFACTS_DIR / "diabetes_pipeline_v2.pkl")
    with open(ARTIFACTS_DIR / "diabetes_metadata_v2.json") as f:
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
    "HvyAlcoholConsump": 0, "GenHlth": 1, "DiffWalk": 0, "Sex": 0, "Age": 3,
}

SAMPLE_HIGHER_RISK = {
    "HighBP": 1, "HighChol": 1, "CholCheck": 1, "BMI": 38, "Smoker": 1,
    "Stroke": 0, "HeartDiseaseorAttack": 1, "PhysActivity": 0, "Fruits": 0,
    "HvyAlcoholConsump": 0, "GenHlth": 4, "DiffWalk": 1, "Sex": 1, "Age": 10,
}


def main():
    pipeline, metadata = load_artifact()
    feature_order = metadata["feature_order"]
    print(f"Loaded artifact: {metadata['model_name']} v{metadata['model_version']} ({metadata['algorithm']})")
    print(f"Feature order ({len(feature_order)}): {feature_order}")
    print(f"Decision threshold: {metadata['decision_threshold']}")

    print("\n--- Exactly 14 features (critical regression check) ---")
    assert len(feature_order) == 14, f"Expected exactly 14 features, got {len(feature_order)}: {feature_order}"
    print("OK: feature_order has exactly 14 entries")

    print("\n--- Removed v1 fields must not have leaked back in ---")
    leaked = [f for f in REMOVED_FROM_V1 if f in feature_order]
    assert not leaked, f"These v1 fields should have been removed but are present: {leaked}"
    print(f"OK: none of {REMOVED_FROM_V1} are present in v2's feature_order")

    print("\n--- No family-history field unless the trained model actually uses one ---")
    family_history_like = [f for f in feature_order if "family" in f.lower() or "pedigree" in f.lower()]
    assert not family_history_like, f"Unexpected family-history-style field: {family_history_like}"
    print("OK: no family-history-style field present")

    print("\n--- Lower-risk sample ---")
    result_low = predict_diabetes_risk(pipeline, metadata, SAMPLE_LOWER_RISK)
    print(result_low)
    assert 0.0 <= result_low["risk_probability"] <= 1.0
    assert result_low["risk_probability"] == result_low["risk_probability"]  # not NaN

    print("\n--- Higher-risk sample ---")
    result_high = predict_diabetes_risk(pipeline, metadata, SAMPLE_HIGHER_RISK)
    print(result_high)
    assert 0.0 <= result_high["risk_probability"] <= 1.0
    assert result_high["risk_probability"] > result_low["risk_probability"], (
        "Higher-risk profile scored lower than the lower-risk profile."
    )
    print(f"OK: higher-risk sample scored higher risk ({result_high['risk_probability']:.4f} > {result_low['risk_probability']:.4f})")

    print("\n--- Missing feature (should raise KeyError, fail safe) ---")
    incomplete = dict(SAMPLE_LOWER_RISK)
    del incomplete["BMI"]
    try:
        predict_diabetes_risk(pipeline, metadata, incomplete)
        raise AssertionError("Expected KeyError for missing feature")
    except KeyError as e:
        print(f"OK: raised KeyError as expected: {e}")

    print("\n--- Unexpected/extra feature (should be silently ignored, not corrupt the prediction) ---")
    extra = dict(SAMPLE_LOWER_RISK)
    extra["Income"] = 8  # a real v1 field, deliberately not part of v2 — must be ignored, not used
    result_extra = predict_diabetes_risk(pipeline, metadata, extra)
    assert result_extra["risk_probability"] == result_low["risk_probability"], (
        "An unexpected extra field (Income) changed the prediction — it must be ignored."
    )
    print(f"OK: unexpected 'Income' field ignored, prediction unchanged ({result_extra['risk_probability']:.4f})")

    print("\n--- Out-of-codebook categorical value (should raise ValueError, fail safe) ---")
    invalid_category = dict(SAMPLE_LOWER_RISK)
    invalid_category["Sex"] = 2
    try:
        predict_diabetes_risk(pipeline, metadata, invalid_category)
        raise AssertionError("Expected ValueError for out-of-codebook Sex value")
    except ValueError as e:
        print(f"OK: raised ValueError as expected: {e}")

    print("\n--- Out-of-range ordinal value (should raise ValueError, fail safe) ---")
    invalid_range = dict(SAMPLE_LOWER_RISK)
    invalid_range["GenHlth"] = 99
    try:
        predict_diabetes_risk(pipeline, metadata, invalid_range)
        raise AssertionError("Expected ValueError for out-of-range GenHlth value")
    except ValueError as e:
        print(f"OK: raised ValueError as expected: {e}")

    print("\n--- Non-numeric feature value (should raise ValueError, fail safe) ---")
    invalid_type = dict(SAMPLE_LOWER_RISK)
    invalid_type["BMI"] = "not-a-number"
    try:
        predict_diabetes_risk(pipeline, metadata, invalid_type)
        raise AssertionError("Expected ValueError for non-numeric feature")
    except ValueError as e:
        print(f"OK: raised ValueError as expected: {e}")

    print("\n--- Insertion-order independence (dict key order must not matter) ---")
    reordered = {k: SAMPLE_HIGHER_RISK[k] for k in reversed(list(SAMPLE_HIGHER_RISK.keys()))}
    result_reordered = predict_diabetes_risk(pipeline, metadata, reordered)
    assert result_reordered["risk_probability"] == result_high["risk_probability"]
    print(f"OK: insertion-order-shuffled dict gave an identical prediction ({result_reordered['risk_probability']:.4f})")

    print("\n--- Threshold is metadata-driven, not hardcoded (critical regression check) ---")
    low_metadata = dict(metadata, decision_threshold=max(0.01, result_high["risk_probability"] - 0.01))
    high_metadata = dict(metadata, decision_threshold=min(0.99, result_high["risk_probability"] + 0.2))
    result_low_threshold = predict_diabetes_risk(pipeline, low_metadata, SAMPLE_HIGHER_RISK)
    result_high_threshold = predict_diabetes_risk(pipeline, high_metadata, SAMPLE_HIGHER_RISK)
    assert result_low_threshold["predicted_class"] == 1
    assert result_high_threshold["predicted_class"] == 0
    assert result_low_threshold["risk_probability"] == result_high_threshold["risk_probability"]
    print("OK: predicted_class tracks metadata['decision_threshold'], not a fixed cutoff")

    print("\n--- Calibrated probability generation (artifact contains calibration) ---")
    from sklearn.calibration import CalibratedClassifierCV
    classifier = pipeline.named_steps["classifier"]
    assert isinstance(classifier, CalibratedClassifierCV), (
        f"Expected a calibrated classifier, got {type(classifier).__name__}"
    )
    print(f"OK: classifier is {type(classifier).__name__} (method={classifier.method})")

    print("\nAll v2 inference tests passed.")


if __name__ == "__main__":
    main()
