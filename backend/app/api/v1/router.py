from fastapi import APIRouter
from app.api.v1.endpoints import auth, predict

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(predict.router, prefix="/predict", tags=["predict"])
# Placeholders for future routers
# api_router.include_router(users.router, prefix="/users", tags=["users"])
