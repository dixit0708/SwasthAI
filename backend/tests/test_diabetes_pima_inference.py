from pathlib import Path

from app.ai.models.diabetes_pima_model import load_diabetes_pima_model, predict_diabetes_pima
from app.models.prediction import DiabetesPimaPredictionInput


def test_model_direct_inference():
    base_dir = Path(__file__).parent.parent.parent
    artifacts_dir = base_dir / "ml_pipeline" / "diabetes_pima" / "artifacts"

    pipeline, metadata = load_diabetes_pima_model(
        artifacts_dir / "diabetes_pima_pipeline_v1.pkl",
        artifacts_dir / "diabetes_pima_metadata_v1.json",
    )

    # Low-risk sample: young, no pregnancies, normal glucose/BP/BMI
    sample_healthy = {
        "Pregnancies": 0,
        "Glucose": 85.0,
        "BloodPressure": 66.0,
        "SkinThickness": 20.0,
        "BMI": 21.0,
        "Age": 22,
    }

    # High-risk sample: older, high glucose/BP/BMI, several pregnancies
    sample_elevated = {
        "Pregnancies": 6,
        "Glucose": 190.0,
        "BloodPressure": 95.0,
        "SkinThickness": 40.0,
        "BMI": 40.0,
        "Age": 55,
    }

    res_healthy = predict_diabetes_pima(pipeline, metadata, sample_healthy)
    assert res_healthy["is_elevated"] is False
    print("Healthy sample inference successful.")

    res_elevated = predict_diabetes_pima(pipeline, metadata, sample_elevated)
    assert res_elevated["is_elevated"] is True
    print("Elevated sample inference successful.")


def test_pydantic_validation():
    # Valid
    valid = DiabetesPimaPredictionInput(
        pregnancies=0,
        glucose=85.0,
        blood_pressure=66.0,
        skin_thickness=20.0,
        bmi=21.0,
        age=22,
    )
    assert valid.age == 22
    print("Pydantic valid model test successful.")

    # Invalid missing
    try:
        DiabetesPimaPredictionInput(age=22)
        assert False, "Should have raised exception for missing fields"
    except Exception as e:
        print("Pydantic missing fields validation successful:", type(e).__name__)

    # Invalid range
    try:
        DiabetesPimaPredictionInput(
            pregnancies=0,
            glucose=85.0,
            blood_pressure=66.0,
            skin_thickness=20.0,
            bmi=21.0,
            age=10,  # out of range (model trained on adults 18+)
        )
        assert False, "Should have raised exception for out of range field"
    except Exception as e:
        print("Pydantic range validation successful:", type(e).__name__)


if __name__ == "__main__":
    test_model_direct_inference()
    test_pydantic_validation()
