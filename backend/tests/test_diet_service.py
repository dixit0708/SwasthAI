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
    # Should fall back to Mediterranean baseline if no other risks
    assert "Balanced Mediterranean Wellness Diet" in result["diet_types"]


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
    assert result["diet_types"] == ["Balanced Mediterranean Wellness Diet"]
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
            "input_snapshot": {"Glucose": 120.0, "BMI": 27.5},
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
        assert guidance["metrics_evaluated"]["fasting_glucose"] == 120.0

