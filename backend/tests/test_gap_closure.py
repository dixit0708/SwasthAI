"""Tests for the features added to close the synopsis gaps: emergency
detection, extended health profile, personalised diet/exercise/medication
guidance, saved-result history, appointments, document storage checks and
password reset."""
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.ai.safety.emergency_detection import MEDICAL_EMERGENCY, SELF_HARM, detect_emergency
from app.api.v1.endpoints.assistant import chat_rate_limiter
from app.api.v1.endpoints.auth import forgot_password_limiter
from app.core.config import settings
from app.db.mongodb import db_manager
from app.services import password_reset_service
from app.services.diet_service import build_exercise_plan, build_medication_guidance, evaluate_diet_rules
from conftest import unique_email

VALID_PASSWORD = "Correct-Horse9-Battery"
NEW_PASSWORD = "Fresh-Staple7-Window"


async def _register(client, email=None) -> tuple[str, str]:
    email = email or unique_email()
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": email, "password": VALID_PASSWORD},
    )
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Emergency detection (assistant)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("message", [
    "I have severe chest pain and I'm sweating",
    "my father can't breathe properly",
    "she is unconscious and not waking up",
    "I think I am having a stroke",
    "he is bleeding heavily from the leg",
    "shortness of breath since morning",
])
def test_medical_emergencies_are_detected(message):
    assert detect_emergency(message) == MEDICAL_EMERGENCY


@pytest.mark.parametrize("message", [
    "I want to kill myself",
    "I feel suicidal",
    "there is no reason to live anymore",
    "I took an overdose on purpose",
])
def test_self_harm_is_detected_and_takes_priority(message):
    assert detect_emergency(message) == SELF_HARM


@pytest.mark.parametrize("message", [
    "What should I eat for breakfast?",
    "How can I prevent a stroke in the future?",
    "Is fitness important for heart health?",
    "How do I lower my cholesterol?",
    "",
])
def test_ordinary_questions_are_not_flagged(message):
    assert detect_emergency(message) is None


@pytest.mark.asyncio
async def test_assistant_emergency_skips_llm_and_stores_no_text(client):
    chat_rate_limiter.reset()
    token, user_id = await _register(client)
    message = "I have crushing chest pain right now"

    with patch("app.services.assistant_service._call_gemini_api") as mock_llm:
        res = await client.post("/api/v1/assistant/chat", headers=_auth(token), json={"message": message})

    assert res.status_code == 200
    body = res.json()
    assert body["emergency"] is True
    assert "112" in body["response"]
    assert "108" in body["response"]
    mock_llm.assert_not_called()

    saved = await db_manager.db["ai_conversations"].find({"user_id": user_id}).to_list(length=10)
    assert len(saved) == 1
    assert saved[0]["emergency_flag"] == MEDICAL_EMERGENCY
    assert message not in str(saved[0])


@pytest.mark.asyncio
async def test_assistant_self_harm_points_to_crisis_line(client):
    chat_rate_limiter.reset()
    token, _ = await _register(client)
    res = await client.post(
        "/api/v1/assistant/chat", headers=_auth(token), json={"message": "I want to end my life"}
    )
    assert res.status_code == 200
    assert res.json()["emergency"] is True
    assert "14416" in res.json()["response"]


@pytest.mark.asyncio
async def test_assistant_chat_is_rate_limited_per_user(client):
    chat_rate_limiter.reset()
    token, _ = await _register(client)
    original_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = ""
    try:
        statuses = []
        for _ in range(chat_rate_limiter.max_requests + 1):
            res = await client.post("/api/v1/assistant/chat", headers=_auth(token), json={"message": "hello"})
            statuses.append(res.status_code)
        assert statuses[:-1] == [200] * chat_rate_limiter.max_requests
        assert statuses[-1] == 429
    finally:
        settings.GEMINI_API_KEY = original_key
        chat_rate_limiter.reset()


# ---------------------------------------------------------------------------
# Health profile: new fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_profile_stores_body_and_lifestyle_fields_and_derives_bmi(client):
    token, _ = await _register(client)
    res = await client.put(
        "/api/v1/health-profile/me",
        headers=_auth(token),
        json={
            "date_of_birth": "1990-01-01",
            "gender": "female",
            "height_cm": 160,
            "weight_kg": 64,
            "allergies": ["Peanuts", " peanuts ", "Penicillin", ""],
            "activity_level": "light",
            "diet_preference": "vegetarian",
            "smoking_status": "never",
            "alcohol_use": "none",
            "sleep_hours": 6.5,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["bmi"] == 25.0
    assert body["age"] >= 35
    assert body["allergies"] == ["Peanuts", "Penicillin"]
    assert body["diet_preference"] == "vegetarian"

    # A partial update must not wipe the other fields; null clears a field.
    res2 = await client.put(
        "/api/v1/health-profile/me", headers=_auth(token), json={"weight_kg": None, "sleep_hours": ""}
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["weight_kg"] is None
    assert body2["bmi"] is None
    assert body2["sleep_hours"] is None
    assert body2["height_cm"] == 160
    assert body2["gender"] == "female"


@pytest.mark.asyncio
async def test_profile_rejects_out_of_range_and_unknown_values(client):
    token, _ = await _register(client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    for payload in (
        {"height_cm": 500},
        {"weight_kg": -3},
        {"activity_level": "superhuman"},
        {"sleep_hours": 30},
        {"date_of_birth": tomorrow},
    ):
        res = await client.put("/api/v1/health-profile/me", headers=_auth(token), json=payload)
        assert res.status_code == 422, payload


# ---------------------------------------------------------------------------
# Diet, exercise and medication guidance
# ---------------------------------------------------------------------------

def test_elevated_diabetes_and_liver_assessments_drive_guidance():
    result = evaluate_diet_rules(bmi=22.0, diabetes_risk_elevated=True, liver_risk_elevated=True)
    assert "Diabetic Low-GI Diet" in result["diet_types"]
    assert "Liver-Friendly Diet" in result["diet_types"]
    assert "Balanced Indian Thali" not in result["diet_types"]


def test_lifestyle_inputs_tailor_guidance():
    result = evaluate_diet_rules(
        bmi=22.0,
        activity_level="sedentary",
        diet_preference="vegan",
        smoking_status="current",
        alcohol_use="regular",
        sleep_hours=5,
        allergies=["Peanuts"],
    )
    text = " ".join(result["lifestyle_guidance"]).lower()
    assert "tobacco" in text
    assert "alcohol" in text
    assert "sleep" in text
    notes = " ".join(result["preference_notes"])
    assert "B12" in notes
    assert "Peanuts" in notes


def test_exercise_plan_matches_activity_level_and_adds_cautions():
    default_plan = build_exercise_plan()
    assert default_plan["personalised"] is False
    assert len(default_plan["sessions"]) == 7

    active = build_exercise_plan(activity_level="active")
    assert active["personalised"] is True
    assert any(s["intensity"] == "vigorous" for s in active["sessions"])

    cautious = build_exercise_plan(activity_level="active", cardiac_caution=True, age=65, bmi=31)
    assert all(s["intensity"] != "vigorous" for s in cautious["sessions"])
    assert any("doctor" in c.lower() for c in cautious["cautions"])
    assert any("balance" in c.lower() for c in cautious["cautions"])


def test_medication_guidance_lists_medicines_without_dosing_advice():
    assert build_medication_guidance([]) == {"medications": [], "tips": []}

    guidance = build_medication_guidance(
        [{"name": "Metformin", "dosage": "500 mg", "frequency": "Twice daily"}], alcohol_use="occasional"
    )
    assert guidance["medications"][0]["name"] == "Metformin"
    tips = " ".join(guidance["tips"]).lower()
    assert "as prescribed" in tips
    assert "alcohol" in tips
    # Guidance must never tell the user to change a dose themselves.
    assert "increase your dose" not in tips and "reduce your dose" not in tips


@pytest.mark.asyncio
async def test_diet_endpoint_uses_profile_measurements_and_reports_missing_inputs(client):
    token, _ = await _register(client)

    first = await client.get("/api/v1/diet/recommendations", headers=_auth(token))
    assert first.status_code == 200
    assert set(first.json()["missing_inputs"]) == {"height_weight", "lifestyle", "risk_assessment"}

    await client.put(
        "/api/v1/health-profile/me",
        headers=_auth(token),
        json={"height_cm": 170, "weight_kg": 90, "activity_level": "moderate", "diet_preference": "eggetarian",
              "occupation_type": "working_professional", "cuisine_region": "north"},
    )
    second = await client.get("/api/v1/diet/recommendations", headers=_auth(token))
    body = second.json()
    assert body["metrics_evaluated"]["bmi"] == 31.1
    assert "Weight Management & Caloric Balance" in body["diet_types"]
    assert body["exercise_plan"]["personalised"] is True
    assert body["missing_inputs"] == ["risk_assessment"]


# ---------------------------------------------------------------------------
# Saved risk-assessment history
# ---------------------------------------------------------------------------

async def _seed_prediction(user_id: str, condition: str, elevated: bool, days_ago: int = 0) -> str:
    result = await db_manager.db["predictions"].insert_one({
        "user_id": user_id,
        "condition": condition,
        "model_version": "test",
        "input_snapshot": {"secret_input": 123},
        "result": {
            "risk_level": "screening_elevated" if elevated else "screening_negative",
            "risk_probability": 0.71 if elevated else 0.12,
            "is_elevated": elevated,
            "message": "Test message",
        },
        "created_at": datetime.now(timezone.utc) - timedelta(days=days_ago),
    })
    return str(result.inserted_id)


@pytest.mark.asyncio
async def test_diet_plan_uses_own_latest_assessments_and_ignores_family_results(client):
    token, user_id = await _register(client)
    await _seed_prediction(user_id, "diabetes", True, days_ago=3)
    await _seed_prediction(user_id, "heart_disease", False, days_ago=1)
    # An elevated liver result saved for a family member describes someone else.
    await db_manager.db["predictions"].insert_one({
        "user_id": user_id, "family_member_id": "fm-1", "condition": "liver_disease",
        "input_snapshot": {}, "result": {"risk_probability": 0.9, "is_elevated": True},
        "created_at": datetime.now(timezone.utc),
    })

    body = (await client.get("/api/v1/diet/recommendations", headers=_auth(token))).json()
    used = {a["assessment"]: a for a in body["assessments_used"]}
    assert set(used) == {"heart", "diabetes"}
    assert used["diabetes"]["is_elevated"] is True and "millets" in used["diabetes"]["plan_effect"]
    assert used["heart"]["is_elevated"] is False
    assert "Diabetic Low-GI Diet" in body["diet_types"]
    assert body["metrics_evaluated"]["liver_risk_elevated"] is False
    assert "risk_assessment" not in body["missing_inputs"]


@pytest.mark.asyncio
async def test_prediction_history_is_paginated_filtered_and_private(client):
    token_a, user_a = await _register(client)
    token_b, _ = await _register(client)

    assert (await client.get("/api/v1/predict/history")).status_code == 401

    await _seed_prediction(user_a, "heart_disease", True, days_ago=2)
    await _seed_prediction(user_a, "diabetes", False, days_ago=1)
    newest_id = await _seed_prediction(user_a, "liver_disease", False)

    res = await client.get("/api/v1/predict/history?page_size=2", headers=_auth(token_a))
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == newest_id
    assert body["items"][0]["condition_label"] == "Liver Disease Risk Assessment"
    # Raw inputs are never returned.
    assert "secret_input" not in res.text

    heart_only = await client.get("/api/v1/predict/history?assessment=heart", headers=_auth(token_a))
    assert [i["condition"] for i in heart_only.json()["items"]] == ["heart_disease"]

    assert (await client.get("/api/v1/predict/history?assessment=bogus", headers=_auth(token_a))).status_code == 400

    # Another user sees none of it and cannot delete it.
    assert (await client.get("/api/v1/predict/history", headers=_auth(token_b))).json()["total"] == 0
    assert (await client.delete(f"/api/v1/predict/history/{newest_id}", headers=_auth(token_b))).status_code == 404

    assert (await client.delete(f"/api/v1/predict/history/{newest_id}", headers=_auth(token_a))).status_code == 200
    assert (await client.get("/api/v1/predict/history", headers=_auth(token_a))).json()["total"] == 2


# ---------------------------------------------------------------------------
# Analysed report history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_report_history_lists_reads_and_deletes_only_own_reports(client):
    token_a, user_a = await _register(client)
    token_b, _ = await _register(client)

    inserted = await db_manager.db["medical_reports"].insert_one({
        "user_id": user_a,
        "filename": "cbc.pdf",
        "analyzer_version": "test",
        "result": {
            "values": [
                {"key": "hemoglobin", "label": "Hemoglobin", "category": "cbc", "value": 10.0, "unit": "g/dL",
                 "reference_low": 12.0, "reference_high": 16.0, "status": "low"},
                {"key": "wbc", "label": "WBC", "category": "cbc", "value": 7000, "unit": "/uL",
                 "reference_low": 4000, "reference_high": 11000, "status": "normal"},
            ],
            "qualitative_results": [],
            "summary": "1 of 2 values is outside the reference range.",
            "llm_explanation": None,
            "questions_to_ask": [],
            "disclaimer": "Not a diagnosis.",
            "analyzer_version": "test",
        },
        "created_at": datetime.now(timezone.utc),
    })
    report_id = str(inserted.inserted_id)

    listing = await client.get("/api/v1/report-analysis/history", headers=_auth(token_a))
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["filename"] == "cbc.pdf"
    assert item["values_count"] == 2
    assert item["flagged_count"] == 1

    detail = await client.get(f"/api/v1/report-analysis/history/{report_id}", headers=_auth(token_a))
    assert detail.status_code == 200
    assert detail.json()["values"][0]["label"] == "Hemoglobin"

    assert (await client.get("/api/v1/report-analysis/history", headers=_auth(token_b))).json()["total"] == 0
    assert (await client.get(f"/api/v1/report-analysis/history/{report_id}", headers=_auth(token_b))).status_code == 404
    assert (await client.delete(f"/api/v1/report-analysis/history/{report_id}", headers=_auth(token_b))).status_code == 404

    assert (await client.delete(f"/api/v1/report-analysis/history/{report_id}", headers=_auth(token_a))).status_code == 200
    assert (await client.get(f"/api/v1/report-analysis/history/{report_id}", headers=_auth(token_a))).status_code == 404


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

@pytest.fixture
async def doctor_id(client):
    city = f"test-city-{uuid.uuid4().hex}"
    result = await db_manager.db["doctors"].insert_one({
        "source": "consented",
        "source_id": f"test:{uuid.uuid4().hex}",
        "listing_priority": 0,
        "name": "Dr. Test Physician",
        "clinic_name": "Test Clinic",
        "city": city,
        "address": "1 Test Road",
        "phone": "+91 98765 43210",
        "phone_dial": "+919876543210",
        "timings": "Mon-Sat 10:00-14:00",
        "specialties": ["general_medicine"],
        "is_active": True,
    })
    yield str(result.inserted_id)
    await db_manager.db["doctors"].delete_many({"city": city})


@pytest.mark.asyncio
async def test_appointment_lifecycle(client, doctor_id):
    token, _ = await _register(client)
    next_week = (date.today() + timedelta(days=7)).isoformat()
    later = (date.today() + timedelta(days=9)).isoformat()

    assert (await client.get("/api/v1/appointments")).status_code == 401

    created = await client.post(
        "/api/v1/appointments",
        headers=_auth(token),
        json={"doctor_id": doctor_id, "appointment_date": next_week, "appointment_time": "10:30", "reason": "Follow-up"},
    )
    assert created.status_code == 201
    appt = created.json()
    # Never presented as confirmed by the clinic.
    assert appt["status"] == "scheduled"
    assert appt["doctor_name"] == "Dr. Test Physician"
    assert appt["timings"] == "Mon-Sat 10:00-14:00"
    assert appt["is_upcoming"] is True

    # Same slot twice is a conflict.
    clash = await client.post(
        "/api/v1/appointments",
        headers=_auth(token),
        json={"doctor_id": doctor_id, "appointment_date": next_week, "appointment_time": "10:30"},
    )
    assert clash.status_code == 409

    confirmed = await client.patch(
        f"/api/v1/appointments/{appt['id']}", headers=_auth(token), json={"status": "confirmed"}
    )
    assert confirmed.json()["status"] == "confirmed"

    # Rescheduling needs re-confirming with the clinic.
    moved = await client.patch(
        f"/api/v1/appointments/{appt['id']}",
        headers=_auth(token),
        json={"appointment_date": later, "appointment_time": "11:00"},
    )
    assert moved.status_code == 200
    assert moved.json()["appointment_date"] == later
    assert moved.json()["status"] == "scheduled"

    upcoming = await client.get("/api/v1/appointments?view=upcoming", headers=_auth(token))
    assert upcoming.json()["total"] == 1

    cancelled = await client.patch(
        f"/api/v1/appointments/{appt['id']}", headers=_auth(token), json={"status": "cancelled"}
    )
    assert cancelled.json()["status"] == "cancelled"
    assert (await client.get("/api/v1/appointments?view=upcoming", headers=_auth(token))).json()["total"] == 0
    assert (await client.get("/api/v1/appointments?view=past", headers=_auth(token))).json()["total"] == 1

    reopened = await client.patch(
        f"/api/v1/appointments/{appt['id']}", headers=_auth(token), json={"status": "confirmed"}
    )
    assert reopened.status_code == 400


@pytest.mark.asyncio
async def test_appointment_validation_and_ownership(client, doctor_id):
    token_a, _ = await _register(client)
    token_b, _ = await _register(client)
    next_week = (date.today() + timedelta(days=7)).isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    base = {"doctor_id": doctor_id, "appointment_date": next_week, "appointment_time": "09:00"}
    assert (await client.post("/api/v1/appointments", headers=_auth(token_a),
                              json={**base, "appointment_date": yesterday})).status_code == 422
    assert (await client.post("/api/v1/appointments", headers=_auth(token_a),
                              json={**base, "appointment_time": "25:00"})).status_code == 422
    assert (await client.post("/api/v1/appointments", headers=_auth(token_a),
                              json={**base, "doctor_id": "0" * 24})).status_code == 404
    # A family member id that is not the caller's is rejected.
    assert (await client.post("/api/v1/appointments", headers=_auth(token_a),
                              json={**base, "family_member_id": "0" * 24})).status_code == 400

    created = await client.post("/api/v1/appointments", headers=_auth(token_a), json=base)
    appt_id = created.json()["id"]

    assert (await client.get(f"/api/v1/appointments/{appt_id}", headers=_auth(token_b))).status_code == 404
    assert (await client.patch(f"/api/v1/appointments/{appt_id}", headers=_auth(token_b),
                               json={"status": "cancelled"})).status_code == 404
    assert (await client.delete(f"/api/v1/appointments/{appt_id}", headers=_auth(token_b))).status_code == 404
    assert (await client.get("/api/v1/appointments?view=all", headers=_auth(token_b))).json()["total"] == 0

    assert (await client.delete(f"/api/v1/appointments/{appt_id}", headers=_auth(token_a))).status_code == 200


# ---------------------------------------------------------------------------
# Document upload: signature check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_rejects_file_whose_content_does_not_match_its_extension(client):
    token, _ = await _register(client)
    member = await client.post(
        "/api/v1/family/members", headers=_auth(token), json={"name": "Parent", "relationship": "Parent"}
    )
    res = await client.post(
        "/api/v1/family/records",
        headers=_auth(token),
        data={"member_id": member.json()["id"], "title": "Fake", "category": "Other", "record_date": "2026-03-15"},
        files={"file": ("report.pdf", io.BytesIO(b"MZ this is not a pdf"), "application/pdf")},
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Password reset and change
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forgot_password_reports_unavailable_when_email_is_not_configured(client):
    forgot_password_limiter.reset()
    original = settings.SMTP_HOST
    settings.SMTP_HOST = ""
    try:
        res = await client.post("/api/v1/auth/forgot-password", json={"email": unique_email()})
        assert res.status_code == 503
    finally:
        settings.SMTP_HOST = original


@pytest.mark.asyncio
async def test_password_reset_flow_is_single_use_and_signs_out_old_sessions(client):
    forgot_password_limiter.reset()
    email = unique_email()
    old_token, _ = await _register(client, email)

    original = (settings.SMTP_HOST, settings.SMTP_FROM)
    settings.SMTP_HOST, settings.SMTP_FROM = "smtp.test", "noreply@example.com"
    sent = {}

    def fake_send(to_address, subject, body):
        sent["to"], sent["body"] = to_address, body

    try:
        with patch("app.core.email.send_email", side_effect=fake_send):
            # Unknown address: same response, nothing sent.
            unknown = await client.post("/api/v1/auth/forgot-password", json={"email": unique_email()})
            assert unknown.status_code == 200
            assert sent == {}

            known = await client.post("/api/v1/auth/forgot-password", json={"email": email})
            assert known.status_code == 200
            assert known.json() == unknown.json()
    finally:
        settings.SMTP_HOST, settings.SMTP_FROM = original

    assert sent["to"] == email
    reset_token = sent["body"].split("token=")[1].split()[0]

    # Only a hash of the token is stored.
    stored = await db_manager.db["password_resets"].find_one({})
    assert reset_token not in str(stored)

    weak = await client.post("/api/v1/auth/reset-password", json={"token": reset_token, "new_password": "weakpass"})
    assert weak.status_code == 422

    done = await client.post("/api/v1/auth/reset-password", json={"token": reset_token, "new_password": NEW_PASSWORD})
    assert done.status_code == 200

    # Single use.
    again = await client.post("/api/v1/auth/reset-password", json={"token": reset_token, "new_password": NEW_PASSWORD})
    assert again.status_code == 400

    # Old password and old sessions no longer work; the new password does.
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=_auth(old_token))).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": NEW_PASSWORD})).status_code == 200


@pytest.mark.asyncio
async def test_expired_reset_token_is_rejected(client):
    email = unique_email()
    _, user_id = await _register(client, email)
    token = "expired-token-value-123456"
    await db_manager.db["password_resets"].insert_one({
        "user_id": user_id,
        "token_hash": password_reset_service._hash_token(token),
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    })
    res = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert res.status_code == 400
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})).status_code == 200


@pytest.mark.asyncio
async def test_change_password_requires_current_password(client):
    email = unique_email()
    token, _ = await _register(client, email)

    wrong = await client.post(
        "/api/v1/auth/change-password",
        headers=_auth(token),
        json={"current_password": "Not-My-Password1!", "new_password": NEW_PASSWORD},
    )
    assert wrong.status_code == 400

    ok = await client.post(
        "/api/v1/auth/change-password",
        headers=_auth(token),
        json={"current_password": VALID_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert ok.status_code == 200
    new_token = ok.json()["access_token"]
    assert (await client.get("/api/v1/auth/me", headers=_auth(new_token))).status_code == 200
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": NEW_PASSWORD})).status_code == 200


# ---------------------------------------------------------------------------
# Indian meal plan from the Diet & Lifestyle questionnaire
# ---------------------------------------------------------------------------

from app.services.indian_meal_plan import build_daily_meal_plan  # noqa: E402

_NON_VEG_WORDS = ("fish", "chicken", "mutton", "egg")


def _plan_text(plan) -> str:
    return " ".join(" ".join(m["items"]) + " " + (m["tip"] or "") for m in plan["meals"]).lower()


def test_vegetarian_and_jain_plans_contain_no_meat_fish_or_eggs():
    for pref in ("vegetarian", "jain", "vegan"):
        text = _plan_text(build_daily_meal_plan("working_professional", pref, "north"))
        assert not any(word in text for word in _NON_VEG_WORDS), pref


def test_jain_plan_leaves_out_onion_garlic_and_root_vegetables():
    text = _plan_text(build_daily_meal_plan("homemaker", "jain", "west"))
    assert "made without onion, garlic" in text
    assert "salad (cucumber, tomato, onion, carrot)" not in text
    assert "khichdi" not in text or "onion" not in text.split("khichdi")[1][:40]


def test_vegan_plan_has_no_dairy_suggestions():
    plan = build_daily_meal_plan("physical_work", "vegan", "north", underweight=True)
    text = _plan_text(plan) + " ".join(plan["swaps"]).lower()
    for dairy in ("glass of milk", "paneer", "bowl of curd or a glass of buttermilk", "ghee"):
        assert dairy not in text, dairy


def test_non_vegetarian_plan_includes_fish_or_chicken():
    text = _plan_text(build_daily_meal_plan("working_professional", "non_vegetarian", "east"))
    assert "fish" in text or "chicken" in text


def test_regional_staples_follow_the_cuisine_answer():
    assert "idli" in _plan_text(build_daily_meal_plan("homemaker", "vegetarian", "south"))
    assert "roti" in _plan_text(build_daily_meal_plan("homemaker", "vegetarian", "north"))
    assert "bhakri" in _plan_text(build_daily_meal_plan("homemaker", "vegetarian", "west"))


def test_blood_sugar_caution_swaps_white_rice_for_millets():
    plan = build_daily_meal_plan("working_professional", "vegetarian", "south", glucose_caution=True)
    lunch = next(m for m in plan["meals"] if m["slot"] == "Lunch")
    assert "brown rice" in lunch["items"][0] or "ragi" in lunch["items"][0]
    assert "1 cup of rice" not in _plan_text(plan)
    assert any("millet" in s.lower() for s in plan["swaps"])


def test_night_shift_plan_is_timed_around_the_shift():
    plan = build_daily_meal_plan("night_shift", "vegetarian", "north")
    slots = [m["slot"] for m in plan["meals"]]
    assert "Before your shift" in slots
    assert "During the shift" in slots
    assert "After the shift, before sleep" in slots
    assert "Breakfast" not in slots
    assert plan["schedule_note"]


def test_student_plan_has_tiffin_guidance_and_routine_tips():
    result = evaluate_diet_rules(bmi=21.0, occupation_type="student", diet_preference="vegetarian", cuisine_region="north")
    lunch = next(m for m in result["meal_plan"]["meals"] if "Lunch" in m["slot"])
    assert "tiffin" in lunch["tip"].lower()
    assert any("14416" in tip for tip in result["routine_tips"])
    assert result["exercise_plan"]["timing_tip"]
    assert result["meal_plan"]["plan_for"] == {"occupation": "Student", "diet": "Vegetarian", "region": "North Indian"}


def test_unanswered_questionnaire_still_gives_a_vegetarian_safe_default_plan():
    result = evaluate_diet_rules(bmi=22.0)
    assert len(result["meal_plan"]["meals"]) == 6
    assert result["routine_tips"] == []
    assert result["meal_plan"]["plan_for"] == {"occupation": None, "diet": None, "region": None}


@pytest.mark.asyncio
async def test_questionnaire_answers_save_and_shape_the_plan(client):
    token, _ = await _register(client)

    first = await client.get("/api/v1/diet/recommendations", headers=_auth(token))
    assert "lifestyle" in first.json()["missing_inputs"]

    saved = await client.put(
        "/api/v1/health-profile/me",
        headers=_auth(token),
        json={"occupation_type": "night_shift", "diet_preference": "jain", "cuisine_region": "south", "activity_level": "light"},
    )
    assert saved.status_code == 200
    assert saved.json()["occupation_type"] == "night_shift"
    assert saved.json()["cuisine_region"] == "south"

    plan = (await client.get("/api/v1/diet/recommendations", headers=_auth(token))).json()
    assert "lifestyle" not in plan["missing_inputs"]
    assert plan["meal_plan"]["plan_for"]["occupation"] == "Night or rotating shift worker"
    assert any(m["slot"] == "During the shift" for m in plan["meal_plan"]["meals"])

    bad = await client.put("/api/v1/health-profile/me", headers=_auth(token), json={"occupation_type": "astronaut"})
    assert bad.status_code == 422
