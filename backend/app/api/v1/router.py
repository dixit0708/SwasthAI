from fastapi import APIRouter
from app.api.v1.endpoints import (
    appointments,
    assistant,
    auth,
    diet,
    doctors,
    family,
    health_profile,
    predict,
    report_analysis,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(predict.router, prefix="/predict", tags=["predict"])
api_router.include_router(health_profile.router, prefix="/health-profile", tags=["health-profile"])
api_router.include_router(family.router, prefix="/family", tags=["family"])
api_router.include_router(report_analysis.router, prefix="/report-analysis", tags=["report-analysis"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
api_router.include_router(diet.router, prefix="/diet", tags=["diet"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
# Placeholders for future routers
# api_router.include_router(users.router, prefix="/users", tags=["users"])

