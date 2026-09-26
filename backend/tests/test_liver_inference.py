from pathlib import Path

from app.ai.models.liver_model import load_liver_model, predict_liver
from app.models.prediction import LiverPredictionInput


def test_model_direct_inference():
    base_dir = Path(__file__).parent.parent.parent
    liver_artifacts_dir = base_dir / "ml_pipeline" / "liver" / "artifacts"

    pipeline, metadata = load_liver_model(
        liver_artifacts_dir / "liver_pipeline_nhanes_v1.pkl",
        liver_artifacts_dir / "liver_metadata_nhanes_v1.json",
    )

    # Low-risk sample: young, normal BMI, no risk factors
    sample_healthy = {
        "age_years": 28,
        "sex": "Female",
        "race_ethnicity": "Non-Hispanic White",
        "bmi": 21.5,
        "waist_circumference_cm": 75.0,
        "general_health": "Excellent",
        "heavy_alcohol_use": "No",
        "smoker": "No",
        "diabetes_status": "No",
        "hypertension": "No",
        "physical_activity": "Yes",
    }

    # High-risk sample: older, obese, multiple metabolic/lifestyle risk factors
    sample_elevated = {
        "age_years": 62,
        "sex": "Male",
        "race_ethnicity": "Non-Hispanic White",
        "bmi": 38.0,
        "waist_circumference_cm": 130.0,
        "general_health": "Poor",
        "heavy_alcohol_use": "Yes",
        "smoker": "Yes",
        "diabetes_status": "Yes",
        "hypertension": "Yes",
        "physical_activity": "No",
    }

    res_healthy = predict_liver(pipeline, metadata, sample_healthy)
    assert res_healthy["is_elevated"] is False
    print("Healthy sample inference successful.")

    res_elevated = predict_liver(pipeline, metadata, sample_elevated)
    assert res_elevated["is_elevated"] is True
    print("Elevated sample inference successful.")


def test_pydantic_validation():
    # Valid
    valid = LiverPredictionInput(
        age_years=28,
        sex="Female",
        race_ethnicity="Non-Hispanic White",
        bmi=21.5,
        waist_circumference_cm=75.0,
        general_health="Excellent",
        heavy_alcohol_use="No",
        smoker="No",
        diabetes_status="No",
        hypertension="No",
        physical_activity="Yes",
    )
    assert valid.age_years == 28
    print("Pydantic valid model test successful.")

    # Invalid missing
    try:
        LiverPredictionInput(age_years=28)
        assert False, "Should have raised exception for missing fields"
    except Exception as e:
        print("Pydantic missing fields validation successful:", type(e).__name__)

    # Invalid range
    try:
        LiverPredictionInput(
            age_years=10,  # out of range (model trained on adults 20+)
            sex="Female",
            race_ethnicity="Non-Hispanic White",
            bmi=21.5,
            waist_circumference_cm=75.0,
            general_health="Excellent",
            heavy_alcohol_use="No",
            smoker="No",
            diabetes_status="No",
            hypertension="No",
            physical_activity="Yes",
        )
        assert False, "Should have raised exception for out of range field"
    except Exception as e:
        print("Pydantic range validation successful:", type(e).__name__)


if __name__ == "__main__":
    test_model_direct_inference()
    test_pydantic_validation()
