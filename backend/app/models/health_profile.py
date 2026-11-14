from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Gender = Literal["female", "male", "other", "prefer_not_to_say"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active"]
DietPreference = Literal["vegetarian", "eggetarian", "non_vegetarian", "vegan", "jain"]
# The shape of the user's day, which decides meal timing and lifestyle tips.
Occupation = Literal["student", "working_professional", "night_shift", "homemaker", "physical_work", "retired"]
# The regional food the user usually eats, which decides the staples suggested.
CuisineRegion = Literal["north", "south", "east", "west", "mixed"]
SmokingStatus = Literal["never", "former", "current"]
AlcoholUse = Literal["none", "occasional", "regular"]

MAX_ALLERGIES = 30


class Condition(BaseModel):
    id: str
    label: str


class HealthProfileUpdate(BaseModel):
    """Partial update: only the fields present in the request are changed.
    Sending a field as null (or an empty string) clears it."""

    date_of_birth: Optional[date] = None
    blood_group: Optional[str] = Field(default=None, max_length=10)
    gender: Optional[Gender] = None
    # Metric units throughout (AGENTS.md Section 57).
    height_cm: Optional[float] = Field(default=None, ge=30, le=260)
    weight_kg: Optional[float] = Field(default=None, ge=1, le=400)
    allergies: Optional[List[str]] = None
    activity_level: Optional[ActivityLevel] = None
    diet_preference: Optional[DietPreference] = None
    smoking_status: Optional[SmokingStatus] = None
    alcohol_use: Optional[AlcoholUse] = None
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    occupation_type: Optional[Occupation] = None
    cuisine_region: Optional[CuisineRegion] = None

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data):
        # HTML forms submit "" for an untouched select/date/number input.
        if isinstance(data, dict):
            return {k: (None if isinstance(v, str) and not v.strip() else v) for k, v in data.items()}
        return data

    @field_validator("date_of_birth")
    @classmethod
    def _dob_not_in_future(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return value

    @field_validator("allergies")
    @classmethod
    def _clean_allergies(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned: List[str] = []
        for item in value:
            label = (item or "").strip()
            if not label:
                continue
            if len(label) > 100:
                raise ValueError("Each allergy must be 100 characters or fewer.")
            if label.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(label)
        if len(cleaned) > MAX_ALLERGIES:
            raise ValueError(f"You can list up to {MAX_ALLERGIES} allergies.")
        return cleaned


class ConditionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)


class HealthProfileOut(BaseModel):
    date_of_birth: Optional[date] = None
    # Derived from date_of_birth; never stored.
    age: Optional[int] = None
    blood_group: Optional[str] = None
    gender: Optional[Gender] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    # Derived from height and weight; never stored.
    bmi: Optional[float] = None
    allergies: List[str] = []
    activity_level: Optional[ActivityLevel] = None
    diet_preference: Optional[DietPreference] = None
    smoking_status: Optional[SmokingStatus] = None
    alcohol_use: Optional[AlcoholUse] = None
    sleep_hours: Optional[float] = None
    occupation_type: Optional[Occupation] = None
    cuisine_region: Optional[CuisineRegion] = None
    conditions: List[Condition] = []
