"""
Clinical Rule Overlay for Heart Disease Risk Assessment
=======================================================

PURPOSE
-------
The SMOTE-balanced XGBoost model was trained on the CDC BRFSS 2022 survey
where the target is retrospective self-report of heart attack / angina
HISTORY.  Because functional symptoms (difficulty walking, concentrating)
are weakly correlated with past self-reported diagnosis in survey data, the
model assigns them low feature importance (< 1%) even though they carry
clinically established cardiovascular significance.

This module corrects that underweighting by applying a FLOOR (minimum
probability) to profiles whose clinical feature combination is established
by peer-reviewed cardiology guidelines as carrying meaningfully elevated risk.

DESIGN PRINCIPLES
-----------------
1. FLOOR ONLY - the overlay can only raise the probability, never lower it.
   The model natural score is always preserved when it already exceeds
   the tier floor.
2. DETERMINISTIC - same inputs always produce the same output.
3. CONSERVATIVE - every rule requires >= 2 compounding risk factors.
   Single-symptom profiles are never adjusted.
4. TRANSPARENT - every triggered rule is returned in rules_triggered so
   the caller can surface it in the response, logs, and audit trail.
5. NON-DIAGNOSTIC - all language follows AGENTS.md Section 11.

TIER DEFINITIONS
----------------
Tier 2  (floor >= 0.85 up to 0.93):
    Profiles with multiple simultaneous severe comorbidities in the
    stroke/metabolic disease cluster.
    Evidence basis: AHA/ACC 2021 secondary prevention guidelines.

Tier 1  (floor >= 0.60 up to 0.75):
    Profiles matching established Framingham / ACC/AHA compound risk
    factor clusters: older age + smoking + diabetes; stroke + age >= 50;
    cardio-renal syndrome; GOLD cardiopulmonary cluster;
    3+ comorbidities + poor health.

LIMITATIONS
-----------
- This overlay is NOT a validated clinical decision tool.
- It must not be used as a substitute for physician assessment.
- All outputs carry the standard RISK_ASSESSMENT_DISCLAIMER.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List

# ---------------------------------------------------------------------------
# Age category ordinal lookup (mirrors _AGE_CATEGORY_MAP in heart_model.py)
# ---------------------------------------------------------------------------
_AGE_ORDINAL: dict = {
    "Age 18 to 24": 1,  "Age 25 to 29": 2,  "Age 30 to 34": 3,
    "Age 35 to 39": 4,  "Age 40 to 44": 5,  "Age 45 to 49": 6,
    "Age 50 to 54": 7,  "Age 55 to 59": 8,  "Age 60 to 64": 9,
    "Age 65 to 69": 10, "Age 70 to 74": 11, "Age 75 to 79": 12,
    "Age 80 or older": 13,
}

_HEAVY_CURRENT_SMOKER = frozenset({
    "Current smoker - now smokes every day",
    "Current smoker - now smokes some days",
})
_ANY_SMOKER   = _HEAVY_CURRENT_SMOKER | frozenset({"Former smoker"})
_POOR_HEALTH  = frozenset({"Poor", "Fair"})

# Floor calibration
_T2_BASE = 0.85
_T2_STEP = 0.01
_T2_CAP  = 0.93
_T1_BASE = 0.60
_T1_STEP = 0.025
_T1_CAP  = 0.75


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class OverlayResult:
    """Returned by apply_clinical_overlay()."""
    adjusted_probability: float
    model_probability: float
    tier: Optional[int]
    rules_triggered: List[str] = field(default_factory=list)
    overlay_applied: bool = False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
def _age(raw: dict) -> int:
    return _AGE_ORDINAL.get(raw.get("AgeCategory", ""), 0)

def _yes(raw: dict, key: str) -> bool:
    return raw.get(key) == "Yes"

def _current_smoker(raw: dict) -> bool:
    return raw.get("SmokerStatus", "") in _HEAVY_CURRENT_SMOKER

def _any_smoker(raw: dict) -> bool:
    return raw.get("SmokerStatus", "") in _ANY_SMOKER

def _poor_health(raw: dict) -> bool:
    return raw.get("GeneralHealth", "") in _POOR_HEALTH


# ---------------------------------------------------------------------------
# Tier 2 rules (extreme risk - 85%+ floor)
# ---------------------------------------------------------------------------
def _evaluate_tier2(raw: dict):
    """
    T2-A: Stroke + metabolic disease + age >= 60 + functional decline
          Evidence: AHA/ACC 2021 secondary prevention guidelines.
          Prior stroke + diabetes/kidney disease in patients aged 60+ with
          functional decline is an established extreme cardiovascular risk cluster.

    T2-B: 5+ simultaneous severe comorbidities + age >= 65
          Evidence: Framingham / UKPDS cumulative risk data.
          Five or more concurrent cardiovascular comorbidities in patients
          aged 65+ represent compounding extreme hazard.
    """
    rules = []
    severity_points = 0

    # T2-A
    has_metabolic = _yes(raw, "HadDiabetes") or _yes(raw, "HadKidneyDisease")
    has_decline   = _yes(raw, "DifficultyWalking") or _poor_health(raw)
    if _yes(raw, "HadStroke") and has_metabolic and _age(raw) >= 9 and has_decline:
        rules.append(
            "T2-A: Stroke history + metabolic disease (diabetes or kidney disease)"
            " + age >= 60 + functional decline (difficulty walking or poor/fair health)."
            " [AHA/ACC 2021 secondary prevention guidelines]"
        )
        severity_points += 1
        if _yes(raw, "HadDiabetes") and _yes(raw, "HadKidneyDisease"):
            severity_points += 1

    # T2-B
    severe_flags = sum([
        _yes(raw, "HadStroke"),
        _yes(raw, "HadDiabetes"),
        _yes(raw, "HadKidneyDisease"),
        _yes(raw, "HadCOPD"),
        _yes(raw, "HadArthritis"),
        _yes(raw, "DifficultyWalking"),
        _yes(raw, "DifficultyErrands"),
        _current_smoker(raw),
    ])
    if severe_flags >= 5 and _age(raw) >= 10:
        rules.append(
            f"T2-B: {severe_flags}/8 severe comorbidity indicators present + age >= 65."
            " [Framingham / UKPDS cumulative risk data]"
        )
        severity_points += severe_flags - 4

    if not rules:
        return False, [], 0
    return True, rules, severity_points


# ---------------------------------------------------------------------------
# Tier 1 rules (severe risk - 60-75% floor)
# ---------------------------------------------------------------------------
def _evaluate_tier1(raw: dict):
    """
    T1-A: Age >= 65 + current smoker + diabetes
          Evidence: Framingham Heart Study - three compounding independent
          10-year CVD risk factors.

    T1-B: Stroke history + age >= 50
          Evidence: ACC/AHA secondary prevention guidelines - substantial
          recurrent cardiovascular event risk.

    T1-C: Diabetes + kidney disease + any smoking (cardio-renal syndrome)
          Evidence: Concurrent metabolic and renal disease amplified by
          tobacco exposure.

    T1-D: COPD + current smoking + difficulty walking
          Evidence: GOLD / AHA 2020 cardiopulmonary risk cluster. COPD
          patients continuing to smoke with functional limitation face
          dramatically elevated cardiac event rates.

    T1-E: 3+ severe comorbidities + poor/fair general health
          Evidence: Cumulative burden model - SF-36/EQ-5D literature shows
          self-rated health is a validated independent predictor alongside
          multiple concurrent conditions.
    """
    rules = []
    severity_points = 0

    # T1-A
    if _age(raw) >= 10 and _current_smoker(raw) and _yes(raw, "HadDiabetes"):
        rules.append(
            "T1-A: Age >= 65 + active smoking + diabetes."
            " [Framingham compound CVD risk factors]"
        )
        severity_points += 2

    # T1-B
    if _yes(raw, "HadStroke") and _age(raw) >= 7:
        rules.append(
            "T1-B: Stroke history + age >= 50."
            " [ACC/AHA secondary prevention - elevated recurrent event risk]"
        )
        severity_points += 2

    # T1-C
    if _yes(raw, "HadDiabetes") and _yes(raw, "HadKidneyDisease") and _any_smoker(raw):
        rules.append(
            "T1-C: Diabetes + kidney disease + smoking history."
            " [Cardio-renal syndrome risk cluster]"
        )
        severity_points += 1

    # T1-D
    if _yes(raw, "HadCOPD") and _current_smoker(raw) and _yes(raw, "DifficultyWalking"):
        rules.append(
            "T1-D: COPD + active smoking + difficulty walking."
            " [GOLD/AHA 2020 cardiopulmonary cluster]"
        )
        severity_points += 1

    # T1-E
    severe_count = sum([
        _yes(raw, "HadStroke"),
        _yes(raw, "HadDiabetes"),
        _yes(raw, "HadKidneyDisease"),
        _yes(raw, "HadCOPD"),
        _yes(raw, "DifficultyWalking"),
        _yes(raw, "DifficultyConcentrating"),
    ])
    if severe_count >= 3 and _poor_health(raw):
        rules.append(
            f"T1-E: {severe_count}/6 severe comorbidity indicators + poor/fair general health."
            " [Cumulative burden model - SF-36/EQ-5D evidence]"
        )
        severity_points += severe_count - 2

    if not rules:
        return False, [], 0
    return True, rules, severity_points


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def apply_clinical_overlay(model_probability: float, raw_features: dict) -> OverlayResult:
    """Apply tiered clinical rule overlay to the raw XGBoost probability.

    The overlay is a minimum floor. The model natural output is preserved
    when it already exceeds the tier floor.

    Parameters
    ----------
    model_probability : float
        Raw pipeline.predict_proba() output for the positive class, in [0, 1].
    raw_features : dict
        PascalCase string-valued feature dict from prediction_service.py
        (before encoding). All 24 heart feature keys must be present.

    Returns
    -------
    OverlayResult
    """
    # Tier 2 (extreme) takes precedence over Tier 1
    t2_hit, t2_rules, t2_severity = _evaluate_tier2(raw_features)
    if t2_hit:
        floor    = min(_T2_BASE + max(t2_severity - 1, 0) * _T2_STEP, _T2_CAP)
        adjusted = max(model_probability, floor)
        return OverlayResult(
            adjusted_probability=round(adjusted, 4),
            model_probability=round(model_probability, 4),
            tier=2,
            rules_triggered=t2_rules,
            overlay_applied=(adjusted > model_probability + 1e-9),
        )

    t1_hit, t1_rules, t1_severity = _evaluate_tier1(raw_features)
    if t1_hit:
        floor    = min(_T1_BASE + max(t1_severity - 1, 0) * _T1_STEP, _T1_CAP)
        adjusted = max(model_probability, floor)
        return OverlayResult(
            adjusted_probability=round(adjusted, 4),
            model_probability=round(model_probability, 4),
            tier=1,
            rules_triggered=t1_rules,
            overlay_applied=(adjusted > model_probability + 1e-9),
        )

    return OverlayResult(
        adjusted_probability=round(model_probability, 4),
        model_probability=round(model_probability, 4),
        tier=None,
        rules_triggered=[],
        overlay_applied=False,
    )
