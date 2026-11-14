from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
import pytest

from app.db.collections import HealthProfileRepository, PredictionRepository
from app.services.diet_service import evaluate_diet_rules, get_diet_and_lifestyle_guidance



def test_evaluate_diet_rules_bmi_over_25():
    result = evaluate_diet_rules(bmi=28.5)
    assert "Weight Management & Caloric Balance" in result["diet_types"]
    categories = [r["category"] for r in result["recommendations"]]
    assert "Weight Management" in categories
    wm = next(r for r in result["recommendations"] if r["category"] == "Weight Management")
    assert any("caloric deficit" in rule.lower() for rule in wm["rules"])
    assert any("fiber" in rule.lower() for rule in wm["rules"])


def test_evaluate_diet_rules_normal_bmi_no_weight_loss_rules():
    result = evaluate_diet_rules(bmi=22.0)
    assert "Weight Management & Caloric Balance" not in result["diet_types"]
    # Should fall back to the balanced Indian thali baseline if no other risks
    assert "Balanced Indian Thali" in result["diet_types"]


def test_evaluate_diet_rules_high_heart_risk_triggers_dash_and_low_sodium():
    result = evaluate_diet_rules(heart_risk=0.62)  # > 50%
    assert "DASH Diet" in result["diet_types"]
    assert "Low Sodium Diet" in result["diet_types"]
    cardio_rec = next(r for r in result["recommendations"] if "Cardiovascular" in r["category"])
    assert any("sodium" in rule.lower() for rule in cardio_rec["rules"])
    assert any("potassium" in rule.lower() for rule in cardio_rec["rules"])


def test_evaluate_diet_rules_high_bp_triggers_dash_and_low_sodium():
    result = evaluate_diet_rules(high_bp=True)
    assert "DASH Diet" in result["diet_types"]
    assert "Low Sodium Diet" in result["diet_types"]


def test_evaluate_diet_rules_high_fasting_glucose_triggers_low_gi():
    result = evaluate_diet_rules(fasting_glucose=115.0)  # >= 100 mg/dL
    assert "Diabetic Low-GI Diet" in result["diet_types"]
    diabetic_rec = next(r for r in result["recommendations"] if "Glycemic" in r["category"])
    assert any("glycemic index" in rule.lower() for rule in diabetic_rec["rules"])
    assert any("complex carbohydrates" in rule.lower() for rule in diabetic_rec["rules"])


def test_evaluate_diet_rules_diabetes_condition_triggers_low_gi():
    result = evaluate_diet_rules(conditions=["Type 2 Diabetes"])
    assert "Diabetic Low-GI Diet" in result["diet_types"]


def test_evaluate_diet_rules_multiple_clinical_risks_combined():
    result = evaluate_diet_rules(
        bmi=29.2,
        heart_risk=0.58,
        high_bp=True,
        fasting_glucose=126.0,
        conditions=["Hypertension"],
    )
    assert "Weight Management & Caloric Balance" in result["diet_types"]
    assert "DASH Diet" in result["diet_types"]
    assert "Low Sodium Diet" in result["diet_types"]
    assert "Diabetic Low-GI Diet" in result["diet_types"]
    assert len(result["recommendations"]) == 3
    assert result["disclaimer"]


def test_evaluate_diet_rules_baseline_healthy_user():
    result = evaluate_diet_rules(
        bmi=21.5,
        heart_risk=0.08,
        high_bp=False,
        fasting_glucose=85.0,
        conditions=[],
    )
    assert result["diet_types"] == ["Balanced Indian Thali"]
    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["category"] == "General Preventive Health"


@pytest.mark.asyncio
async def test_get_diet_guidance_extracts_from_user_db_records():
    mock_profile = {
        "user_id": "test-user-123",
        "conditions": [{"label": "Hypertension"}],
    }
    mock_predictions = [
        {
            "condition": "heart_disease",
            "input_snapshot": {"BMI": 27.5, "HighBP": 1, "systolic_bp": 140, "diastolic_bp": 90},
            "result": {"risk_probability": 0.55, "risk_level": "screening_elevated"},
        },
        {
            "condition": "diabetes_pima",
            # The lab-value diabetes assessment records a 2-hour OGTT reading.
            "input_snapshot": {"Glucose": 160.0, "BMI": 27.5},
            "result": {"risk_probability": 0.40, "risk_level": "screening_negative"},
        },
    ]

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=mock_predictions)

    mock_hp_col = MagicMock()
    mock_hp_col.find_one = AsyncMock(return_value=mock_profile)

    mock_pred_col = MagicMock()
    mock_pred_col.find = MagicMock(return_value=mock_cursor)


    with patch.object(HealthProfileRepository, "collection", new_callable=PropertyMock, return_value=mock_hp_col), \
         patch.object(PredictionRepository, "collection", new_callable=PropertyMock, return_value=mock_pred_col):
        
        guidance = await get_diet_and_lifestyle_guidance("test-user-123")


        assert guidance["user_id"] == "test-user-123"
        assert "Weight Management & Caloric Balance" in guidance["diet_types"]
        assert "DASH Diet" in guidance["diet_types"]
        assert "Diabetic Low-GI Diet" in guidance["diet_types"]
        assert guidance["metrics_evaluated"]["bmi"] == 27.5
        assert guidance["metrics_evaluated"]["high_bp"] is True
        # A 2-hour OGTT reading is never treated as a fasting reading.
        assert guidance["metrics_evaluated"]["fasting_glucose"] is None
        assert guidance["metrics_evaluated"]["two_hour_glucose"] == 160.0
        assert [a["assessment"] for a in guidance["assessments_used"]] == ["heart", "diabetes"]



# ── Assessment results feeding the plan ─────────────────────────────────────
from app.services.diet_service import (  # noqa: E402
    _assessments_used,
    _latest_per_assessment,
    _signals_from_assessments,
)


def _pred(condition, elevated, snapshot=None, prob=0.3, **extra):
    return {
        "condition": condition,
        "input_snapshot": snapshot or {},
        "result": {"risk_probability": prob, "is_elevated": elevated},
        **extra,
    }


def test_heart_models_own_verdict_triggers_heart_friendly_plan():
    # 30% is below the old fixed 50% cut-off, but the model flagged it.
    signals = _signals_from_assessments(_latest_per_assessment([_pred("heart_disease", True, prob=0.30)]))
    assert signals["heart_elevated"] is True
    result = evaluate_diet_rules(heart_risk=signals["heart_risk"], heart_risk_elevated=True)
    assert "DASH Diet" in result["diet_types"]
    assert result["metrics_evaluated"]["heart_risk_elevated"] is True
    assert "heart disease risk assessment" in result["recommendations"][0]["reason"].lower()


def test_each_model_keeps_its_own_latest_result():
    newest_first = [
        _pred("diabetes", False),        # newer lifestyle-question result
        _pred("diabetes_pima", True),    # older lab-value result, still current for that model
        _pred("diabetes", True),         # superseded by the newer lifestyle result
    ]
    latest = _latest_per_assessment(newest_first)
    assert [p["condition"] for p in latest] == ["diabetes", "diabetes_pima"]
    assert _signals_from_assessments(latest)["diabetes_elevated"] is True


def test_newer_result_of_same_model_replaces_older_one():
    latest = _latest_per_assessment([_pred("liver_disease", False), _pred("liver_disease", True)])
    assert _signals_from_assessments(latest)["liver_elevated"] is False


def test_skin_results_do_not_shape_diet():
    assert _latest_per_assessment([_pred("skin", True)]) == []


def test_two_hour_glucose_uses_its_own_range():
    normal = evaluate_diet_rules(two_hour_glucose=120.0)
    assert "Diabetic Low-GI Diet" not in normal["diet_types"]
    high = evaluate_diet_rules(two_hour_glucose=165.0)
    assert "Diabetic Low-GI Diet" in high["diet_types"]
    assert "2-hour glucose" in high["recommendations"][0]["reason"]


def test_cholesterol_and_yes_no_answers_are_read():
    latest = _latest_per_assessment([
        _pred("diabetes", False, {"HighChol": 1}),
        _pred("liver_disease", False, {"hypertension": "Yes"}),
    ])
    signals = _signals_from_assessments(latest)
    assert signals["high_cholesterol"] is True
    assert signals["high_bp"] is True
    result = evaluate_diet_rules(high_cholesterol=True)
    assert "DASH Diet" in result["diet_types"]
    assert "cholesterol" in result["recommendations"][0]["reason"].lower()


def test_assessments_used_explains_effect():
    items = _assessments_used([_pred("liver_disease_ilpd", True), _pred("heart_disease_clinical", False)])
    assert items[0]["assessment"] == "liver" and items[0]["is_elevated"] is True
    assert "alcohol" in items[0]["plan_effect"]
    assert items[1]["plan_effect"].startswith("No extra changes")
