import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId

from app.db.collections import (
    family_member_repo,
    medical_record_repo,
    medication_repo,
    health_metric_repo,
)
from app.models.family import (
    FamilyMemberCreate,
    FamilyMemberOut,
    FamilyMemberUpdate,
    FamilyOverviewOut,
    HealthMeasurementCreate,
    HealthMeasurementOut,
    MedicalHistoryCreate,
    MedicalHistoryItem,
    MedicalHistoryUpdate,
    MedicalRecordCreate,
    MedicalRecordOut,
    MedicalRecordUpdate,
    MedicationCreate,
    MedicationOut,
    MedicationUpdate,
    TimelineEventOut,
)

# Storage location for medical documents
BASE_DIR = Path(__file__).resolve().parents[3]
STORAGE_DIR = BASE_DIR / "storage" / "documents"

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB


def _calculate_age(dob: Optional[date]) -> Optional[int]:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _ensure_storage_dir(user_id: str) -> Path:
    user_dir = STORAGE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


# ---------------------------------------------------------------------------
# Family Member Management
# ---------------------------------------------------------------------------

async def list_members(user_id: str, include_archived: bool = False) -> List[FamilyMemberOut]:
    query: Dict[str, Any] = {"user_id": user_id}
    if not include_archived:
        query["is_archived"] = {"$ne": True}

    cursor = family_member_repo.collection.find(query).sort("created_at", 1)
    member_docs = await cursor.to_list(length=100)

    results = []
    for doc in member_docs:
        member_id = str(doc["_id"])
        # Counts for badges and stats
        records_count = await medical_record_repo.collection.count_documents(
            {"user_id": user_id, "member_id": member_id}
        )
        meds_count = await medication_repo.collection.count_documents(
            {"user_id": user_id, "member_id": member_id, "status": "active"}
        )
        vitals_count = await health_metric_repo.collection.count_documents(
            {"user_id": user_id, "member_id": member_id}
        )

        dob_val = doc.get("date_of_birth")
        dob = date.fromisoformat(dob_val) if dob_val else None

        # Determine latest activity date
        latest_record = await medical_record_repo.collection.find_one(
            {"user_id": user_id, "member_id": member_id},
            sort=[("record_date", -1)],
        )
        latest_activity = latest_record.get("record_date") if latest_record else None

        history_items = [
            MedicalHistoryItem(**h) for h in doc.get("medical_history", [])
        ]

        results.append(
            FamilyMemberOut(
                id=member_id,
                user_id=doc["user_id"],
                name=doc["name"],
                relationship=doc["relationship"],
                date_of_birth=dob,
                age=_calculate_age(dob),
                gender=doc.get("gender"),
                blood_group=doc.get("blood_group"),
                phone=doc.get("phone"),
                email=doc.get("email"),
                emergency_contact=doc.get("emergency_contact"),
                notes=doc.get("notes"),
                avatar_color=doc.get("avatar_color", "#0F766E"),
                is_archived=doc.get("is_archived", False),
                medical_history=history_items,
                records_count=records_count,
                medications_count=meds_count,
                measurements_count=vitals_count,
                latest_activity_date=latest_activity,
                created_at=doc.get("created_at"),
                updated_at=doc.get("updated_at"),
            )
        )
    return results


async def get_member(user_id: str, member_id: str) -> Optional[FamilyMemberOut]:
    if not ObjectId.is_valid(member_id):
        return None
    doc = await family_member_repo.collection.find_one(
        {"_id": ObjectId(member_id), "user_id": user_id}
    )
    if not doc:
        return None

    dob_val = doc.get("date_of_birth")
    dob = date.fromisoformat(dob_val) if dob_val else None

    records_count = await medical_record_repo.collection.count_documents(
        {"user_id": user_id, "member_id": member_id}
    )
    meds_count = await medication_repo.collection.count_documents(
        {"user_id": user_id, "member_id": member_id, "status": "active"}
    )
    vitals_count = await health_metric_repo.collection.count_documents(
        {"user_id": user_id, "member_id": member_id}
    )

    history_items = [
        MedicalHistoryItem(**h) for h in doc.get("medical_history", [])
    ]

    return FamilyMemberOut(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        name=doc["name"],
        relationship=doc["relationship"],
        date_of_birth=dob,
        age=_calculate_age(dob),
        gender=doc.get("gender"),
        blood_group=doc.get("blood_group"),
        phone=doc.get("phone"),
        email=doc.get("email"),
        emergency_contact=doc.get("emergency_contact"),
        notes=doc.get("notes"),
        avatar_color=doc.get("avatar_color", "#0F766E"),
        is_archived=doc.get("is_archived", False),
        medical_history=history_items,
        records_count=records_count,
        medications_count=meds_count,
        measurements_count=vitals_count,
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


async def create_member(user_id: str, payload: FamilyMemberCreate) -> FamilyMemberOut:
    now = datetime.now(timezone.utc)
    avatar_color = payload.avatar_color or "#0F766E"

    doc = {
        "user_id": user_id,
        "name": payload.name.strip(),
        "relationship": payload.relationship.strip(),
        "date_of_birth": payload.date_of_birth.isoformat() if payload.date_of_birth else None,
        "gender": payload.gender,
        "blood_group": payload.blood_group,
        "phone": payload.phone.strip() if payload.phone else None,
        "email": payload.email.strip() if payload.email else None,
        "emergency_contact": payload.emergency_contact.strip() if payload.emergency_contact else None,
        "notes": payload.notes.strip() if payload.notes else None,
        "avatar_color": avatar_color,
        "is_archived": False,
        "medical_history": [],
        "created_at": now,
        "updated_at": now,
    }

    result = await family_member_repo.collection.insert_one(doc)
    created_id = str(result.inserted_id)
    return (await get_member(user_id, created_id))  # type: ignore


async def update_member(
    user_id: str, member_id: str, payload: FamilyMemberUpdate
) -> Optional[FamilyMemberOut]:
    if not ObjectId.is_valid(member_id):
        return None

    fields: Dict[str, Any] = {}
    if payload.name is not None:
        fields["name"] = payload.name.strip()
    if payload.relationship is not None:
        fields["relationship"] = payload.relationship.strip()
    if payload.date_of_birth is not None:
        fields["date_of_birth"] = payload.date_of_birth.isoformat()
    if payload.gender is not None:
        fields["gender"] = payload.gender
    if payload.blood_group is not None:
        fields["blood_group"] = payload.blood_group
    if payload.phone is not None:
        fields["phone"] = payload.phone.strip() if payload.phone else None
    if payload.email is not None:
        fields["email"] = payload.email.strip() if payload.email else None
    if payload.emergency_contact is not None:
        fields["emergency_contact"] = payload.emergency_contact.strip() if payload.emergency_contact else None
    if payload.notes is not None:
        fields["notes"] = payload.notes.strip() if payload.notes else None
    if payload.avatar_color is not None:
        fields["avatar_color"] = payload.avatar_color
    if payload.is_archived is not None:
        fields["is_archived"] = payload.is_archived

    if not fields:
        return await get_member(user_id, member_id)

    fields["updated_at"] = datetime.now(timezone.utc)

    result = await family_member_repo.collection.update_one(
        {"_id": ObjectId(member_id), "user_id": user_id},
        {"$set": fields},
    )
    if result.matched_count == 0:
        return None
    return await get_member(user_id, member_id)


async def delete_member(user_id: str, member_id: str, cascade: bool = True) -> bool:
    if not ObjectId.is_valid(member_id):
        return False

    member = await family_member_repo.collection.find_one(
        {"_id": ObjectId(member_id), "user_id": user_id}
    )
    if not member:
        return False

    if cascade:
        # Delete related files from disk
        records = await medical_record_repo.collection.find(
            {"user_id": user_id, "member_id": member_id}
        ).to_list(length=500)
        for r in records:
            if r.get("file_path"):
                fp = STORAGE_DIR / r["file_path"]
                if fp.exists():
                    try:
                        fp.unlink()
                    except OSError:
                        pass
        await medical_record_repo.collection.delete_many(
            {"user_id": user_id, "member_id": member_id}
        )
        await medication_repo.collection.delete_many(
            {"user_id": user_id, "member_id": member_id}
        )
        await health_metric_repo.collection.delete_many(
            {"user_id": user_id, "member_id": member_id}
        )

    res = await family_member_repo.collection.delete_one(
        {"_id": ObjectId(member_id), "user_id": user_id}
    )
    return res.deleted_count > 0


# ---------------------------------------------------------------------------
# Medical History Management (Per Member)
# ---------------------------------------------------------------------------

async def add_medical_history(
    user_id: str, member_id: str, payload: MedicalHistoryCreate
) -> Optional[FamilyMemberOut]:
    if not ObjectId.is_valid(member_id):
        return None

    item = {
        "id": uuid.uuid4().hex,
        "title": payload.title.strip(),
        "category": payload.category.strip().lower(),
        "diagnosed_date": payload.diagnosed_date,
        "status": payload.status.strip().lower(),
        "doctor_or_hospital": payload.doctor_or_hospital.strip() if payload.doctor_or_hospital else None,
        "notes": payload.notes.strip() if payload.notes else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    res = await family_member_repo.collection.update_one(
        {"_id": ObjectId(member_id), "user_id": user_id},
        {
            "$push": {"medical_history": item},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    if res.matched_count == 0:
        return None
    return await get_member(user_id, member_id)


async def update_medical_history(
    user_id: str, member_id: str, item_id: str, payload: MedicalHistoryUpdate
) -> Optional[FamilyMemberOut]:
    if not ObjectId.is_valid(member_id):
        return None

    update_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if payload.title is not None:
        update_fields["medical_history.$.title"] = payload.title.strip()
    if payload.category is not None:
        update_fields["medical_history.$.category"] = payload.category.strip().lower()
    if payload.diagnosed_date is not None:
        update_fields["medical_history.$.diagnosed_date"] = payload.diagnosed_date
    if payload.status is not None:
        update_fields["medical_history.$.status"] = payload.status.strip().lower()
    if payload.doctor_or_hospital is not None:
        update_fields["medical_history.$.doctor_or_hospital"] = (
            payload.doctor_or_hospital.strip() if payload.doctor_or_hospital else None
        )
    if payload.notes is not None:
        update_fields["medical_history.$.notes"] = (
            payload.notes.strip() if payload.notes else None
        )

    res = await family_member_repo.collection.update_one(
        {"_id": ObjectId(member_id), "user_id": user_id, "medical_history.id": item_id},
        {"$set": update_fields},
    )
    if res.matched_count == 0:
        return None
    return await get_member(user_id, member_id)


async def delete_medical_history(
    user_id: str, member_id: str, item_id: str
) -> Optional[FamilyMemberOut]:
    if not ObjectId.is_valid(member_id):
        return None

    res = await family_member_repo.collection.update_one(
        {"_id": ObjectId(member_id), "user_id": user_id},
        {
            "$pull": {"medical_history": {"id": item_id}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    if res.matched_count == 0:
        return None
    return await get_member(user_id, member_id)


# ---------------------------------------------------------------------------
# Medical Records & Document Upload
# ---------------------------------------------------------------------------

async def create_record(
    user_id: str,
    payload: MedicalRecordCreate,
    file_bytes: Optional[bytes] = None,
    original_filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> MedicalRecordOut:
    # Ensure member belongs to user
    member = await get_member(user_id, payload.member_id)
    if not member:
        raise ValueError("Family member not found or access denied.")

    now = datetime.now(timezone.utc)
    stored_path = None
    stored_filename = None
    file_size = None

    if file_bytes and original_filename:
        if len(file_bytes) > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum allowed limit of 15MB.")

        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file format '{ext}'. Allowed: PDF, JPG, PNG.")

        # Save to user storage
        user_dir = _ensure_storage_dir(user_id)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        target_path = user_dir / unique_name

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        stored_path = f"{user_id}/{unique_name}"
        stored_filename = original_filename
        file_size = len(file_bytes)

    doc = {
        "user_id": user_id,
        "member_id": payload.member_id,
        "member_name": member.name,
        "title": payload.title.strip(),
        "category": payload.category.strip(),
        "record_date": payload.record_date,
        "provider": payload.provider.strip() if payload.provider else None,
        "notes": payload.notes.strip() if payload.notes else None,
        "file_path": stored_path,
        "file_name": stored_filename,
        "file_size": file_size,
        "file_type": content_type,
        "created_at": now,
        "updated_at": now,
    }

    result = await medical_record_repo.collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_record_out(doc)


def _to_record_out(doc: Dict[str, Any]) -> MedicalRecordOut:
    return MedicalRecordOut(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        member_id=doc["member_id"],
        member_name=doc.get("member_name"),
        title=doc["title"],
        category=doc["category"],
        record_date=doc["record_date"],
        provider=doc.get("provider"),
        notes=doc.get("notes"),
        file_name=doc.get("file_name"),
        file_size=doc.get("file_size"),
        file_type=doc.get("file_type"),
        has_document=bool(doc.get("file_path")),
        created_at=doc.get("created_at"),
    )


async def list_records(
    user_id: str,
    member_id: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "newest",
) -> List[MedicalRecordOut]:
    query: Dict[str, Any] = {"user_id": user_id}
    if member_id:
        query["member_id"] = member_id
    if category and category.lower() != "all":
        query["category"] = category
    if start_date or end_date:
        date_query: Dict[str, str] = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        query["record_date"] = date_query
    if search:
        search_rgx = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [
            {"title": search_rgx},
            {"provider": search_rgx},
            {"notes": search_rgx},
            {"file_name": search_rgx},
        ]

    sort_order = -1 if sort_by == "newest" else 1
    cursor = medical_record_repo.collection.find(query).sort("record_date", sort_order)
    docs = await cursor.to_list(length=300)

    # Populate member names if missing
    members_map: Dict[str, str] = {}
    results = []
    for d in docs:
        mid = d.get("member_id")
        if mid and not d.get("member_name"):
            if mid not in members_map:
                m = await get_member(user_id, mid)
                members_map[mid] = m.name if m else "Unknown"
            d["member_name"] = members_map[mid]
        results.append(_to_record_out(d))
    return results


async def get_record(user_id: str, record_id: str) -> Optional[MedicalRecordOut]:
    if not ObjectId.is_valid(record_id):
        return None
    doc = await medical_record_repo.collection.find_one(
        {"_id": ObjectId(record_id), "user_id": user_id}
    )
    if not doc:
        return None
    if not doc.get("member_name"):
        m = await get_member(user_id, doc["member_id"])
        doc["member_name"] = m.name if m else "Unknown"
    return _to_record_out(doc)


async def get_document_file(
    user_id: str, record_id: str
) -> Optional[Tuple[Path, str, str]]:
    """Returns (file_path, file_name, content_type) for authorized download/preview."""
    if not ObjectId.is_valid(record_id):
        return None
    doc = await medical_record_repo.collection.find_one(
        {"_id": ObjectId(record_id), "user_id": user_id}
    )
    if not doc or not doc.get("file_path"):
        return None

    physical_path = STORAGE_DIR / doc["file_path"]
    if not physical_path.exists():
        return None

    file_name = doc.get("file_name", physical_path.name)
    content_type = doc.get("file_type", "application/octet-stream")
    return physical_path, file_name, content_type


async def update_record(
    user_id: str, record_id: str, payload: MedicalRecordUpdate
) -> Optional[MedicalRecordOut]:
    if not ObjectId.is_valid(record_id):
        return None

    fields: Dict[str, Any] = {}
    if payload.title is not None:
        fields["title"] = payload.title.strip()
    if payload.category is not None:
        fields["category"] = payload.category.strip()
    if payload.record_date is not None:
        fields["record_date"] = payload.record_date
    if payload.provider is not None:
        fields["provider"] = payload.provider.strip() if payload.provider else None
    if payload.notes is not None:
        fields["notes"] = payload.notes.strip() if payload.notes else None

    if not fields:
        return await get_record(user_id, record_id)

    fields["updated_at"] = datetime.now(timezone.utc)
    res = await medical_record_repo.collection.update_one(
        {"_id": ObjectId(record_id), "user_id": user_id},
        {"$set": fields},
    )
    if res.matched_count == 0:
        return None
    return await get_record(user_id, record_id)


async def delete_record(user_id: str, record_id: str) -> bool:
    if not ObjectId.is_valid(record_id):
        return False
    doc = await medical_record_repo.collection.find_one(
        {"_id": ObjectId(record_id), "user_id": user_id}
    )
    if not doc:
        return False

    # Delete physical file if attached
    if doc.get("file_path"):
        fp = STORAGE_DIR / doc["file_path"]
        if fp.exists():
            try:
                fp.unlink()
            except OSError:
                pass

    res = await medical_record_repo.collection.delete_one(
        {"_id": ObjectId(record_id), "user_id": user_id}
    )
    return res.deleted_count > 0


# ---------------------------------------------------------------------------
# Prescriptions & Medications Management
# ---------------------------------------------------------------------------

async def create_medication(user_id: str, payload: MedicationCreate) -> MedicationOut:
    member = await get_member(user_id, payload.member_id)
    if not member:
        raise ValueError("Family member not found or access denied.")

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "member_id": payload.member_id,
        "member_name": member.name,
        "name": payload.name.strip(),
        "dosage": payload.dosage.strip(),
        "frequency": payload.frequency.strip(),
        "instructions": payload.instructions.strip() if payload.instructions else None,
        "prescribing_doctor": payload.prescribing_doctor.strip() if payload.prescribing_doctor else None,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "status": payload.status.strip().lower(),
        "notes": payload.notes.strip() if payload.notes else None,
        "linked_record_id": payload.linked_record_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await medication_repo.collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_medication_out(doc)


def _to_medication_out(doc: Dict[str, Any]) -> MedicationOut:
    return MedicationOut(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        member_id=doc["member_id"],
        member_name=doc.get("member_name"),
        name=doc["name"],
        dosage=doc["dosage"],
        frequency=doc["frequency"],
        instructions=doc.get("instructions"),
        prescribing_doctor=doc.get("prescribing_doctor"),
        start_date=doc.get("start_date"),
        end_date=doc.get("end_date"),
        status=doc.get("status", "active"),
        notes=doc.get("notes"),
        linked_record_id=doc.get("linked_record_id"),
        created_at=doc.get("created_at"),
    )


async def list_medications(
    user_id: str, member_id: Optional[str] = None, status: Optional[str] = None
) -> List[MedicationOut]:
    query: Dict[str, Any] = {"user_id": user_id}
    if member_id:
        query["member_id"] = member_id
    if status and status.lower() != "all":
        query["status"] = status.lower()

    cursor = medication_repo.collection.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=200)

    members_map: Dict[str, str] = {}
    results = []
    for d in docs:
        mid = d.get("member_id")
        if mid and not d.get("member_name"):
            if mid not in members_map:
                m = await get_member(user_id, mid)
                members_map[mid] = m.name if m else "Unknown"
            d["member_name"] = members_map[mid]
        results.append(_to_medication_out(d))
    return results


async def update_medication(
    user_id: str, medication_id: str, payload: MedicationUpdate
) -> Optional[MedicationOut]:
    if not ObjectId.is_valid(medication_id):
        return None

    fields: Dict[str, Any] = {}
    if payload.name is not None:
        fields["name"] = payload.name.strip()
    if payload.dosage is not None:
        fields["dosage"] = payload.dosage.strip()
    if payload.frequency is not None:
        fields["frequency"] = payload.frequency.strip()
    if payload.instructions is not None:
        fields["instructions"] = payload.instructions.strip() if payload.instructions else None
    if payload.prescribing_doctor is not None:
        fields["prescribing_doctor"] = payload.prescribing_doctor.strip() if payload.prescribing_doctor else None
    if payload.start_date is not None:
        fields["start_date"] = payload.start_date
    if payload.end_date is not None:
        fields["end_date"] = payload.end_date
    if payload.status is not None:
        fields["status"] = payload.status.strip().lower()
    if payload.notes is not None:
        fields["notes"] = payload.notes.strip() if payload.notes else None
    if payload.linked_record_id is not None:
        fields["linked_record_id"] = payload.linked_record_id

    if not fields:
        doc = await medication_repo.collection.find_one(
            {"_id": ObjectId(medication_id), "user_id": user_id}
        )
        return _to_medication_out(doc) if doc else None

    fields["updated_at"] = datetime.now(timezone.utc)
    res = await medication_repo.collection.update_one(
        {"_id": ObjectId(medication_id), "user_id": user_id},
        {"$set": fields},
    )
    if res.matched_count == 0:
        return None

    doc = await medication_repo.collection.find_one(
        {"_id": ObjectId(medication_id), "user_id": user_id}
    )
    return _to_medication_out(doc) if doc else None


async def delete_medication(user_id: str, medication_id: str) -> bool:
    if not ObjectId.is_valid(medication_id):
        return False
    res = await medication_repo.collection.delete_one(
        {"_id": ObjectId(medication_id), "user_id": user_id}
    )
    return res.deleted_count > 0


# ---------------------------------------------------------------------------
# Health Progress Tracking (Measurements / Lab Trends)
# ---------------------------------------------------------------------------

async def create_measurement(
    user_id: str, payload: HealthMeasurementCreate
) -> HealthMeasurementOut:
    member = await get_member(user_id, payload.member_id)
    if not member:
        raise ValueError("Family member not found or access denied.")

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "member_id": payload.member_id,
        "member_name": member.name,
        "metric_type": payload.metric_type.strip().lower(),
        "metric_name": payload.metric_name.strip(),
        "value": float(payload.value),
        "value_secondary": float(payload.value_secondary) if payload.value_secondary is not None else None,
        "unit": payload.unit.strip(),
        "recorded_date": payload.recorded_date,
        "notes": payload.notes.strip() if payload.notes else None,
        "created_at": now,
    }
    result = await health_metric_repo.collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_measurement_out(doc)


def _to_measurement_out(doc: Dict[str, Any]) -> HealthMeasurementOut:
    return HealthMeasurementOut(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        member_id=doc["member_id"],
        member_name=doc.get("member_name"),
        metric_type=doc["metric_type"],
        metric_name=doc["metric_name"],
        value=doc["value"],
        value_secondary=doc.get("value_secondary"),
        unit=doc["unit"],
        recorded_date=doc["recorded_date"],
        notes=doc.get("notes"),
        created_at=doc.get("created_at"),
    )


async def list_measurements(
    user_id: str, member_id: Optional[str] = None, metric_type: Optional[str] = None
) -> List[HealthMeasurementOut]:
    query: Dict[str, Any] = {"user_id": user_id}
    if member_id:
        query["member_id"] = member_id
    if metric_type and metric_type.lower() != "all":
        query["metric_type"] = metric_type.lower()

    cursor = health_metric_repo.collection.find(query).sort("recorded_date", 1)  # chronological order for charting
    docs = await cursor.to_list(length=300)

    members_map: Dict[str, str] = {}
    results = []
    for d in docs:
        mid = d.get("member_id")
        if mid and not d.get("member_name"):
            if mid not in members_map:
                m = await get_member(user_id, mid)
                members_map[mid] = m.name if m else "Unknown"
            d["member_name"] = members_map[mid]
        results.append(_to_measurement_out(d))
    return results


async def delete_measurement(user_id: str, measurement_id: str) -> bool:
    if not ObjectId.is_valid(measurement_id):
        return False
    res = await health_metric_repo.collection.delete_one(
        {"_id": ObjectId(measurement_id), "user_id": user_id}
    )
    return res.deleted_count > 0


# ---------------------------------------------------------------------------
# Health Timeline Aggregation
# ---------------------------------------------------------------------------

async def get_member_timeline(
    user_id: str, member_id: Optional[str] = None
) -> List[TimelineEventOut]:
    member = None
    if member_id:
        member = await get_member(user_id, member_id)
        if not member:
            return []

    events: List[TimelineEventOut] = []

    # 1. Documents & Reports
    records = await list_records(user_id, member_id=member_id)
    for r in records:
        events.append(
            TimelineEventOut(
                id=f"rec-{r.id}",
                event_type="document",
                title=f"{r.category}: {r.title}",
                date=r.record_date,
                description=f"Recorded at {r.provider or 'Clinic/Hospital'}" + (f" ({r.file_name})" if r.file_name else ""),
                member_id=r.member_id,
                member_name=r.member_name or (member.name if member else "Member"),
                badge_color="var(--info)",
                icon="fas fa-file-medical",
                link_id=r.id,
            )
        )

    # 2. Medical History
    if member:
        members_list = [member]
    else:
        members_list = await list_members(user_id)

    for m in members_list:
        for h in m.medical_history:
            d = h.diagnosed_date or (h.created_at[:10] if h.created_at else "Earlier")
            events.append(
                TimelineEventOut(
                    id=f"hist-{h.id}",
                    event_type="history",
                    title=f"{h.category.capitalize()}: {h.title}",
                    date=d,
                    description=f"Status: {h.status.capitalize()}" + (f" • {h.doctor_or_hospital}" if h.doctor_or_hospital else ""),
                    member_id=m.id,
                    member_name=m.name,
                    badge_color="var(--warning)",
                    icon="fas fa-notes-medical",
                    link_id=h.id,
                )
            )

    # 3. Medications
    meds = await list_medications(user_id, member_id=member_id)
    for med in meds:
        d = med.start_date or (med.created_at.strftime("%Y-%m-%d") if med.created_at else "Current")
        events.append(
            TimelineEventOut(
                id=f"med-{med.id}",
                event_type="medication",
                title=f"Medication Prescribed: {med.name}",
                date=d,
                description=f"{med.dosage} • {med.frequency} (Status: {med.status})",
                member_id=med.member_id,
                member_name=med.member_name or (member.name if member else "Member"),
                badge_color="var(--primary)",
                icon="fas fa-pills",
                link_id=med.id,
            )
        )

    # 4. Health Vitals / Measurements
    vitals = await list_measurements(user_id, member_id=member_id)
    for v in vitals:
        val_str = f"{v.value}"
        if v.value_secondary is not None:
            val_str = f"{int(v.value)}/{int(v.value_secondary)}"
        events.append(
            TimelineEventOut(
                id=f"vit-{v.id}",
                event_type="measurement",
                title=f"Logged: {v.metric_name}",
                date=v.recorded_date,
                description=f"{val_str} {v.unit}" + (f" • {v.notes}" if v.notes else ""),
                member_id=v.member_id,
                member_name=v.member_name or (member.name if member else "Member"),
                badge_color="var(--success)",
                icon="fas fa-heartbeat",
                link_id=v.id,
            )
        )

    # Sort descending by date
    events.sort(key=lambda x: x.date, reverse=True)
    return events


# ---------------------------------------------------------------------------
# Family Overview Aggregator
# ---------------------------------------------------------------------------

async def get_family_overview(user_id: str) -> FamilyOverviewOut:
    members = await list_members(user_id)
    total_members = len(members)

    # Distinct members with records
    distinct_members_with_records = await medical_record_repo.collection.distinct(
        "member_id", {"user_id": user_id}
    )
    members_with_records = len(distinct_members_with_records)

    total_records = await medical_record_repo.collection.count_documents({"user_id": user_id})
    total_medications = await medication_repo.collection.count_documents(
        {"user_id": user_id, "status": "active"}
    )

    recent_records = await list_records(user_id, sort_by="newest")
    active_meds = await list_medications(user_id, status="active")

    return FamilyOverviewOut(
        total_members=total_members,
        members_with_records=members_with_records,
        total_records=total_records,
        total_medications=total_medications,
        recent_records=recent_records[:6],
        active_medications=active_meds[:6],
    )
