import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
import joblib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.ai.models.diabetes_model import load_diabetes_model
from app.ai.models.diabetes_pima_model import load_diabetes_pima_model
from app.ai.models.heart_model import load_heart_model
from app.ai.models.liver_model import load_liver_model
from app.ai.models.liver_ilpd_model import load_liver_ilpd_model

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()

    # Pneumonia CNN: lazy-loaded on first request rather than here.
    # Importing torch + torchvision alone costs ~230MB RSS (measured), which
    # every worker process would otherwise pay unconditionally even if it
    # never serves a pneumonia request. See the lazy-load-and-cache helper
    # in app/api/v1/endpoints/predict.py, which populates
    # app.state.pneumonia_model on first use and reuses it after that.
    #
    # Checkpoint path: backend/app/ai/models/pneumonia_cnn.pt, the canonical
    # production location a teammate's concurrent commit moved it to (it
    # previously lived under ml-services/cnn-detector/checkpoints/).
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app.state.pneumonia_ckpt_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ai", "models", "pneumonia_cnn.pt"
    )
    app.state.pneumonia_model = None
    app.state.pneumonia_model_lock = asyncio.Lock()

    # Diabetes risk model: a small sklearn Pipeline (StandardScaler +
    # calibrated XGBoost) trained on the CDC BRFSS 2015 Diabetes Health
    # Indicators dataset. Now serving diabetes-brfss-v2 (14 features) —
    # see ml_pipeline/diabetes/reports/v2_final_recommendation.md for why.
    # The original 21-feature diabetes-brfss-v1 artifact
    # (diabetes_pipeline.pkl + metadata.json) is deliberately left on disk
    # untouched as the immutable comparison baseline; production now loads
    # the v2 files instead. Loaded eagerly since it's cheap and keeps
    # request latency predictable and uniform for every caller, not just
    # the first one. The decision threshold and feature order live only in
    # the metadata file (not inside the pickle), so both files are loaded
    # and cross-validated together; a missing/malformed metadata file
    # fails loudly here rather than the service silently guessing a
    # threshold.
    try:
        diabetes_artifacts_dir = Path(base_dir) / "ml_pipeline" / "diabetes" / "artifacts"
        app.state.diabetes_model, app.state.diabetes_model_metadata = load_diabetes_model(
            diabetes_artifacts_dir / "diabetes_pipeline_v2.pkl",
            diabetes_artifacts_dir / "diabetes_metadata_v2.json",
        )
        logger.info(
            f"Loaded diabetes risk model {app.state.diabetes_model_metadata.get('model_version')} "
            f"from {diabetes_artifacts_dir}"
        )
    except Exception as e:
        logger.error(f"Failed to load diabetes risk model: {e}")
        app.state.diabetes_model = None
        app.state.diabetes_model_metadata = None


    # Heart Disease Risk model: a small sklearn Pipeline (StandardScaler +
    # calibrated XGBoost) trained on the CDC BRFSS 2022 dataset.
    # Loaded eagerly alongside the diabetes model — both are lightweight
    # joblib artifacts. The metadata file is the single source of truth for
    # the decision threshold and feature order; a missing/malformed metadata
    # file fails loudly here rather than silently guessing defaults.
    try:
        heart_model_dir  = Path(__file__).parent / "ai" / "models"
        heart_metadata_path = (
            Path(base_dir) / "ml_pipeline" / "heart" / "artifacts" / "heart_metadata.json"
        )
        app.state.heart_model, app.state.heart_model_metadata = load_heart_model(
            heart_model_dir / "heart_disease_model.pkl",
            heart_metadata_path,
        )
        logger.info(
            f"Loaded heart disease risk model "
            f"{app.state.heart_model_metadata.get('model_version')} "
            f"from {heart_model_dir}"
        )
    except Exception as e:
        logger.error(f"Failed to load heart disease risk model: {e}")
        app.state.heart_model          = None
        app.state.heart_model_metadata = None

    # Load Heart Clinical model
    try:
        clinical_model_dir = Path(base_dir) / "ml_pipeline" / "heart_clinical"
        app.state.heart_clinical_model = joblib.load(clinical_model_dir / "heart_clinical_model.pkl")
        app.state.heart_clinical_scaler = joblib.load(clinical_model_dir / "scaler.pkl")
        logger.info(f"Loaded heart clinical model from {clinical_model_dir}")
    except Exception as e:
        logger.error(f"Failed to load heart clinical model: {e}")
        app.state.heart_clinical_model = None
        app.state.heart_clinical_scaler = None

    # Liver risk model: a lab-free sklearn Pipeline trained on pooled NHANES
    # 2013-2018 survey/exam data (age, sex, BMI, waist circumference,
    # self-rated health, alcohol/smoking/activity habits, previously
    # diagnosed diabetes/hypertension) — no LFT/blood values required. The
    # original liver-ilpd-v1 (which required an LFT panel as input, and so
    # added no triage value — see ml_pipeline/liver/reports/evaluation_nhanes.md)
    # is deliberately left on disk untouched as the immutable comparison
    # baseline; production loads liver-nhanes-v1. A candidate v2 (with
    # general_health removed) was trained and evaluated but NOT adopted —
    # see ml_pipeline/liver/reports/v2_general_health_removal.md — because
    # removing general_health from diabetes-brfss-v3 (the sibling attempt)
    # caused an unacceptable false-positive regression, and the same
    # feature-removal decision was reverted for both models for consistency.
    try:
        liver_artifacts_dir = Path(base_dir) / "ml_pipeline" / "liver" / "artifacts"
        app.state.liver_model, app.state.liver_model_metadata = load_liver_model(
            liver_artifacts_dir / "liver_pipeline_nhanes_v1.pkl",
            liver_artifacts_dir / "liver_metadata_nhanes_v1.json",
        )
        logger.info(
            f"Loaded liver risk model {app.state.liver_model_metadata.get('model_version')} "
            f"from {liver_artifacts_dir}"
        )
    except Exception as e:
        logger.error(f"Failed to load liver risk model: {e}")
        app.state.liver_model = None
        app.state.liver_model_metadata = None

    # Diabetes risk model, LAB-BASED (Pima): a second, independent diabetes
    # model — the "I have recent lab results" counterpart to diabetes-brfss-v2
    # above. Trained on the Pima Indians Diabetes Database (NIDDK/UCI, Smith
    # et al. 1988, see ml_pipeline/diabetes_pima/README.md). Requires an
    # actual glucose reading, blood pressure, BMI, and skinfold measurement
    # — not lab-free, and trained on a narrow population (female, Pima
    # Indian heritage, 21+). Never merged or blended with the BRFSS model.
    try:
        diabetes_pima_artifacts_dir = Path(base_dir) / "ml_pipeline" / "diabetes_pima" / "artifacts"
        app.state.diabetes_pima_model, app.state.diabetes_pima_model_metadata = load_diabetes_pima_model(
            diabetes_pima_artifacts_dir / "diabetes_pima_pipeline_v1.pkl",
            diabetes_pima_artifacts_dir / "diabetes_pima_metadata_v1.json",
        )
        logger.info(
            f"Loaded diabetes (Pima) risk model {app.state.diabetes_pima_model_metadata.get('model_version')} "
            f"from {diabetes_pima_artifacts_dir}"
        )
    except Exception as e:
        logger.error(f"Failed to load diabetes (Pima) risk model: {e}")
        app.state.diabetes_pima_model = None
        app.state.diabetes_pima_model_metadata = None

    # Liver risk model, LAB-BASED (ILPD): a second, independent liver model —
    # the "I have my lab report" counterpart to liver-nhanes-v1 above.
    # Trained on the canonical UCI ILPD dataset (583 rows, see
    # ml_pipeline/liver/reports/ilpd_final_model_report.md). This is a
    # LOCKED artifact: load_liver_ilpd_model() verifies its SHA-256
    # checksum before loading and raises ArtifactIntegrityError if it has
    # drifted — that exception is deliberately allowed to propagate into
    # this try/except like any other load failure, so a checksum mismatch
    # disables the endpoint (503) rather than silently serving predictions
    # from an unverified file. Explicitly NOT trained on the rejected
    # liver_lpd dataset (see
    # ml_pipeline/liver_lpd/reports/data_integrity_investigation.md).
    # Never merged or blended with liver-nhanes-v1.
    try:
        liver_ilpd_artifacts_dir = Path(base_dir) / "ml_pipeline" / "liver" / "artifacts"
        app.state.liver_ilpd_model, app.state.liver_ilpd_model_metadata = load_liver_ilpd_model(
            liver_ilpd_artifacts_dir / "liver_ilpd_logistic_v1.pkl",
            liver_ilpd_artifacts_dir / "liver_ilpd_logistic_metadata_v1.json",
        )
        logger.info(
            f"Loaded liver risk model (ILPD) {app.state.liver_ilpd_model_metadata.get('model_version')} "
            f"from {liver_ilpd_artifacts_dir}"
        )
    except Exception as e:
        logger.error(f"Failed to load liver risk model (ILPD): {e}")
        app.state.liver_ilpd_model = None
        app.state.liver_ilpd_model_metadata = None

    # Load Skin Disease PyTorch model
    # Load Skin Disease PyTorch model (Eager Loading)
    try:
        from app.ai.models.skin_model import load_skin_model
        skin_ckpt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai", "models", "skin_cnn.pt")
        
        if os.path.exists(skin_ckpt):
            app.state.skin_model, app.state.skin_idx_to_class = load_skin_model(skin_ckpt)
            logger.info(f"Loaded Skin Disease CNN model eagerly from {skin_ckpt}")
        else:
            logger.warning(f"Skin Disease CNN checkpoint not found at {skin_ckpt}. Endpoints will return 503.")
            app.state.skin_model = None
            app.state.skin_idx_to_class = None
    except Exception as e:
        logger.error(f"Failed to eagerly load Skin Disease CNN model: {e}")
        app.state.skin_model = None
        app.state.skin_idx_to_class = None
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-Powered Personalized Healthcare Ecosystem API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "project": settings.PROJECT_NAME}

# reload trigger
