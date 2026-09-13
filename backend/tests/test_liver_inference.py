import asyncio
import json
from pathlib import Path

from app.main import app
from app.ai.models.liver_model import load_liver_model, predict_liver
from app.models.prediction import LiverPredictionInput

def test_model_direct_inference():
    base_dir = Path(__file__).parent.parent.parent
    liver_artifacts_dir = base_dir / "ml_pipeline" / "liver" / "artifacts"
    
    pipeline, metadata = load_liver_model(
        liver_artifacts_dir / "liver_pipeline.pkl",
        liver_artifacts_dir / "liver_metadata.json",
    )
    
    # Healthy sample
    sample_healthy = {
        "age_years": 35,
        "gender": "Female",
        "total_bilirubin_mg_dl": 0.8,
        "direct_bilirubin_mg_dl": 0.2,
        "alkaline_phosphatase_u_l": 120,
        "alanine_aminotransferase_u_l": 25,
        "aspartate_aminotransferase_u_l": 20,
        "total_proteins_g_dl": 7.0,
        "albumin_g_dl": 4.5,
        "albumin_globulin_ratio": 1.8
    }
    
    # Elevated sample
    sample_elevated = {
        "age_years": 60,
        "gender": "Male",
        "total_bilirubin_mg_dl": 12.0,
        "direct_bilirubin_mg_dl": 5.5,
        "alkaline_phosphatase_u_l": 450,
        "alanine_aminotransferase_u_l": 150,
        "aspartate_aminotransferase_u_l": 180,
        "total_proteins_g_dl": 5.5,
        "albumin_g_dl": 2.5,
        "albumin_globulin_ratio": 0.8
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
        age_years=35,
        gender="Female",
        total_bilirubin_mg_dl=0.8,
        direct_bilirubin_mg_dl=0.2,
        alkaline_phosphatase_u_l=120,
        alanine_aminotransferase_u_l=25,
        aspartate_aminotransferase_u_l=20,
        total_proteins_g_dl=7.0,
        albumin_g_dl=4.5,
        albumin_globulin_ratio=1.8
    )
    assert valid.age_years == 35
    print("Pydantic valid model test successful.")

    # Invalid missing
    try:
        LiverPredictionInput(age_years=35)
        assert False, "Should have raised exception for missing fields"
    except Exception as e:
        print("Pydantic missing fields validation successful:", type(e).__name__)
        
    # Invalid range
    try:
        LiverPredictionInput(
            age_years=35,
            gender="Female",
            total_bilirubin_mg_dl=200.0, # out of range (max 100)
            direct_bilirubin_mg_dl=0.2,
            alkaline_phosphatase_u_l=120,
            alanine_aminotransferase_u_l=25,
            aspartate_aminotransferase_u_l=20,
            total_proteins_g_dl=7.0,
            albumin_g_dl=4.5,
            albumin_globulin_ratio=1.8
        )
        assert False, "Should have raised exception for out of range field"
    except Exception as e:
        print("Pydantic range validation successful:", type(e).__name__)

if __name__ == "__main__":
    test_model_direct_inference()
    test_pydantic_validation()
