import json
import logging
from pathlib import Path
from typing import Any, Dict

import joblib
import joblib

logger = logging.getLogger(__name__)

# Correctly map paths relative to this file's location
MODEL_DIR = Path(__file__).parent
PIPELINE_PATH = MODEL_DIR / "liver_lifestyle_pipeline_tuned.pkl"
METADATA_PATH = MODEL_DIR / "liver_lifestyle_metadata.json"

class LiverLifestyleModel:
    """Wrapper for the XGBoost Liver Lifestyle Disease Risk pipeline."""

    def __init__(self) -> None:
        self.pipeline = None
        self.metadata: Dict[str, Any] = {}
        self.threshold: float = 0.5

    def load(self) -> None:
        """Loads the trained pipeline and its metadata from disk."""
        if self.pipeline is not None:
            return  # Already loaded

        logger.info(f"Loading liver lifestyle pipeline from {PIPELINE_PATH}")
        if not PIPELINE_PATH.exists():
            raise FileNotFoundError(f"Model pipeline not found at {PIPELINE_PATH}. Did you run train_lifestyle.py?")

        self.pipeline, self.threshold = joblib.load(PIPELINE_PATH)

        if METADATA_PATH.exists():
            with open(METADATA_PATH, "r") as f:
                self.metadata = json.load(f)
        else:
            logger.warning(f"Metadata not found at {METADATA_PATH}")

    def predict(self, input_data: "LiverLifestylePredictionInput") -> Dict[str, Any]: # type: ignore
        """
        Runs inference on the provided input data.
        """
        if self.pipeline is None:
            self.load()

        # Map to expected model format as 2D list (no pandas needed)
        # order: ['age', 'gender', 'bmi', 'waist_circumference', 'diabetes', 'hypertension', 'smoking', 'high_cholesterol', 'vigorous_activity', 'alcohol_drinks_per_day']
        row = [[
            input_data.age,
            1 if input_data.gender == "Male" else 0,
            input_data.bmi,
            input_data.waist_circumference,
            input_data.diabetes,
            input_data.hypertension,
            input_data.smoking,
            input_data.high_cholesterol,
            input_data.vigorous_activity,
            input_data.alcohol_drinks_per_day,
        ]]

        # Predict probability of class 1
        probability = float(self.pipeline.predict_proba(row)[0, 1])

        is_elevated = bool(probability >= float(self.threshold))

        return {
            "risk_probability": probability,
            "is_elevated": is_elevated,
            "threshold": float(self.threshold),
            "model_version": self.metadata.get("version", "unknown"),
        }

# Global instance
liver_lifestyle_model = LiverLifestyleModel()
