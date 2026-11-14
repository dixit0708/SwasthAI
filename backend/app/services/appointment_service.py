"""Appointment scheduling and management (synopsis Module 5).

What this is: the user's own schedule of visits to doctors and clinics in
the SwasthAI directory, with reschedule, confirm, complete and cancel.

What this is not: a booking made with the clinic. SwasthAI has no
clinic-side system and does not contact the clinic, so a new appointment
starts as "scheduled" and the user is asked to call the clinic to confirm.
Presenting it as confirmed by the clinic would be fabricating an
appointment (AGENTS.md Section 23).

Every query is scoped to the owning user_id (AGENTS.md Section 14).
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId

from app.db.collections import appointment_repo, family_member_repo
from app.models.appointment import AppointmentCreate, AppointmentUpdate
from app.services import doctor_directory_service

MAX_PAGE_SIZE = 50
ACTIVE_STATUSES = ["scheduled", "confirmed"]


class AppointmentNotFound(Exception):
    pass


class AppointmentConflict(Exception):
    pass


def _is_upcoming(doc: Dict[str, Any]) -> bool:
    return doc.get("status") in ACTIVE_STATUSES and doc.get("appointment_date", "") >= date.today().isoformat()


def _to_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "doctor_id": doc["doctor_id"],
        "doctor_name": doc.get("doctor_name", ""),
        "clinic_name": doc.get("clinic_name"),
        "address": doc.get("address"),
        "city": doc.get("city"),
        "phone": doc.get("phone"),
        "phone_dial": doc.get("phone_dial"),
        "timings": doc.get("timings"),
        "directions_url": doc.get("directions_url"),
        "appointment_date": doc["appointment_date"],
        "appointment_time": doc["appointment_time"],
        "reason": doc.get("reason"),
        "status": doc.get("status", "scheduled"),
        "family_member_id": doc.get("family_member_id"),
        "patient_name": doc.get("patient_name"),
        "is_upcoming": _is_upcoming(doc),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def _ensure_no_clash(
    user_id: str, appointment_date: str, appointment_time: str, exclude_id: Optional[ObjectId] = None
) -> None:
    """A user cannot hold two active appointments at the same date and time."""
    query: Dict[str, Any] = {
        "user_id": user_id,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "status": {"$in": ACTIVE_STATUSES},
    }
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    if await appointment_repo.collection.find_one(query):
        raise AppointmentConflict("You already have an appointment at this date and time.")


async def create_appointment(user_id: str, payload: AppointmentCreate) -> Dict[str, Any]:
    # Raises DoctorNotFound for an unknown or inactive listing.
    doctor = await doctor_directory_service.get_doctor(payload.doctor_id)

    patient_name: Optional[str] = None
    family_member_id: Optional[str] = None
    if payload.family_member_id:
        member = None
        if ObjectId.is_valid(payload.family_member_id):
            member = await family_member_repo.collection.find_one(
                {"_id": ObjectId(payload.family_member_id), "user_id": user_id}
            )
        if not member:
            raise ValueError("Family member not found.")
        family_member_id = payload.family_member_id
        patient_name = member.get("name")

    appointment_date = payload.appointment_date.isoformat()
    await _ensure_no_clash(user_id, appointment_date, payload.appointment_time)

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "doctor_id": doctor.id,
        # Snapshot of the listing, so the appointment still reads correctly
        # if the directory entry later changes or is removed.
        "doctor_name": doctor.name,
        "clinic_name": doctor.clinic_name,
        "address": doctor.address,
        "city": doctor.city,
        "phone": doctor.phone,
        "phone_dial": doctor.phone_dial,
        "timings": doctor.timings,
        "directions_url": doctor.directions_url,
        "appointment_date": appointment_date,
        "appointment_time": payload.appointment_time,
        "reason": payload.reason.strip() if payload.reason and payload.reason.strip() else None,
        "status": "scheduled",
        "family_member_id": family_member_id,
        "patient_name": patient_name,
        "created_at": now,
        "updated_at": now,
    }
    result = await appointment_repo.collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_out(doc)


async def list_appointments(
    user_id: str, view: str = "upcoming", page: int = 1, page_size: int = 10
) -> Dict[str, Any]:
    """view: "upcoming" (active, today onward, soonest first), "past"
    (everything else, newest first) or "all"."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    today = date.today().isoformat()

    query: Dict[str, Any] = {"user_id": user_id}
    sort = [("appointment_date", -1), ("appointment_time", -1)]
    if view == "upcoming":
        query["status"] = {"$in": ACTIVE_STATUSES}
        query["appointment_date"] = {"$gte": today}
        sort = [("appointment_date", 1), ("appointment_time", 1)]
    elif view == "past":
        query["$or"] = [
            {"status": {"$nin": ACTIVE_STATUSES}},
            {"appointment_date": {"$lt": today}},
        ]
    elif view != "all":
        raise ValueError("view must be upcoming, past or all.")

    total = await appointment_repo.collection.count_documents(query)
    cursor = appointment_repo.collection.find(query).sort(sort).skip((page - 1) * page_size).limit(page_size)
    docs = await cursor.to_list(length=page_size)
    return {"items": [_to_out(d) for d in docs], "total": total, "page": page, "page_size": page_size}


async def _get_owned(user_id: str, appointment_id: str) -> Dict[str, Any]:
    if not ObjectId.is_valid(appointment_id):
        raise AppointmentNotFound("Appointment not found.")
    doc = await appointment_repo.collection.find_one({"_id": ObjectId(appointment_id), "user_id": user_id})
    if not doc:
        raise AppointmentNotFound("Appointment not found.")
    return doc


async def get_appointment(user_id: str, appointment_id: str) -> Dict[str, Any]:
    return _to_out(await _get_owned(user_id, appointment_id))


async def update_appointment(user_id: str, appointment_id: str, payload: AppointmentUpdate) -> Dict[str, Any]:
    doc = await _get_owned(user_id, appointment_id)
    sent = payload.model_fields_set
    fields: Dict[str, Any] = {}

    new_date = payload.appointment_date.isoformat() if payload.appointment_date else doc["appointment_date"]
    new_time = payload.appointment_time or doc["appointment_time"]
    rescheduled = new_date != doc["appointment_date"] or new_time != doc["appointment_time"]

    if rescheduled:
        if doc.get("status") not in ACTIVE_STATUSES:
            raise ValueError("Only an upcoming appointment can be rescheduled.")
        await _ensure_no_clash(user_id, new_date, new_time, exclude_id=doc["_id"])
        fields["appointment_date"] = new_date
        fields["appointment_time"] = new_time
        # A new slot has not been agreed with the clinic yet.
        fields["status"] = "scheduled"

    if "reason" in sent:
        fields["reason"] = payload.reason.strip() if payload.reason and payload.reason.strip() else None

    if payload.status is not None and not (rescheduled and payload.status == "confirmed"):
        if doc.get("status") == "cancelled" and payload.status != "cancelled":
            raise ValueError("A cancelled appointment cannot be reopened. Please schedule a new one.")
        fields["status"] = payload.status

    if fields:
        fields["updated_at"] = datetime.now(timezone.utc)
        await appointment_repo.collection.update_one(
            {"_id": doc["_id"], "user_id": user_id}, {"$set": fields}
        )
        doc.update(fields)
    return _to_out(doc)


async def delete_appointment(user_id: str, appointment_id: str) -> None:
    doc = await _get_owned(user_id, appointment_id)
    await appointment_repo.collection.delete_one({"_id": doc["_id"], "user_id": user_id})
