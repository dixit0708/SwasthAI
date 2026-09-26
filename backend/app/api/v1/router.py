from fastapi import APIRouter
from app.api.v1.endpoints import auth, health_profile, predict, report_analysis

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(predict.router, prefix="/predict", tags=["predict"])
api_router.include_router(health_profile.router, prefix="/health-profile", tags=["health-profile"])
api_router.include_router(report_analysis.router, prefix="/report-analysis", tags=["report-analysis"])
# Placeholders for future routers
# api_router.include_router(users.router, prefix="/users", tags=["users"])
