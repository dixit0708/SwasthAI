from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class Condition(BaseModel):
    id: str
    label: str


class HealthProfileUpdate(BaseModel):
    date_of_birth: Optional[date] = None
    blood_group: Optional[str] = Field(default=None, max_length=10)


class ConditionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)


class HealthProfileOut(BaseModel):
    date_of_birth: Optional[date] = None
    blood_group: Optional[str] = None
    conditions: List[Condition] = []
