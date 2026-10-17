"""Builds `doctors` documents from the two allowed sources and syncs them.

Used by backend/scripts/import_osm_doctors.py and
backend/scripts/import_consented_doctors.py. Each import fully replaces its
own scope: a listing missing from the new data is deleted. For consented
doctors that is how a withdrawn consent is honoured, since their details
are personal data and must not linger (AGENTS.md Section 46).
"""
import hashlib
import re
from datetime import date, datetime, timezone

from app.db.collections import doctor_repo
from app.services.doctor_directory_service import (
    SOURCE_CONSENTED,
    SOURCE_OSM,
    SPECIALTIES,
    infer_specialties,
)

# "centre" = healthcare=centre, e.g. government primary/community health centres.
OSM_KINDS = {"hospital", "clinic", "doctors", "doctor", "dentist", "centre"}
YES_VALUES = {"yes", "y", "true", "1"}


def _osm_address(tags: dict) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"].strip()
    parts = [
        tags.get(key, "").strip()
        for key in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city", "addr:postcode")
    ]
    address = ", ".join(part for part in parts if part)
    return address or None


def osm_element_to_listing(element: dict, city: str) -> dict | None:
    tags = element.get("tags") or {}
    name = (tags.get("name:en") or tags.get("name") or "").strip()
    kind = tags.get("amenity") or tags.get("healthcare")
    if not name or kind not in OSM_KINDS:
        return None

    lat = element.get("lat", (element.get("center") or {}).get("lat"))
    lng = element.get("lon", (element.get("center") or {}).get("lon"))
    specialties = infer_specialties(name)
    if kind == "dentist" and "dental" not in specialties:
        specialties.append("dental")

    return {
        "source": SOURCE_OSM,
        "source_id": f"osm:{element['type']}/{element['id']}",
        "listing_priority": 1,
        "name": name,
        "kind": "doctor" if kind == "doctors" else kind,
        "specialties": specialties,
        "specialty_source": "name_match" if specialties else None,
        "address": _osm_address(tags),
        "city": city,
        "latitude": lat,
        "longitude": lng,
        "is_active": True,
    }


def _dial_string(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        # Landline with STD code, e.g. 0591 2412345.
        return f"+91{digits[1:]}"
    raise ValueError(f"phone '{phone}' is not a valid Indian number")


def consented_row_to_listing(row: dict) -> dict:
    """Validate one CSV row; raises ValueError naming the problem."""
    get = lambda key: (row.get(key) or "").strip()  # noqa: E731

    name, phone, specialty = get("doctor_name"), get("phone"), get("specialty").lower()
    if not name:
        raise ValueError("doctor_name is required")
    if get("consent_given").lower() not in YES_VALUES:
        raise ValueError(f"{name}: consent_given must be 'yes' (no consent, no listing)")
    try:
        consent_date = date.fromisoformat(get("consent_date"))
    except ValueError:
        raise ValueError(f"{name}: consent_date must be YYYY-MM-DD")
    if specialty not in SPECIALTIES:
        raise ValueError(f"{name}: specialty '{specialty}' must be one of {', '.join(SPECIALTIES)}")
    if not get("address") or not get("city"):
        raise ValueError(f"{name}: address and city are required")

    phone_dial = _dial_string(phone)
    lat, lng = get("latitude"), get("longitude")
    identity = hashlib.sha256(f"{name.lower()}|{phone_dial}".encode()).hexdigest()[:16]

    return {
        "source": SOURCE_CONSENTED,
        "source_id": f"consented:{identity}",
        "listing_priority": 0,
        "name": name,
        "kind": "doctor",
        "specialties": [specialty],
        "specialty_source": "provided",
        "qualification": get("qualification") or None,
        "clinic_name": get("clinic_name") or None,
        "address": get("address"),
        "city": get("city"),
        "latitude": float(lat) if lat else None,
        "longitude": float(lng) if lng else None,
        "phone": phone,
        "phone_dial": phone_dial,
        "timings": get("timings") or None,
        "consent_obtained_on": consent_date.isoformat(),
        "is_active": True,
    }


async def replace_listings(listings: list[dict], scope: dict) -> tuple[int, int]:
    """Upsert `listings` and delete anything else matching `scope`.

    Returns (upserted_count, removed_count).
    """
    collection = doctor_repo.collection
    now = datetime.now(timezone.utc)
    for listing in listings:
        await collection.update_one(
            {"source_id": listing["source_id"]},
            {"$set": {**listing, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    seen = [listing["source_id"] for listing in listings]
    removed = await collection.delete_many({**scope, "source_id": {"$nin": seen}})
    return len(listings), removed.deleted_count
