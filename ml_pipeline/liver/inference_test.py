import json
from pathlib import Path

import joblib
import pandas as pd

BASE = Path(__file__).parent
ARTIFACTS_DIR = BASE / "artifacts"

def load_pipeline():
    pipeline_path = ARTIFACTS_DIR / "liver_pipeline.pkl"
    metadata_path = ARTIFACTS_DIR / "liver_metadata.json"
    
    pipeline = joblib.load(pipeline_path)
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
        
    return pipeline, metadata

def main():
    pipeline, metadata = load_pipeline()
    
    # Test sample with normal/healthy features
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
    
    # Test sample with elevated features
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
    
    feature_order = metadata["feature_order"]
    threshold = metadata["decision_threshold"]
    
    for name, sample in [("Healthy", sample_healthy), ("Elevated", sample_elevated)]:
        df = pd.DataFrame([sample])[feature_order]
        proba = pipeline.predict_proba(df)[0, 1]
        
        print(f"--- {name} Sample ---")
        print(f"Probability: {proba:.4f}")
        print(f"Threshold:   {threshold}")
        print(f"Prediction:  {'Elevated Risk' if proba >= threshold else 'Negative Screening'}")
        print()

if __name__ == "__main__":
    main()
