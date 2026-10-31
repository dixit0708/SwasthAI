"""Doctor directory tests: specialty inference, import validation, sync, API.

Every inserted document uses a unique per-test city and a "test:" source_id
prefix, so tests never collide with each other or with imported data.
"""
import uuid

import pytest
from bson import ObjectId

from app.db.mongodb import db_manager
from app.services.doctor_directory_service import directions_url, google_maps_search_url, infer_specialties
from app.services.doctor_import import (
    consented_row_to_listing,
    osm_element_to_listing,
    replace_listings,
)
from conftest import unique_email

VALID_PASSWORD = "Correct-Horse9-Battery"


async def _auth(client) -> dict:
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": unique_email(), "password": VALID_PASSWORD},
    )
    assert res.status_code == 201
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
async def seeded(client):
    """Insert a small directory into a unique city; yields (city, ids)."""
    city = f"TestCity{uuid.uuid4().hex[:8]}"
    base = {"city": city, "is_active": True, "kind": "hospital", "latitude": 28.8, "longitude": 78.7}
    docs = {
        "heart": {**base, "source": "osm", "listing_priority": 1, "name": "Apex Heart Hospital",
                  "specialties": ["cardiology"], "specialty_source": "name_match",
                  "address": "Civil Lines", "phone": "should-never-be-shown"},
        "general": {**base, "source": "osm", "listing_priority": 1, "name": "City Hospital",
                    "specialties": [], "address": "Station Road (Near Bus Stand)"},
        "consented": {**base, "source": "consented", "listing_priority": 0, "name": "Dr. Test Sharma",
                      "kind": "doctor", "specialties": ["cardiology"], "specialty_source": "provided",
                      "address": "Gandhi Nagar", "phone": "98765 43210", "phone_dial": "+919876543210"},
        "closed": {**base, "source": "osm", "listing_priority": 1, "name": "Closed Heart Clinic",
                   "specialties": ["cardiology"], "is_active": False},
    }
    ids = {}
    for key, doc in docs.items():
        result = await db_manager.db["doctors"].insert_one({**doc, "source_id": f"test:{uuid.uuid4().hex}"})
        ids[key] = str(result.inserted_id)
    yield city, ids
    await db_manager.db["doctors"].delete_many({"city": city})


# ---------------------------------------------------------------------------
# Specialty inference from listing names
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("Varshney Eye and Ortho Care Center", {"ophthalmology", "orthopedics"}),
    ("Smile Orthodontic Clinic", {"dental"}),  # teeth, not bones
    ("Sai Dental Care", {"dental"}),
    ("Apex Heart Hospital", {"cardiology"}),
    ("Madan Maternity and Laproscopic Surgery Centre", {"gynecology"}),
    ("Shekhar Hospital Kidney and Stone Clinic", {"urology"}),
    ("City Centre Hospital", set()),  # "ent" must not match inside "Centre"
    ("Dr. Gupta ENT Clinic", {"ent"}),
])
def test_infer_specialties_from_name(name, expected):
    assert set(infer_specialties(name)) == expected


# ---------------------------------------------------------------------------
# Google Maps links
# ---------------------------------------------------------------------------

def test_links_open_the_named_place_at_its_position():
    url = google_maps_search_url("M M Hospitals", "Gulzarimal Dharamshala Road", "Moradabad", 28.83, 78.76)
    assert url == "https://www.google.com/maps/search/M%20M%20Hospitals%2C%20Moradabad/@28.83,78.76,17z"
    url = directions_url("M M Hospitals", None, "Moradabad", 28.83, 78.76)
    assert url == "https://www.google.com/maps/dir//M%20M%20Hospitals%2C%20Moradabad/@28.83,78.76,17z"


def test_links_encode_slashes_and_skip_duplicate_city():
    url = google_maps_search_url("Modern Nursing Home - Moradabad A/6", None, "Moradabad", 28.8, 78.7)
    assert "A%2F6/@" in url  # a "/" in the name must not split the URL path
    assert url.count("Moradabad") == 1


def test_links_without_coordinates_fall_back_to_text_with_city():
    url = directions_url("City Hospital", "Station Road", "Moradabad", None, None)
    assert url == "https://www.google.com/maps/dir/?api=1&destination=City+Hospital%2C+Station+Road%2C+Moradabad"


# ---------------------------------------------------------------------------
# OpenStreetMap element mapping
# ---------------------------------------------------------------------------

def test_osm_way_maps_to_listing():
    listing = osm_element_to_listing({
        "type": "way", "id": 42, "center": {"lat": 28.83, "lon": 78.77},
        "tags": {"amenity": "hospital", "name": "Apex Heart Hospital",
                 "addr:street": "Civil Lines", "addr:city": "Moradabad", "addr:postcode": "244001"},
    }, "Moradabad")
    assert listing["source_id"] == "osm:way/42"
    assert (listing["latitude"], listing["longitude"]) == (28.83, 78.77)
    assert listing["address"] == "Civil Lines, Moradabad, 244001"
    assert listing["specialties"] == ["cardiology"]
    assert listing["specialty_source"] == "name_match"
    assert "phone" not in listing


@pytest.mark.parametrize("tags", [
    {"amenity": "hospital"},  # unnamed
    {"amenity": "pharmacy", "name": "Wellness Chemist"},  # not a doctor listing
])
def test_osm_skips_unusable_elements(tags):
    assert osm_element_to_listing({"type": "node", "id": 1, "lat": 0, "lon": 0, "tags": tags}, "X") is None


def test_osm_dentist_gets_dental_and_doctors_kind_normalised():
    dentist = osm_element_to_listing({"type": "node", "id": 2, "lat": 1, "lon": 2,
                                      "tags": {"amenity": "dentist", "name": "Bright Care"}}, "X")
    assert dentist["specialties"] == ["dental"]
    doctor = osm_element_to_listing({"type": "node", "id": 3, "lat": 1, "lon": 2,
                                     "tags": {"amenity": "doctors", "name": "Gupta Clinic"}}, "X")
    assert doctor["kind"] == "doctor"
    centre = osm_element_to_listing({"type": "node", "id": 4, "lat": 1, "lon": 2,
                                     "tags": {"healthcare": "centre", "name": "PHC Bilari"}}, "X")
    assert centre["kind"] == "centre"


# ---------------------------------------------------------------------------
# Consented CSV row validation
# ---------------------------------------------------------------------------

VALID_ROW = {
    "doctor_name": "Dr. A. Sharma", "qualification": "MBBS, MD", "specialty": "Cardiology",
    "clinic_name": "Sharma Heart Clinic", "address": "Civil Lines", "city": "Moradabad",
    "phone": "98765 43210", "timings": "Mon-Sat 10am-2pm",
    "consent_given": "Yes", "consent_date": "2026-10-10", "latitude": "", "longitude": "",
}


def test_consented_row_maps_to_listing():
    listing = consented_row_to_listing(VALID_ROW)
    assert listing["phone_dial"] == "+919876543210"
    assert listing["specialties"] == ["cardiology"]
    assert listing["listing_priority"] == 0
    assert listing["consent_obtained_on"] == "2026-10-10"
    assert listing["latitude"] is None
    # Same doctor + phone always maps to the same record (idempotent re-import).
    assert consented_row_to_listing(VALID_ROW)["source_id"] == listing["source_id"]


def test_consented_landline_with_std_code():
    assert consented_row_to_listing({**VALID_ROW, "phone": "0591-2412345"})["phone_dial"] == "+915912412345"


@pytest.mark.parametrize("override, message", [
    ({"consent_given": "no"}, "consent_given"),
    ({"consent_given": ""}, "consent_given"),
    ({"consent_date": "10/10/2026"}, "consent_date"),
    ({"specialty": "astrology"}, "specialty"),
    ({"phone": "12345"}, "phone"),
    ({"address": ""}, "address"),
    ({"doctor_name": ""}, "doctor_name"),
])
def test_consented_row_rejects_invalid(override, message):
    with pytest.raises(ValueError, match=message):
        consented_row_to_listing({**VALID_ROW, **override})


# ---------------------------------------------------------------------------
# Sync (replace_listings)
# ---------------------------------------------------------------------------

async def test_replace_listings_is_idempotent_and_scoped(client):
    city, other_city = f"TestCity{uuid.uuid4().hex[:8]}", f"TestCity{uuid.uuid4().hex[:8]}"
    collection = db_manager.db["doctors"]

    def listing(source_id, target_city):
        return {"source": "osm", "source_id": source_id, "listing_priority": 1, "name": source_id,
                "city": target_city, "specialties": [], "is_active": True}

    try:
        await replace_listings([listing("test:keep", other_city)], {"source": "osm", "city": other_city})
        await replace_listings([listing("test:a", city), listing("test:b", city)], {"source": "osm", "city": city})
        upserted, removed = await replace_listings([listing("test:a", city)], {"source": "osm", "city": city})

        assert (upserted, removed) == (1, 1)
        assert await collection.count_documents({"city": city}) == 1
        assert await collection.count_documents({"source_id": "test:keep"}) == 1  # other city untouched
    finally:
        await collection.delete_many({"city": {"$in": [city, other_city]}})


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

async def test_specialties_public_and_cover_every_assessment(client):
    res = await client.get("/api/v1/doctors/specialties")
    assert res.status_code == 200
    linked = {a for s in res.json() for a in s["related_assessments"]}
    assert {"diabetes", "heart", "liver", "skin", "pneumonia"} <= linked


async def test_search_and_details_require_auth(client):
    assert (await client.get("/api/v1/doctors/search")).status_code == 401
    assert (await client.get(f"/api/v1/doctors/{ObjectId()}")).status_code == 401


async def test_search_rejects_unknown_specialty(client):
    res = await client.get("/api/v1/doctors/search?specialty=astrology", headers=await _auth(client))
    assert res.status_code == 400


async def test_search_by_specialty_lists_consented_first_and_hides_inactive(client, seeded):
    city, _ = seeded
    res = await client.get(f"/api/v1/doctors/search?specialty=cardiology&city={city.lower()}",
                           headers=await _auth(client))
    assert res.status_code == 200
    body = res.json()
    # Specialty matches (consented first), then the general hospital, labelled.
    assert [d["name"] for d in body["items"]] == ["Dr. Test Sharma", "Apex Heart Hospital", "City Hospital"]
    assert [d["relevance"] for d in body["items"]] == ["specialty_match", "specialty_match", "general_care"]
    assert (body["total"], body["specialty_matches"]) == (3, 2)

    consented, osm, _general = body["items"]
    assert consented["listed_with_consent"] is True
    assert consented["phone_dial"] == "+919876543210"
    assert osm["listed_with_consent"] is False
    assert osm["phone"] is None  # never exposed for non-consented listings
    assert osm["specialty_source"] == "name_match"
    assert "OpenStreetMap" in osm["attribution"]
    place = f"Apex%20Heart%20Hospital%2C%20{city}"
    assert osm["directions_url"] == f"https://www.google.com/maps/dir//{place}/@28.8,78.7,17z"
    assert osm["google_maps_url"] == f"https://www.google.com/maps/search/{place}/@28.8,78.7,17z"


async def test_search_text_query_is_escaped_and_matches_address(client, seeded):
    city, _ = seeded
    headers = await _auth(client)
    res = await client.get(f"/api/v1/doctors/search?city={city}&q=(Near", headers=headers)
    assert res.status_code == 200
    assert [d["name"] for d in res.json()["items"]] == ["City Hospital"]


async def test_specialty_search_paginates_across_groups(client, seeded):
    city, _ = seeded
    headers = await _auth(client)
    url = f"/api/v1/doctors/search?specialty=cardiology&city={city}&page_size=2"
    page1 = (await client.get(url, headers=headers)).json()
    page2 = (await client.get(url + "&page=2", headers=headers)).json()
    assert [d["relevance"] for d in page1["items"]] == ["specialty_match", "specialty_match"]
    assert [(d["name"], d["relevance"]) for d in page2["items"]] == [("City Hospital", "general_care")]


async def test_unrelated_specialty_still_offers_general_hospitals(client, seeded):
    city, _ = seeded
    res = await client.get(f"/api/v1/doctors/search?specialty=neurology&city={city}", headers=await _auth(client))
    body = res.json()
    assert body["specialty_matches"] == 0
    assert [(d["name"], d["relevance"]) for d in body["items"]] == [("City Hospital", "general_care")]


async def test_consented_only_specialty_search_excludes_general(client, seeded):
    city, _ = seeded
    res = await client.get(f"/api/v1/doctors/search?specialty=cardiology&consented_only=true&city={city}",
                           headers=await _auth(client))
    assert [d["name"] for d in res.json()["items"]] == ["Dr. Test Sharma"]


async def test_search_sorts_nearest_first(client):
    city = f"TestCity{uuid.uuid4().hex[:8]}"
    origin = (28.8386, 78.7733)
    collection = db_manager.db["doctors"]
    base = {"city": city, "is_active": True, "kind": "hospital", "source": "osm",
            "listing_priority": 1, "specialties": []}
    await collection.insert_many([
        {**base, "source_id": f"test:{uuid.uuid4().hex}", "name": "A Far Hospital",
         "latitude": origin[0] + 0.1, "longitude": origin[1]},
        {**base, "source_id": f"test:{uuid.uuid4().hex}", "name": "B No Location Hospital"},
        {**base, "source_id": f"test:{uuid.uuid4().hex}", "name": "C Near Hospital",
         "latitude": origin[0] + 0.01, "longitude": origin[1]},
    ])
    try:
        res = await client.get(f"/api/v1/doctors/search?city={city}&lat={origin[0]}&lng={origin[1]}",
                               headers=await _auth(client))
        assert res.status_code == 200
        items = res.json()["items"]
        assert [d["name"] for d in items] == ["C Near Hospital", "A Far Hospital", "B No Location Hospital"]
        assert items[0]["distance_km"] == pytest.approx(1.1, abs=0.1)
        assert items[1]["distance_km"] == pytest.approx(11.1, abs=0.2)
        assert items[2]["distance_km"] is None
    finally:
        await collection.delete_many({"city": city})


async def test_search_without_location_has_no_distance(client, seeded):
    city, _ = seeded
    res = await client.get(f"/api/v1/doctors/search?city={city}", headers=await _auth(client))
    assert all(d["distance_km"] is None for d in res.json()["items"])


async def test_search_rejects_half_location(client):
    res = await client.get("/api/v1/doctors/search?lat=28.8", headers=await _auth(client))
    assert res.status_code == 400


async def test_search_consented_only(client, seeded):
    city, _ = seeded
    res = await client.get(f"/api/v1/doctors/search?city={city}&consented_only=true",
                           headers=await _auth(client))
    assert res.status_code == 200
    assert [d["name"] for d in res.json()["items"]] == ["Dr. Test Sharma"]


async def test_search_paginates(client, seeded):
    city, _ = seeded
    headers = await _auth(client)
    page1 = (await client.get(f"/api/v1/doctors/search?city={city}&page_size=2", headers=headers)).json()
    page2 = (await client.get(f"/api/v1/doctors/search?city={city}&page_size=2&page=2", headers=headers)).json()
    assert page1["total"] == page2["total"] == 3
    assert len(page1["items"]) == 2 and len(page2["items"]) == 1
    assert {d["id"] for d in page1["items"]}.isdisjoint({d["id"] for d in page2["items"]})


async def test_get_doctor(client, seeded):
    _, ids = seeded
    headers = await _auth(client)
    res = await client.get(f"/api/v1/doctors/{ids['consented']}", headers=headers)
    assert res.status_code == 200
    assert res.json()["phone"] == "98765 43210"

    assert (await client.get(f"/api/v1/doctors/{ids['closed']}", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/doctors/not-an-id", headers=headers)).status_code == 404
