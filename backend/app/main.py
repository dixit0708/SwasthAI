from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.ai.models.pneumonia_cnn import load_pneumonia_model
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
        ckpt_path = os.path.join(base_dir, "ml-services", "cnn-detector", "checkpoints", "resnet18_finetuned.pt")
        
        app.state.pneumonia_model = load_pneumonia_model(ckpt_path)
        logger.info(f"Loaded Pneumonia CNN model from {ckpt_path}")
    except Exception as e:
        logger.error(f"Failed to load Pneumonia CNN model: {e}")
        app.state.pneumonia_model = None
        
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
