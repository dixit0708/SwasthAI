import io
from datetime import date, timedelta
import pytest
from conftest import unique_email

VALID_PASSWORD = "correct-horse-battery-staple"


async def _register_and_get_token(client, email=None, name="Test User") -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email or unique_email(), "password": VALID_PASSWORD},
    )
    assert res.status_code == 201
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Auth Boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_family_endpoints_require_auth(client):
    assert (await client.get("/api/v1/family/overview")).status_code == 401
    assert (await client.get("/api/v1/family/members")).status_code == 401
    assert (await client.post("/api/v1/family/members", json={"name": "X", "relationship": "Child"})).status_code == 401
    assert (await client.get("/api/v1/family/records")).status_code == 401
    assert (await client.get("/api/v1/family/medications")).status_code == 401
    assert (await client.get("/api/v1/family/measurements")).status_code == 401
    assert (await client.get("/api/v1/family/timeline")).status_code == 401


# ---------------------------------------------------------------------------
# 2. Family Member Lifecycle & Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_manage_family_member(client):
    token = await _register_and_get_token(client)

    # 1. Reject future birth date
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res_bad = await client.post(
        "/api/v1/family/members",
        headers=_auth(token),
        json={"name": "Baby", "relationship": "Child", "date_of_birth": tomorrow},
    )
    assert res_bad.status_code == 422 or res_bad.status_code == 400

    # 1b. Reject invalid phone numbers
    res_bad_phone = await client.post(
        "/api/v1/family/members",
        headers=_auth(token),
        json={"name": "Baby", "relationship": "Child", "phone": "12345"},
    )
    assert res_bad_phone.status_code == 422

    res_repeating_phone = await client.post(
        "/api/v1/family/members",
        headers=_auth(token),
        json={"name": "Baby", "relationship": "Child", "phone": "0000000000"},
    )
    assert res_repeating_phone.status_code == 422

    # 2. Valid creation with calculated age and validated phone
    ten_years_ago = (date.today() - timedelta(days=365 * 10 + 2)).isoformat()
    res = await client.post(
        "/api/v1/family/members",
        headers=_auth(token),
        json={
            "name": "Arjun Sharma",
            "relationship": "Child",
            "date_of_birth": ten_years_ago,
            "gender": "Male",
            "blood_group": "B+",
            "phone": "+91 98765 43210",
            "emergency_contact": "Sunita - 9876543211",
            "notes": "Mild asthma in winter",
        },
    )
    assert res.status_code == 201
    member = res.json()
    assert member["name"] == "Arjun Sharma"
    assert member["relationship"] == "Child"
    assert member["blood_group"] == "B+"
    assert member["age"] == 10
    member_id = member["id"]

    # 3. Retrieve member
    res_get = await client.get(f"/api/v1/family/members/{member_id}", headers=_auth(token))
    assert res_get.status_code == 200
    assert res_get.json()["id"] == member_id

    # 4. Update member
    res_up = await client.put(
        f"/api/v1/family/members/{member_id}",
        headers=_auth(token),
        json={"blood_group": "O+", "notes": "Updated allergy notes"},
    )
    assert res_up.status_code == 200
    assert res_up.json()["blood_group"] == "O+"
    assert res_up.json()["notes"] == "Updated allergy notes"

    # 5. List members
    res_list = await client.get("/api/v1/family/members", headers=_auth(token))
    assert res_list.status_code == 200
    members = res_list.json()
    assert len(members) == 1
    assert members[0]["name"] == "Arjun Sharma"

    # 6. Delete member
    res_del = await client.delete(f"/api/v1/family/members/{member_id}", headers=_auth(token))
    assert res_del.status_code == 200

    # Verify deleted
    res_check = await client.get(f"/api/v1/family/members/{member_id}", headers=_auth(token))
    assert res_check.status_code == 404


# ---------------------------------------------------------------------------
# 3. Multi-Tenant Privacy Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_user_isolation(client):
    user_a_token = await _register_and_get_token(client, name="User A")
    user_b_token = await _register_and_get_token(client, name="User B")

    # User A creates member
    res_a = await client.post(
        "/api/v1/family/members",
        headers=_auth(user_a_token),
        json={"name": "A's Mother", "relationship": "Parent"},
    )
    assert res_a.status_code == 201
    member_a_id = res_a.json()["id"]

    # User B tries to view member A -> 404 Not Found (privacy safe)
    res_b_view = await client.get(f"/api/v1/family/members/{member_a_id}", headers=_auth(user_b_token))
    assert res_b_view.status_code == 404

    # User B tries to update member A -> 404 Not Found
    res_b_up = await client.put(
        f"/api/v1/family/members/{member_a_id}",
        headers=_auth(user_b_token),
        json={"name": "Hacked"},
    )
    assert res_b_up.status_code == 404

    # User B tries to delete member A -> 404 Not Found
    res_b_del = await client.delete(f"/api/v1/family/members/{member_a_id}", headers=_auth(user_b_token))
    assert res_b_del.status_code == 404

    # User B's list should not show User A's member
    res_b_list = await client.get("/api/v1/family/members", headers=_auth(user_b_token))
    assert res_b_list.status_code == 200
    assert len(res_b_list.json()) == 0


# ---------------------------------------------------------------------------
# 4. Medical History
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_medical_history_operations(client):
    token = await _register_and_get_token(client)
    res = await client.post(
        "/api/v1/family/members",
        headers=_auth(token),
        json={"name": "Father", "relationship": "Parent"},
    )
    member_id = res.json()["id"]

    # Add medical history
    res_hist = await client.post(
        f"/api/v1/family/members/{member_id}/history",
        headers=_auth(token),
        json={
            "title": "Hypertension",
            "category": "condition",
            "diagnosed_date": "2020-05-10",
            "status": "ongoing",
            "doctor_or_hospital": "City Hospital",
            "notes": "Takes daily morning medication",
        },
    )
    assert res_hist.status_code == 201
    member_data = res_hist.json()
    assert len(member_data["medical_history"]) == 1
    item = member_data["medical_history"][0]
    assert item["title"] == "Hypertension"
    item_id = item["id"]

    # Update medical history
    res_up = await client.put(
        f"/api/v1/family/members/{member_id}/history/{item_id}",
        headers=_auth(token),
        json={"status": "in_management", "notes": "Under control with diet"},
    )
    assert res_up.status_code == 200
    up_item = res_up.json()["medical_history"][0]
    assert up_item["status"] == "in_management"
    assert up_item["notes"] == "Under control with diet"

    # Delete medical history
    res_del = await client.delete(
        f"/api/v1/family/members/{member_id}/history/{item_id}",
        headers=_auth(token),
    )
    assert res_del.status_code == 200
    assert len(res_del.json()["medical_history"]) == 0


# ---------------------------------------------------------------------------
# 5. Medical Records & Document Upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_medical_records_and_documents(client):
    user_a = await _register_and_get_token(client, name="Record Owner")
    user_b = await _register_and_get_token(client, name="Stranger")

    res = await client.post(
        "/api/v1/family/members",
        headers=_auth(user_a),
        json={"name": "Spouse", "relationship": "Spouse"},
    )
    member_id = res.json()["id"]

    # 1. Create record with document upload (e.g. PDF)
    fake_pdf = b"%PDF-1.4 test medical report content"
    res_upload = await client.post(
        "/api/v1/family/records",
        headers=_auth(user_a),
        data={
            "member_id": member_id,
            "title": "Annual Blood Panel",
            "category": "Lab Report",
            "record_date": "2026-03-15",
            "provider": "Apex Diagnostic Labs",
            "notes": "All values within normal range",
        },
        files={"file": ("blood_test_2026.pdf", io.BytesIO(fake_pdf), "application/pdf")},
    )
    assert res_upload.status_code == 201
    rec = res_upload.json()
    assert rec["title"] == "Annual Blood Panel"
    assert rec["category"] == "Lab Report"
    assert rec["file_name"] == "blood_test_2026.pdf"
    assert rec["has_document"] is True
    rec_id = rec["id"]

    # 2. Reject invalid file format
    res_bad_file = await client.post(
        "/api/v1/family/records",
        headers=_auth(user_a),
        data={
            "member_id": member_id,
            "title": "Bad File Test",
            "category": "Other",
            "record_date": "2026-03-15",
        },
        files={"file": ("bad_script.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
    )
    assert res_bad_file.status_code == 400

    # 3. Secure Document Retrieval - User A can download
    res_download = await client.get(
        f"/api/v1/family/records/{rec_id}/document",
        headers=_auth(user_a),
    )
    assert res_download.status_code == 200
    assert res_download.content == fake_pdf

    # 4. Privacy Check - User B CANNOT download User A's document
    res_stranger_dl = await client.get(
        f"/api/v1/family/records/{rec_id}/document",
        headers=_auth(user_b),
    )
    assert res_stranger_dl.status_code == 404

    # 5. List and search records
    res_search = await client.get(
        f"/api/v1/family/records?search=Apex",
        headers=_auth(user_a),
    )
    assert res_search.status_code == 200
    assert len(res_search.json()) == 1

    # 6. Delete record
    res_del_rec = await client.delete(f"/api/v1/family/records/{rec_id}", headers=_auth(user_a))
    assert res_del_rec.status_code == 200

    # Verify document no longer accessible
    res_dl_deleted = await client.get(
        f"/api/v1/family/records/{rec_id}/document",
        headers=_auth(user_a),
    )
    assert res_dl_deleted.status_code == 404


# ---------------------------------------------------------------------------
# 6. Prescriptions and Medications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_medications_management(client):
    token = await _register_and_get_token(client)
    res = await client.post(
        "/api/v1/family/members",
        headers=_auth(token),
        json={"name": "Grandmother", "relationship": "Grandparent"},
    )
    member_id = res.json()["id"]

    # Create medication
    res_med = await client.post(
        "/api/v1/family/medications",
        headers=_auth(token),
        json={
            "member_id": member_id,
            "name": "Metformin",
            "dosage": "500 mg",
            "frequency": "Twice daily with meals",
            "instructions": "Take with breakfast and dinner",
            "prescribing_doctor": "Dr. Verma",
            "start_date": "2026-01-01",
            "status": "active",
        },
    )
    assert res_med.status_code == 201
    med = res_med.json()
    assert med["name"] == "Metformin"
    assert med["dosage"] == "500 mg"
    assert med["status"] == "active"
    med_id = med["id"]

    # Update medication status to completed
    res_up = await client.put(
        f"/api/v1/family/medications/{med_id}",
        headers=_auth(token),
        json={"status": "completed", "end_date": "2026-06-30"},
    )
    assert res_up.status_code == 200
    assert res_up.json()["status"] == "completed"

    # List medications
    res_list = await client.get(f"/api/v1/family/medications?member_id={member_id}", headers=_auth(token))
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1

    # Delete medication
    res_del = await client.delete(f"/api/v1/family/medications/{med_id}", headers=_auth(token))
    assert res_del.status_code == 200


# ---------------------------------------------------------------------------
# 7. Health Measurements / Progress & Timeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_measurements_and_timeline(client):
    token = await _register_and_get_token(client)
    res = await client.post(
        "/api/v1/family/members",
        headers=_auth(token),
        json={"name": "Sister", "relationship": "Sibling"},
    )
    member_id = res.json()["id"]

    # Add BP measurement
    res_m1 = await client.post(
        "/api/v1/family/measurements",
        headers=_auth(token),
        json={
            "member_id": member_id,
            "metric_type": "blood_pressure",
            "metric_name": "Blood Pressure",
            "value": 120.0,
            "value_secondary": 80.0,
            "unit": "mmHg",
            "recorded_date": "2026-04-01",
            "notes": "Resting BP",
        },
    )
    assert res_m1.status_code == 201

    # Add second measurement
    res_m2 = await client.post(
        "/api/v1/family/measurements",
        headers=_auth(token),
        json={
            "member_id": member_id,
            "metric_type": "blood_pressure",
            "metric_name": "Blood Pressure",
            "value": 118.0,
            "value_secondary": 78.0,
            "unit": "mmHg",
            "recorded_date": "2026-04-10",
        },
    )
    assert res_m2.status_code == 201

    # List measurements (chronological)
    res_vitals = await client.get(
        f"/api/v1/family/measurements?member_id={member_id}&metric_type=blood_pressure",
        headers=_auth(token),
    )
    assert res_vitals.status_code == 200
    items = res_vitals.json()
    assert len(items) == 2
    assert items[0]["value"] == 120.0
    assert items[1]["value"] == 118.0

    # Retrieve timeline
    res_timeline = await client.get(
        f"/api/v1/family/timeline?member_id={member_id}",
        headers=_auth(token),
    )
    assert res_timeline.status_code == 200
    events = res_timeline.json()
    assert len(events) >= 2
    # Newest first
    assert events[0]["date"] >= events[1]["date"]

    # Check Family Overview
    res_ov = await client.get("/api/v1/family/overview", headers=_auth(token))
    assert res_ov.status_code == 200
    ov = res_ov.json()
    assert ov["total_members"] == 1
