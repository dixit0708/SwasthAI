from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.ai.models.pneumonia_cnn import load_pneumonia_model
from app.ai.models.diabetes_model import load_diabetes_model
import logging
import os

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    
    # Load PyTorch model
    try:
        # Assuming app/main.py is 3 levels deep from SwasthAI root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Pneumonia model
        pneumonia_ckpt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai", "models", "pneumonia_cnn.pt")
        app.state.pneumonia_model = load_pneumonia_model(pneumonia_ckpt)
        logger.info(f"Loaded Pneumonia CNN model from {pneumonia_ckpt}")
    except Exception as e:
        logger.error(f"Failed to load Pneumonia CNN model: {e}")
        app.state.pneumonia_model = None

    # Load diabetes risk model
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        diabetes_model_path = os.path.join(base_dir, "ml_pipeline", "diabetes", "models", "diabetes_model.joblib")

        app.state.diabetes_model = load_diabetes_model(diabetes_model_path)
        logger.info(f"Loaded diabetes risk model from {diabetes_model_path}")
    except Exception as e:
        logger.error(f"Failed to load diabetes risk model: {e}")
        app.state.diabetes_model = None

    # Load Skin Disease PyTorch model
    try:
        from app.ai.models.skin_cnn import load_skin_model
        skin_ckpt = os.path.join(base_dir, "ml-services", "skin-disease-detector", "checkpoints", "skin_disease_resnet50.pt")
        
        if os.path.exists(skin_ckpt):
            app.state.skin_model = load_skin_model(skin_ckpt, num_classes=7)
            logger.info(f"Loaded Skin Disease CNN model from {skin_ckpt}")
        else:
            logger.warning(f"Skin Disease CNN model not found at {skin_ckpt}. Please train the model first.")
            app.state.skin_model = None
    except Exception as e:
        logger.error(f"Failed to load Skin Disease CNN model: {e}")
        app.state.skin_model = None
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
