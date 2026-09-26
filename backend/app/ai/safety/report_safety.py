"""
Turns extracted, classified lab values into a non-diagnostic, plain-language
summary — the report-analyzer counterpart to response_filter.py. Every
report analysis response must be routed through this before it reaches the
client (AGENTS.md Section 11): it never states a diagnosis, only describes
which recognized values sit outside a general reference range.
"""
from app.ai.safety.medical_disclaimer import REPORT_ANALYSIS_DISCLAIMER

# One follow-up question per lab category, shown only when at least one
# value in that category was flagged abnormal. Deliberately generic and
# framed as something to ask a doctor, not an answer this tool provides
# itself.
FOLLOW_UP_QUESTIONS = {
    "cbc": "What could be causing this change in my blood counts, and do I need any follow-up tests?",
    "lipid": "Should I make any diet or lifestyle changes based on my cholesterol levels?",
    "liver": "Is there anything affecting my liver that I should be monitoring?",
    "kidney": "Do these kidney-related values need any follow-up, and should I stay extra hydrated?",
    "glucose": "What do these blood sugar results mean for my diabetes risk, and should I get tested again?",
    "thyroid": "Could my thyroid levels be affecting how I feel, and do I need further testing?",
    "infectious_screening": "What confirmatory testing or next steps are recommended after this screening result?",
    "vitals": "Should I be monitoring this at home, and could it be related to anything else going on?",
    "iron": "Could this be related to my diet, and would an iron supplement be appropriate for me?",
    "vitamins": "Should I consider a supplement for this, and what's a safe dose to discuss with my doctor?",
}

# A reactive/positive infectious-disease screening result is a different
# kind of finding from a mildly high cholesterol value — it carries real
# urgency (confirmatory testing, possible partner notification) even
# though a screening test alone still never confirms a diagnosis (every
# such test on the report itself says so). This gets its own, more direct
# paragraph rather than being folded into the generic "outside typical
# range" phrasing used for numeric values.
QUALITATIVE_ABNORMAL_NOTICE = (
    "Important: {tests} came back as a reactive/positive screening result. On its own, "
    "a screening test like this does not confirm a diagnosis — screening tests can have "
    "false positives, and confirmatory testing is the standard next step. Please contact "
    "your doctor or the testing lab promptly to discuss confirmatory testing."
)


def build_report_summary(classified_values: list[dict], qualitative_results: list[dict] = None) -> dict:
    qualitative_results = qualitative_results or []

    abnormal = [v for v in classified_values if v["status"] != "normal"]
    normal = [v for v in classified_values if v["status"] == "normal"]
    qual_abnormal = [q for q in qualitative_results if q["status"] == "abnormal"]
    qual_normal = [q for q in qualitative_results if q["status"] == "normal"]

    total_recognized = len(classified_values) + len(qualitative_results)
    total_abnormal = len(abnormal) + len(qual_abnormal)

    if total_recognized == 0:
        summary = (
            "We couldn't automatically recognize any of the lab parameters this tool "
            "currently supports in this report. This may be because the report uses an "
            "unfamiliar layout, or covers a panel this tool doesn't support yet — the "
            "original report is still the complete record."
        )
    elif total_abnormal == 0:
        summary = (
            f"All {len(normal) + len(qual_normal)} recognized value(s) in this report fall "
            "within typical reference ranges, and all recognized screening result(s) were "
            "non-reactive/negative."
        )
    else:
        details = [
            f"{v['label']} ({v['value']} {v['unit']}) is "
            f"{'above' if v['status'] == 'high' else 'below'} the typical range "
            f"({v['reference_low']}-{v['reference_high']} {v['unit']})"
            for v in abnormal
        ]
        details += [f"{q['label']} was reactive/positive" for q in qual_abnormal]
        summary = (
            f"{total_abnormal} of {total_recognized} recognized value(s) fall outside "
            "typical reference ranges or came back reactive/positive: " + "; ".join(details) + "."
        )

    if qual_abnormal:
        summary += " " + QUALITATIVE_ABNORMAL_NOTICE.format(
            tests=", ".join(q["label"] for q in qual_abnormal)
        )

    categories_flagged = sorted({v["category"] for v in abnormal} | {q["category"] for q in qual_abnormal})
    questions = [FOLLOW_UP_QUESTIONS[c] for c in categories_flagged if c in FOLLOW_UP_QUESTIONS]

    return {
        "summary": summary,
        "questions_to_ask": questions,
        "disclaimer": REPORT_ANALYSIS_DISCLAIMER,
    }
