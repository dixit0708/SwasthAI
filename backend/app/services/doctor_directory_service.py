"""Doctor directory backed by the `doctors` collection.

Two sources populate it (see backend/scripts/):
  - "osm": hospitals/clinics imported from OpenStreetMap (ODbL). Real names,
    addresses and coordinates, but no phone numbers or specialty tags, so
    specialties are inferred from the listing name and labelled as such.
  - "consented": doctors who personally agreed to be listed, with phone
    numbers they supplied. Shown first.

Nothing here is invented: every listing comes from one of those sources.
"""
import math
import re
from urllib.parse import quote, urlencode

from bson import ObjectId

from app.db.collections import doctor_repo
from app.models.doctor import Doctor, DoctorSearchResponse, Specialty

SOURCE_OSM = "osm"
SOURCE_CONSENTED = "consented"

OSM_ATTRIBUTION = "Listing data © OpenStreetMap contributors (ODbL)."
CONSENTED_ATTRIBUTION = "Details provided by the doctor, who agreed to be listed on SwasthAI."

# key -> (label, word-start regex for inferring from a listing name, related assessments)
# Patterns are anchored at word starts so e.g. "ent" never matches "centre"
# and "ortho" (bones) never matches "orthodontic" (teeth).
SPECIALTIES: dict[str, tuple[str, str, list[str]]] = {
    "general": ("General Physician", r"\b(?:general physician|family (?:doctor|physician))", []),
    "cardiology": ("Cardiologist (Heart)", r"\b(?:heart|cardi)", ["heart"]),
    "endocrinology": ("Diabetologist / Endocrinologist", r"\b(?:diabet|endocrin|thyroid)", ["diabetes"]),
    "gastroenterology": ("Gastroenterologist (Liver & Digestive)", r"\b(?:gastro|liver|hepat|digestive)", ["liver"]),
    "dermatology": ("Dermatologist (Skin)", r"\b(?:skin|derma)", ["skin"]),
    "pulmonology": ("Pulmonologist (Chest & Lungs)", r"\b(?:chest|lung|pulmo|respirat|asthma)", ["pneumonia"]),
    "pediatrics": ("Pediatrician (Children)", r"\b(?:child|p(?:a)?ediatric|kids|shishu)", []),
    "gynecology": ("Gynecologist & Maternity", r"\b(?:maternity|gyn|women|ivf|fertility|prasuti)", []),
    "orthopedics": ("Orthopedic (Bones & Joints)", r"\b(?:ortho(?!dont)|bone|joint|fracture|spine)", []),
    "ophthalmology": ("Eye Specialist", r"\b(?:eye|netra|ophthal|vision|lasik)", []),
    "ent": ("ENT (Ear, Nose & Throat)", r"\b(?:ent|e\.n\.t\.?)\b", []),
    "dental": ("Dentist", r"\b(?:dent|teeth|tooth|orthodont|smile)", []),
    "neurology": ("Neurologist", r"\b(?:neuro|brain)", []),
    "urology": ("Urologist / Kidney Specialist", r"\b(?:kidney|stone|uro|nephro)", []),
    "psychiatry": ("Psychiatrist (Mental Health)", r"\b(?:psych|mental|de-?addiction|nasha)", []),
}

_SPECIALTY_PATTERNS = {key: re.compile(pattern, re.IGNORECASE) for key, (_, pattern, _) in SPECIALTIES.items()}

MAX_PAGE_SIZE = 50
SCAN_LIMIT = 2000
EARTH_RADIUS_KM = 6371.0

# Listings with no specialty of their own that still provide broad care, so
# they are offered (labelled) alongside specialty matches.
GENERAL_CARE_KINDS = {"hospital", "centre"}


class InvalidSearch(Exception):
    pass


class DoctorNotFound(Exception):
    pass


def list_specialties() -> list[Specialty]:
    return [
        Specialty(key=key, label=label, related_assessments=related)
        for key, (label, _pattern, related) in SPECIALTIES.items()
    ]


def infer_specialties(name: str) -> list[str]:
    return [key for key, pattern in _SPECIALTY_PATTERNS.items() if pattern.search(name)]


def _place_text(name: str, city: str | None) -> str:
    # Most OSM addresses omit the city, and a bare "City Hospital, Station
    # Road" matches same-named places in other cities.
    return f"{name}, {city}" if city and city.lower() not in name.lower() else name


def _fallback_text(name: str, address: str | None, city: str | None) -> str:
    return ", ".join(part for part in (name, address, city) if part)


# With coordinates, both links open Google's own place for this listing: the
# name is searched inside a viewport centred on the listing, so Google picks
# the matching place there. Bare coordinates would route to an unnamed pin.

def google_maps_search_url(
    name: str, address: str | None, city: str | None, latitude: float | None, longitude: float | None
) -> str:
    if latitude is not None and longitude is not None:
        return f"https://www.google.com/maps/search/{quote(_place_text(name, city), safe='')}/@{latitude},{longitude},17z"
    return "https://www.google.com/maps/search/?" + urlencode({"api": "1", "query": _fallback_text(name, address, city)})


def directions_url(
    name: str, address: str | None, city: str | None, latitude: float | None, longitude: float | None
) -> str:
    if latitude is not None and longitude is not None:
        return f"https://www.google.com/maps/dir//{quote(_place_text(name, city), safe='')}/@{latitude},{longitude},17z"
    return "https://www.google.com/maps/dir/?" + urlencode({"api": "1", "destination": _fallback_text(name, address, city)})


def _to_doctor(doc: dict, relevance: str | None = None, distance: float | None = None) -> Doctor:
    consented = doc.get("source") == SOURCE_CONSENTED
    name, address, city = doc["name"], doc.get("address"), doc.get("city")
    place_name = doc.get("clinic_name") or name
    lat, lng = doc.get("latitude"), doc.get("longitude")
    return Doctor(
        id=str(doc["_id"]),
        name=name,
        kind=doc.get("kind"),
        specialties=[
            Specialty(key=key, label=SPECIALTIES[key][0], related_assessments=SPECIALTIES[key][2])
            for key in doc.get("specialties", [])
            if key in SPECIALTIES
        ],
        specialty_source=doc.get("specialty_source"),
        qualification=doc.get("qualification"),
        clinic_name=doc.get("clinic_name"),
        address=address,
        city=doc.get("city"),
        latitude=lat,
        longitude=lng,
        phone=doc.get("phone") if consented else None,
        phone_dial=doc.get("phone_dial") if consented else None,
        timings=doc.get("timings"),
        listed_with_consent=consented,
        google_maps_url=google_maps_search_url(place_name, address, city, lat, lng),
        directions_url=directions_url(place_name, address, city, lat, lng),
        attribution=CONSENTED_ATTRIBUTION if consented else OSM_ATTRIBUTION,
        relevance=relevance,
        distance_km=round(distance, 1) if distance is not None else None,
    )


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle (haversine) distance."""
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _ranked(docs: list[dict], origin: tuple[float, float] | None) -> list[tuple[dict, float | None]]:
    """Nearest first when an origin is given (listings without coordinates
    last); otherwise consented first, then by name."""
    ranked = []
    for doc in docs:
        dist = None
        if origin and doc.get("latitude") is not None and doc.get("longitude") is not None:
            dist = distance_km(origin[0], origin[1], doc["latitude"], doc["longitude"])
        ranked.append((doc, dist))
    if origin:
        ranked.sort(key=lambda item: (item[1] is None, item[1] or 0, item[0]["name"].lower()))
    else:
        ranked.sort(key=lambda item: (item[0].get("listing_priority", 1), item[0]["name"].lower()))
    return ranked


async def search_doctors(
    specialty: str | None,
    query: str | None,
    city: str | None,
    page: int,
    page_size: int,
    consented_only: bool = False,
    latitude: float | None = None,
    longitude: float | None = None,
) -> DoctorSearchResponse:
    """Paginated search, nearest first when a location is given.

    With a specialty, results come in two groups: listings matching that
    specialty, then hospitals/health centres with no specialty of their own
    (multi-specialty or general), which may also offer the care. Each item's
    `relevance` says which group it is in, so the UI can label it honestly.

    Matching listings are ranked in Python rather than with a $geoNear
    index: a city/district directory holds a few hundred listings, and this
    keeps listings without coordinates (e.g. some consented doctors) in the
    results instead of silently dropping them. Past SCAN_LIMIT this should
    move to a 2dsphere index.
    """
    if specialty and specialty not in SPECIALTIES:
        raise InvalidSearch("Unknown specialty.")
    if (latitude is None) != (longitude is None):
        raise InvalidSearch("Both latitude and longitude are required to sort by distance.")
    origin = (latitude, longitude) if latitude is not None else None

    base: dict = {"is_active": True}
    if consented_only:
        base["source"] = SOURCE_CONSENTED
    if city:
        base["city"] = {"$regex": f"^{re.escape(city)}$", "$options": "i"}
    if query:
        escaped = re.escape(query)
        base["$or"] = [
            {"name": {"$regex": escaped, "$options": "i"}},
            {"clinic_name": {"$regex": escaped, "$options": "i"}},
            {"address": {"$regex": escaped, "$options": "i"}},
        ]

    groups: list[tuple[str | None, dict]] = [(None, base)]
    if specialty:
        groups = [("specialty_match", {**base, "specialties": specialty})]
        if not consented_only:
            groups.append(("general_care", {
                **base, "specialties": {"$size": 0}, "kind": {"$in": list(GENERAL_CARE_KINDS)},
            }))

    results: list[tuple[dict, float | None, str | None]] = []
    group_sizes = []
    for relevance, filters in groups:
        docs = await doctor_repo.collection.find(filters).to_list(length=SCAN_LIMIT)
        group_sizes.append(len(docs))
        results += [(doc, dist, relevance) for doc, dist in _ranked(docs, origin)]

    page_size = min(page_size, MAX_PAGE_SIZE)
    window = results[(page - 1) * page_size: page * page_size]
    return DoctorSearchResponse(
        items=[_to_doctor(doc, relevance, dist) for doc, dist, relevance in window],
        total=len(results),
        specialty_matches=group_sizes[0] if specialty else None,
        page=page,
        page_size=page_size,
    )


async def get_doctor(doctor_id: str) -> Doctor:
    if not ObjectId.is_valid(doctor_id):
        raise DoctorNotFound("Doctor not found.")
    doc = await doctor_repo.collection.find_one({"_id": ObjectId(doctor_id), "is_active": True})
    if not doc:
        raise DoctorNotFound("Doctor not found.")
    return _to_doctor(doc)
