"""Appointment models.

SwasthAI has no clinic-side system, so an appointment here is the user's
own schedule entry for a visit to a listed doctor or clinic. It is never
presented as confirmed by the clinic: the user confirms with the clinic
directly and then marks it confirmed (see appointment_service.py).
"""
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

AppointmentStatus = Literal["scheduled", "confirmed", "completed", "cancelled"]

_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class AppointmentCreate(BaseModel):
    doctor_id: str
    appointment_date: date
    # 24-hour HH:MM, clinic local time.
    appointment_time: str = Field(pattern=_TIME_PATTERN)
    reason: Optional[str] = Field(default=None, max_length=300)
    # Optional: the visit is for one of the user's family members.
    family_member_id: Optional[str] = None

    @field_validator("appointment_date")
    @classmethod
    def _not_in_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Appointment date cannot be in the past.")
        return value


class AppointmentUpdate(BaseModel):
    """Reschedule (date/time), change status, or edit the reason."""

    appointment_date: Optional[date] = None
    appointment_time: Optional[str] = Field(default=None, pattern=_TIME_PATTERN)
    reason: Optional[str] = Field(default=None, max_length=300)
    status: Optional[AppointmentStatus] = None

    @field_validator("appointment_date")
    @classmethod
    def _not_in_past(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value < date.today():
            raise ValueError("Appointment date cannot be in the past.")
        return value


class AppointmentOut(BaseModel):
    id: str
    doctor_id: str
    doctor_name: str
    clinic_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    # Only present for doctors who agreed to be listed with their number.
    phone: Optional[str] = None
    phone_dial: Optional[str] = None
    timings: Optional[str] = None
    directions_url: Optional[str] = None
    appointment_date: date
    appointment_time: str
    reason: Optional[str] = None
    status: AppointmentStatus
    family_member_id: Optional[str] = None
    # Who the visit is for: the family member's name, or None for the user.
    patient_name: Optional[str] = None
    is_upcoming: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AppointmentListResponse(BaseModel):
    items: List[AppointmentOut]
    total: int
    page: int
    page_size: int
