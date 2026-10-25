import re
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


def _validate_phone_field(v: Optional[str], field_name: str = "Phone number") -> Optional[str]:
    if not v or not v.strip():
        return None
    trimmed = v.strip()
    digits = re.sub(r"\D", "", trimmed)
    if not digits:
        return trimmed
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError(f"{field_name} must contain between 10 and 15 digits.")
    if len(set(digits)) == 1:
        raise ValueError(f"{field_name} cannot consist of repeating dummy digits.")
    if digits in ("1234567890", "0123456789"):
        raise ValueError(f"Please provide a realistic {field_name.lower()}.")
    return trimmed


class MedicalHistoryItem(BaseModel):
    id: str
    title: str
    category: str = "condition"  # condition, allergy, surgery, family_history, other
    diagnosed_date: Optional[str] = None
    status: str = "ongoing"  # ongoing, resolved, in_management
    doctor_or_hospital: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class MedicalHistoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(default="condition", max_length=50)
    diagnosed_date: Optional[str] = None
    status: str = Field(default="ongoing", max_length=30)
    doctor_or_hospital: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)


class MedicalHistoryUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=50)
    diagnosed_date: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=30)
    doctor_or_hospital: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)


class FamilyMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    relationship: str = Field(min_length=1, max_length=50)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=30)
    blood_group: Optional[str] = Field(default=None, max_length=10)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=100)
    emergency_contact: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)
    avatar_color: Optional[str] = Field(default=None, max_length=20)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob_not_future(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone_field(v, "Phone number")

    @field_validator("emergency_contact")
    @classmethod
    def validate_emergency(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone_field(v, "Emergency contact")


class FamilyMemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    relationship: Optional[str] = Field(default=None, min_length=1, max_length=50)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=30)
    blood_group: Optional[str] = Field(default=None, max_length=10)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=100)
    emergency_contact: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)
    avatar_color: Optional[str] = Field(default=None, max_length=20)
    is_archived: Optional[bool] = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob_not_future(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone_field(v, "Phone number")

    @field_validator("emergency_contact")
    @classmethod
    def validate_emergency(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone_field(v, "Emergency contact")


class FamilyMemberOut(BaseModel):
    id: str
    user_id: str
    name: str
    relationship: str
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    emergency_contact: Optional[str] = None
    notes: Optional[str] = None
    avatar_color: Optional[str] = None
    is_archived: bool = False
    medical_history: List[MedicalHistoryItem] = []
    records_count: int = 0
    medications_count: int = 0
    measurements_count: int = 0
    latest_activity_date: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MedicalRecordCreate(BaseModel):
    member_id: str
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    record_date: str
    provider: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)


class MedicalRecordUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, min_length=1, max_length=50)
    record_date: Optional[str] = None
    provider: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)


class MedicalRecordOut(BaseModel):
    id: str
    user_id: str
    member_id: str
    member_name: Optional[str] = None
    title: str
    category: str
    record_date: str
    provider: Optional[str] = None
    notes: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    has_document: bool = False
    created_at: Optional[datetime] = None


class MedicationCreate(BaseModel):
    member_id: str
    name: str = Field(min_length=1, max_length=200)
    dosage: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=100)
    instructions: Optional[str] = Field(default=None, max_length=500)
    prescribing_doctor: Optional[str] = Field(default=None, max_length=200)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = Field(default="active", max_length=30)
    notes: Optional[str] = Field(default=None, max_length=1000)
    linked_record_id: Optional[str] = None


class MedicationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    dosage: Optional[str] = Field(default=None, min_length=1, max_length=100)
    frequency: Optional[str] = Field(default=None, min_length=1, max_length=100)
    instructions: Optional[str] = Field(default=None, max_length=500)
    prescribing_doctor: Optional[str] = Field(default=None, max_length=200)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=30)
    notes: Optional[str] = Field(default=None, max_length=1000)
    linked_record_id: Optional[str] = None


class MedicationOut(BaseModel):
    id: str
    user_id: str
    member_id: str
    member_name: Optional[str] = None
    name: str
    dosage: str
    frequency: str
    instructions: Optional[str] = None
    prescribing_doctor: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    linked_record_id: Optional[str] = None
    created_at: Optional[datetime] = None


class HealthMeasurementCreate(BaseModel):
    member_id: str
    metric_type: str = Field(min_length=1, max_length=50)
    metric_name: str = Field(min_length=1, max_length=100)
    value: float
    value_secondary: Optional[float] = None
    unit: str = Field(min_length=1, max_length=30)
    recorded_date: str
    notes: Optional[str] = Field(default=None, max_length=500)


class HealthMeasurementOut(BaseModel):
    id: str
    user_id: str
    member_id: str
    member_name: Optional[str] = None
    metric_type: str
    metric_name: str
    value: float
    value_secondary: Optional[float] = None
    unit: str
    recorded_date: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class TimelineEventOut(BaseModel):
    id: str
    event_type: str  # document, history, medication, measurement
    title: str
    date: str
    description: str
    member_id: str
    member_name: str
    badge_color: str
    icon: str
    link_id: Optional[str] = None


class FamilyOverviewOut(BaseModel):
    total_members: int
    members_with_records: int
    total_records: int
    total_medications: int
    recent_records: List[MedicalRecordOut] = []
    active_medications: List[MedicationOut] = []
