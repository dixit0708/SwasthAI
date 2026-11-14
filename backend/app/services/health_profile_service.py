import uuid
from datetime import date, datetime, timezone
from typing import Optional

from app.db.collections import health_profile_repo
from app.models.health_profile import Condition, HealthProfileOut, HealthProfileUpdate

# Stored as-is; date_of_birth is handled separately (stored as an ISO string).
_SIMPLE_FIELDS = (
    "blood_group",
    "gender",
    "height_cm",
    "weight_kg",
    "allergies",
    "activity_level",
    "diet_preference",
    "smoking_status",
    "alcohol_use",
    "sleep_hours",
    "occupation_type",
    "cuisine_region",
)


def calculate_age(dob: Optional[date]) -> Optional[int]:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def calculate_bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    if not height_cm or not weight_kg:
        return None
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m * height_m), 1)


def _to_out(doc: dict | None) -> HealthProfileOut:
    if not doc:
        return HealthProfileOut()
    dob_raw = doc.get("date_of_birth")
    dob = date.fromisoformat(dob_raw) if dob_raw else None
    return HealthProfileOut(
        date_of_birth=dob,
        age=calculate_age(dob),
        blood_group=doc.get("blood_group"),
        gender=doc.get("gender"),
        height_cm=doc.get("height_cm"),
        weight_kg=doc.get("weight_kg"),
        bmi=calculate_bmi(doc.get("height_cm"), doc.get("weight_kg")),
        allergies=doc.get("allergies") or [],
        activity_level=doc.get("activity_level"),
        diet_preference=doc.get("diet_preference"),
        smoking_status=doc.get("smoking_status"),
        alcohol_use=doc.get("alcohol_use"),
        sleep_hours=doc.get("sleep_hours"),
        occupation_type=doc.get("occupation_type"),
        cuisine_region=doc.get("cuisine_region"),
        conditions=[Condition(**c) for c in doc.get("conditions", [])],
    )


async def get_profile(user_id: str) -> HealthProfileOut:
    doc = await health_profile_repo.collection.find_one({"user_id": user_id})
    return _to_out(doc)


async def update_basic_info(user_id: str, payload: HealthProfileUpdate) -> HealthProfileOut:
    # Only touch fields the client actually sent, so a form that edits one
    # part of the profile cannot wipe another. An explicit null clears a field.
    sent = payload.model_fields_set
    fields: dict = {}
    if "date_of_birth" in sent:
        fields["date_of_birth"] = payload.date_of_birth.isoformat() if payload.date_of_birth else None
    for name in _SIMPLE_FIELDS:
        if name in sent:
            value = getattr(payload, name)
            if name == "allergies" and value is None:
                value = []
            fields[name] = value
    fields["updated_at"] = datetime.now(timezone.utc)

    await health_profile_repo.collection.update_one(
        {"user_id": user_id},
        {
            "$set": fields,
            "$setOnInsert": {
                "user_id": user_id,
                "conditions": [],
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    return await get_profile(user_id)


async def add_condition(user_id: str, label: str) -> HealthProfileOut:
    condition = {"id": uuid.uuid4().hex, "label": label.strip()}
    await health_profile_repo.collection.update_one(
        {"user_id": user_id},
        {
            "$push": {"conditions": condition},
            "$set": {"updated_at": datetime.now(timezone.utc)},
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    return await get_profile(user_id)


async def remove_condition(user_id: str, condition_id: str) -> HealthProfileOut:
    await health_profile_repo.collection.update_one(
        {"user_id": user_id},
        {
            "$pull": {"conditions": {"id": condition_id}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    return await get_profile(user_id)
