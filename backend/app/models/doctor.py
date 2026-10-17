from typing import List, Literal, Optional

from pydantic import BaseModel


class Specialty(BaseModel):
    key: str
    label: str
    # Risk assessments (e.g. "heart") whose results link to this specialty.
    related_assessments: List[str] = []


class Doctor(BaseModel):
    id: str
    name: str
    kind: Optional[str] = None
    specialties: List[Specialty] = []
    # "provided" = stated by a consented doctor; "name_match" = inferred
    # from an OpenStreetMap listing's name, so the UI can label it honestly.
    specialty_source: Optional[Literal["provided", "name_match"]] = None
    qualification: Optional[str] = None
    clinic_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Only ever set for consented listings.
    phone: Optional[str] = None
    # Digits and a leading "+" only, safe to place in a tel: link.
    phone_dial: Optional[str] = None
    timings: Optional[str] = None
    listed_with_consent: bool = False
    google_maps_url: str
    directions_url: str
    attribution: str
    # Set only in specialty searches: "specialty_match", or "general_care"
    # for a general/multi-specialty hospital that may also offer the care.
    relevance: Optional[Literal["specialty_match", "general_care"]] = None
    # Set only when the search included a location.
    distance_km: Optional[float] = None


class DoctorSearchResponse(BaseModel):
    items: List[Doctor]
    total: int
    # Set only in specialty searches: how many of `total` match the specialty.
    specialty_matches: Optional[int] = None
    page: int
    page_size: int
