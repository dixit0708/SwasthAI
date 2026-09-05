import uuid
from datetime import date, datetime, timezone

from app.db.collections import health_profile_repo
from app.models.health_profile import Condition, HealthProfileOut, HealthProfileUpdate


def _to_out(doc: dict | None) -> HealthProfileOut:
    if not doc:
        return HealthProfileOut()
    dob = doc.get("date_of_birth")
    return HealthProfileOut(
        date_of_birth=date.fromisoformat(dob) if dob else None,
        blood_group=doc.get("blood_group"),
        conditions=[Condition(**c) for c in doc.get("conditions", [])],
    )


async def get_profile(user_id: str) -> HealthProfileOut:
    doc = await health_profile_repo.collection.find_one({"user_id": user_id})
    return _to_out(doc)


async def update_basic_info(user_id: str, payload: HealthProfileUpdate) -> HealthProfileOut:
    fields = {}
    if payload.date_of_birth is not None:
        fields["date_of_birth"] = payload.date_of_birth.isoformat()
    if payload.blood_group is not None:
        fields["blood_group"] = payload.blood_group or None
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
