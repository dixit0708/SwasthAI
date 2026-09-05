from fastapi import APIRouter, Depends, status

from app.api.v1.deps import get_current_user
from app.models.health_profile import (
    ConditionCreate,
    HealthProfileOut,
    HealthProfileUpdate,
)
from app.models.user import UserOut
from app.services import health_profile_service

router = APIRouter()


@router.get("/me", response_model=HealthProfileOut)
async def get_my_health_profile(current_user: UserOut = Depends(get_current_user)):
    return await health_profile_service.get_profile(current_user.id)


@router.put("/me", response_model=HealthProfileOut)
async def update_my_health_profile(
    payload: HealthProfileUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    return await health_profile_service.update_basic_info(current_user.id, payload)


@router.post("/me/conditions", response_model=HealthProfileOut, status_code=status.HTTP_201_CREATED)
async def add_condition(
    payload: ConditionCreate,
    current_user: UserOut = Depends(get_current_user),
):
    return await health_profile_service.add_condition(current_user.id, payload.label)


@router.delete("/me/conditions/{condition_id}", response_model=HealthProfileOut)
async def delete_condition(
    condition_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    return await health_profile_service.remove_condition(current_user.id, condition_id)
