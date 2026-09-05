from fastapi import APIRouter
from app.api.v1.endpoints import auth, health_profile, predict

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(predict.router, prefix="/predict", tags=["predict"])
api_router.include_router(health_profile.router, prefix="/health-profile", tags=["health-profile"])
# Placeholders for future routers
# api_router.include_router(users.router, prefix="/users", tags=["users"])
