import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.ai.models.diabetes_model import load_diabetes_model

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
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app.state.pneumonia_ckpt_path = os.path.join(
        base_dir, "ml-services", "cnn-detector", "checkpoints", "resnet18_finetuned.pt"
    )
    app.state.pneumonia_model = None
    app.state.pneumonia_model_lock = asyncio.Lock()

    # Diabetes risk model: a small sklearn Pipeline, loaded eagerly since
    # it's cheap (no heavy import chain) and keeps request latency
    # predictable and uniform for every caller, not just the first one.
    try:
        diabetes_model_path = os.path.join(base_dir, "ml_pipeline", "diabetes", "models", "diabetes_model.joblib")

        app.state.diabetes_model = load_diabetes_model(diabetes_model_path)
        logger.info(f"Loaded diabetes risk model from {diabetes_model_path}")
    except Exception as e:
        logger.error(f"Failed to load diabetes risk model: {e}")
        app.state.diabetes_model = None

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
