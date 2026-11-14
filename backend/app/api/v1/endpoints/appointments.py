from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_user
from app.models.appointment import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentOut,
    AppointmentUpdate,
)
from app.models.user import UserOut
from app.services import appointment_service
from app.services.appointment_service import AppointmentConflict, AppointmentNotFound
from app.services.doctor_directory_service import DoctorNotFound

router = APIRouter()


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def schedule_appointment(
    payload: AppointmentCreate,
    current_user: UserOut = Depends(get_current_user),
):
    """Adds a visit to the user's schedule. SwasthAI does not contact the
    clinic: the appointment starts as "scheduled" until the user confirms
    it with the clinic."""
    try:
        return await appointment_service.create_appointment(current_user.id, payload)
    except DoctorNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AppointmentConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    view: str = Query("upcoming", pattern="^(upcoming|past|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: UserOut = Depends(get_current_user),
):
    return await appointment_service.list_appointments(
        current_user.id, view=view, page=page, page_size=page_size
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
async def get_appointment(
    appointment_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    try:
        return await appointment_service.get_appointment(current_user.id, appointment_id)
    except AppointmentNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    """Reschedule, confirm, complete or cancel an appointment."""
    try:
        return await appointment_service.update_appointment(current_user.id, appointment_id, payload)
    except AppointmentNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AppointmentConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{appointment_id}", status_code=status.HTTP_200_OK)
async def delete_appointment(
    appointment_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    try:
        await appointment_service.delete_appointment(current_user.id, appointment_id)
    except AppointmentNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"message": "Appointment removed"}
