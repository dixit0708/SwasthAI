"""
Rule-based extraction and reference-range classification of common lab
panel values from a lab report's extracted text.

Deliberately NOT an LLM: extraction is a fixed set of documented regexes
and classification is a lookup against a fixed reference-range table, so
output is fully deterministic and reproducible — no hallucination risk for
medical content (AGENTS.md Section 11). This trades recall (it will miss
values in unusual report layouts, and does not attempt unit conversion)
for the ability to state exactly what it can and cannot do.

Reference ranges below are general adult ranges consistent with common
clinical reference sources (e.g. Mayo Clinic Laboratories, MedlinePlus),
assuming the units listed. They are a general fallback, not a substitute
for the reference range printed on the user's own report, which reflects
that specific lab's instrumentation and population — see
docs/report_analyzer/README.md for the full source list and limitations.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LabParameter:
    key: str
    label: str
    category: str
    # Regex alternatives to look for on a line, tried in order; the first
    # number found after a match is taken as the reported value.
    aliases: tuple
    unit: str
    reference_low: float
    reference_high: float
    # Vitals (e.g. temperature) are sometimes OCR'd/printed with a
    # European-style comma decimal ("36,8 °C"). Off by default: a lab
    # value like a platelet count can legitimately use a comma as a
    # *thousands* separator ("150,000/µL"), where treating it as a decimal
    # would silently corrupt the value — so this is opt-in per parameter,
    # not a global behavior change.
    allow_comma_decimal: bool = False
    # WBC and platelet counts are near-universally printed by modern
    # hematology analyzers in "thousands" notation (e.g. "5.7 x10^3/uL" or
    # "5.7 10^9/L" — numerically identical scales) rather than the full
    # absolute count ("5700/uL"). This tool's canonical range for those two
    # parameters is in that same thousands scale (see LAB_PARAMETERS below)
    # to match what real reports actually print — but a report that DOES
    # print the raw absolute count needs to be scaled back down, or it
    # reads as wildly, obviously "High". `normalize_if_above` is that
    # safety net: if the raw extracted number exceeds this (implausible
    # for the thousands scale — even severe leukocytosis/thrombocytosis
    # tops out far below a typical absolute count), divide it by 1000
    # before classifying. None means never normalize.
    normalize_if_above: Optional[float] = None


LAB_PARAMETERS: tuple[LabParameter, ...] = (
    LabParameter("hemoglobin", "Hemoglobin", "cbc", (r"h(a)?emoglobin", r"\bhb\b"), "g/dL", 12.0, 17.5),
    LabParameter(
        "wbc", "White Blood Cell Count", "cbc",
        (r"wbc count", r"total le(u)?cocyte count", r"\bwbc\b", r"\btlc\b"), "×10³/µL", 4, 11,
        normalize_if_above=500,
    ),
    LabParameter(
        "platelet", "Platelet Count", "cbc", (r"platelet count", r"platelets?\b"), "×10³/µL", 150, 450,
        normalize_if_above=2000,
    ),
    LabParameter("rbc", "RBC Count", "cbc", (r"rbc count", r"\brbc\b"), "million/µL", 4.2, 5.9),
    LabParameter(
        "total_cholesterol", "Total Cholesterol", "lipid",
        (r"total cholesterol", r"cholesterol,?\s*total"), "mg/dL", 0, 200,
    ),
    LabParameter("ldl", "LDL Cholesterol", "lipid", (r"ldl cholesterol", r"\bldl\b"), "mg/dL", 0, 100),
    LabParameter("hdl", "HDL Cholesterol", "lipid", (r"hdl cholesterol", r"\bhdl\b"), "mg/dL", 40, 999),
    LabParameter("triglycerides", "Triglycerides", "lipid", (r"triglycerides",), "mg/dL", 0, 150),
    LabParameter("alt", "ALT (SGPT)", "liver", (r"alt\s*\(sgpt\)", r"\bsgpt\b", r"\balt\b"), "U/L", 7, 56),
    LabParameter("ast", "AST (SGOT)", "liver", (r"ast\s*\(sgot\)", r"\bsgot\b", r"\bast\b"), "U/L", 8, 48),
    LabParameter(
        "bilirubin_total", "Total Bilirubin", "liver",
        (r"total bilirubin", r"bilirubin,?\s*total"), "mg/dL", 0.1, 1.2,
    ),
    LabParameter("creatinine", "Creatinine", "kidney", (r"creatinine",), "mg/dL", 0.6, 1.3),
    LabParameter(
        "urea", "Blood Urea", "kidney",
        (r"blood urea nitrogen", r"\bbun\b", r"blood urea", r"\burea\b"), "mg/dL", 7, 20,
    ),
    LabParameter(
        "fasting_glucose", "Fasting Blood Glucose", "glucose",
        (r"fasting (blood )?glucose", r"fasting blood sugar", r"\bfbs\b"), "mg/dL", 70, 100,
    ),
    LabParameter(
        "hba1c", "HbA1c", "glucose",
        (r"hba1c", r"glycated h(a)?emoglobin"), "%", 4.0, 5.6,
    ),
    LabParameter("tsh", "TSH", "thyroid", (r"\btsh\b", r"thyroid stimulating hormone"), "mIU/L", 0.4, 4.0),
    # Total T3/T4 vs Free T3/T4 alias collision: "Free T3: 3.5 pg/mL" would
    # otherwise also match a bare "\bt3\b" alias, wrongly reporting the
    # same number twice under two different parameters with two different
    # (very different-scale) reference ranges. The negative lookbehind
    # `(?<!free )` on the total_* aliases excludes any "T3"/"T4" mention
    # immediately preceded by "free " — a fixed 5-character lookbehind,
    # which Python's `re` requires (no variable-width lookbehind).
    LabParameter(
        "t3_total", "T3 (Total)", "thyroid",
        (r"(?<!free )\btotal t3\b", r"(?<!free )\bt3\b", r"(?<!free )triiodothyronine"),
        "ng/dL", 80, 220,
    ),
    LabParameter(
        "t4_total", "T4 (Total)", "thyroid",
        (r"(?<!free )\btotal t4\b", r"(?<!free )\bt4\b", r"(?<!free )thyroxine"),
        "mcg/dL", 5.0, 12.0,
    ),
    LabParameter(
        "free_t3", "Free T3", "thyroid",
        (r"free\s*t3\b", r"free triiodothyronine"), "pg/mL", 2.3, 4.2,
    ),
    LabParameter(
        "free_t4", "Free T4", "thyroid",
        (r"free\s*t4\b", r"free thyroxine"), "ng/dL", 0.7, 1.9,
    ),
    LabParameter(
        "postprandial_glucose", "Post-Prandial Glucose (PP)", "glucose",
        (r"post[\s-]?prandial (blood )?glucose", r"\bpp\s*glucose\b", r"\b2\s*hr\s*pp\b"),
        "mg/dL", 70, 140,
    ),
    LabParameter(
        "random_glucose", "Random Blood Glucose", "glucose",
        (r"random (blood )?glucose", r"random blood sugar", r"\brbs\b"), "mg/dL", 70, 140,
    ),
    # CBC differential/indices — these round out the CBC panel already
    # covered by hemoglobin/WBC/platelet/RBC above. Percentages (not
    # absolute counts), matching the format most commonly printed on
    # Indian CBC reports.
    LabParameter(
        "hematocrit", "Hematocrit (PCV)", "cbc",
        (r"h(a)?ematocrit", r"\bpcv\b", r"packed cell volume"), "%", 36, 50,
    ),
    LabParameter("mcv", "MCV", "cbc", (r"\bmcv\b", r"mean corpuscular volume"), "fL", 80, 96),
    LabParameter("mch", "MCH", "cbc", (r"\bmch\b(?!c)", r"mean corpuscular h(a)?emoglobin\b(?! concentration)"), "pg", 27, 33),
    LabParameter(
        "mchc", "MCHC", "cbc",
        (r"\bmchc\b", r"mean corpuscular h(a)?emoglobin concentration"), "g/dL", 33, 36,
    ),
    LabParameter("rdw", "RDW", "cbc", (r"\brdw\b", r"red cell distribution width"), "%", 11.5, 14.5),
    LabParameter("esr", "ESR", "cbc", (r"\besr\b", r"erythrocyte sedimentation rate"), "mm/hr", 0, 20),
    LabParameter(
        "neutrophils_pct", "Neutrophils", "cbc",
        (r"neutrophils?\b",), "%", 40, 70,
    ),
    LabParameter(
        "lymphocytes_pct", "Lymphocytes", "cbc",
        (r"lymphocytes?\b",), "%", 20, 40,
    ),
    LabParameter("monocytes_pct", "Monocytes", "cbc", (r"monocytes?\b",), "%", 2, 8),
    LabParameter("eosinophils_pct", "Eosinophils", "cbc", (r"eosinophils?\b",), "%", 1, 6),
    LabParameter("basophils_pct", "Basophils", "cbc", (r"basophils?\b",), "%", 0, 2),
    # Liver panel (LFT) — rounds out ALT/AST/bilirubin already covered.
    LabParameter(
        "alp", "Alkaline Phosphatase (ALP)", "liver",
        (r"alkaline phosphatase", r"\balp\b"), "IU/L", 30, 120,
    ),
    LabParameter("ggt", "GGT", "liver", (r"\bggt\b", r"gamma[\s-]?glutamyl\s*transferase"), "IU/L", 0, 55),
    LabParameter(
        "total_protein", "Total Protein", "liver",
        (r"total protein",), "g/dL", 6.3, 8.0,
    ),
    LabParameter("albumin", "Albumin", "liver", (r"\balbumin\b",), "g/dL", 3.5, 5.0),
    LabParameter("globulin", "Globulin", "liver", (r"\bglobulin\b",), "g/dL", 2.0, 3.5),
    # Kidney panel (KFT) electrolytes/uric acid — rounds out
    # creatinine/urea already covered. Uric acid's clinically normal
    # range differs by sex (this tool has no sex input to key off); the
    # combined 2.4-7.0 band below is intentionally widened to the union of
    # both commonly-cited male/female ranges rather than picking one,
    # trading a little precision for not misclassifying a normal result
    # for either sex as abnormal.
    LabParameter("sodium", "Sodium", "kidney", (r"\bsodium\b", r"\bna\+?\b"), "mmol/L", 135, 145),
    LabParameter("potassium", "Potassium", "kidney", (r"\bpotassium\b", r"\bk\+\b"), "mmol/L", 3.5, 5.0),
    LabParameter("chloride", "Chloride", "kidney", (r"\bchloride\b",), "mmol/L", 96, 106),
    LabParameter("uric_acid", "Uric Acid", "kidney", (r"uric acid",), "mg/dL", 2.4, 7.0),
    # Iron studies — a distinct, common standalone panel ("iron
    # deficiency workup"). Ferritin's combined range is likewise widened
    # across commonly-cited male/female bands for the same reason as uric
    # acid above.
    LabParameter("serum_iron", "Serum Iron", "iron", (r"serum iron", r"\biron\b(?!.{0,15}binding)"), "µg/dL", 50, 175),
    LabParameter("ferritin", "Ferritin", "iron", (r"\bferritin\b",), "ng/mL", 20, 250),
    LabParameter(
        "tibc", "Total Iron-Binding Capacity (TIBC)", "iron",
        (r"total iron.binding capacity", r"\btibc\b"), "µg/dL", 250, 370,
    ),
    LabParameter(
        "transferrin_saturation", "Transferrin Saturation", "iron",
        (r"transferrin saturation", r"%\s*saturation", r"\btsat\b"), "%", 20, 50,
    ),
    # Vitamins — commonly ordered standalone, especially in India
    # (vitamin D and B12 deficiency are both widely screened for).
    LabParameter(
        "vitamin_d", "Vitamin D (25-OH)", "vitamins",
        (r"25[\s-]?\(?oh\)?[\s-]?vitamin\s*d", r"vitamin\s*d\d*\b"), "ng/mL", 30, 100,
    ),
    LabParameter(
        "vitamin_b12", "Vitamin B12", "vitamins",
        (r"vitamin\s*b[\s-]?12", r"\bcobalamin\b"), "pg/mL", 200, 900,
    ),
    # Vitals: from a general check-up/vitals report rather than a lab
    # panel — a different, common document type this tool didn't cover
    # before (see docs/report_analyzer/README.md).
    LabParameter(
        "pulse", "Pulse / Heart Rate", "vitals",
        (r"\bpulse\b", r"heart rate"), "bpm", 60, 100,
    ),
    LabParameter(
        "respiratory_rate", "Respiratory Rate", "vitals",
        (r"respiratory\s*r(?:ate|t)\b", r"resp\.?\s*rate"), "breaths/min", 12, 20,
    ),
    LabParameter(
        "body_temperature", "Body Temperature", "vitals",
        (r"\btemperature\b", r"\btemp\b"), "°C", 36.1, 37.2,
        allow_comma_decimal=True,
    ),
)

# Plain-English "what does this measure" description shown for every
# recognized value, regardless of status. This is the actual "make the
# report easier to read" piece of the tool — the numbers and ranges alone
# are just an echo of what the original report already prints; a reader
# still has no idea what "MCHC" or "GGT" even means. Kept in a separate
# lookup (rather than a LabParameter field) so it can be added without
# touching the extraction/classification logic above. Deliberately
# factual and generic — what the test measures in general, never what a
# specific result means for the person who uploaded it (that reasoning
# still only comes from the LLM explanation step, never from this static
# table) — so it's safe to show unconditionally for every value.
PARAMETER_DESCRIPTIONS: dict[str, str] = {
    "hemoglobin": "The protein in red blood cells that carries oxygen around your body.",
    "wbc": "Total white blood cells — your body's infection-fighting cells.",
    "platelet": "Cell fragments in blood that help it clot.",
    "rbc": "The number of oxygen-carrying red blood cells in your blood.",
    "total_cholesterol": "The total amount of cholesterol (a fat-like substance) in your blood.",
    "ldl": "Often called “bad” cholesterol — can build up in artery walls over time.",
    "hdl": "Often called “good” cholesterol — helps clear excess cholesterol from your blood.",
    "triglycerides": "A type of fat in your blood, often related to diet and metabolism.",
    "alt": "A liver enzyme; elevated levels can indicate liver cell stress.",
    "ast": "A liver enzyme also found in muscle and heart tissue.",
    "bilirubin_total": "A byproduct of red blood cell breakdown, processed by the liver.",
    "creatinine": "A waste product filtered by the kidneys — a key marker of kidney function.",
    "urea": "A waste product from protein breakdown, filtered by the kidneys.",
    "fasting_glucose": "Blood sugar measured after not eating for at least 8 hours.",
    "hba1c": "Your average blood sugar level over the past 2-3 months.",
    "tsh": "A pituitary hormone that tells your thyroid how much hormone to produce.",
    "t3_total": "An active thyroid hormone that helps regulate metabolism.",
    "t4_total": "The main hormone produced by the thyroid gland.",
    "free_t3": "The unbound, active form of T3 available for your body to use.",
    "free_t4": "The unbound, active form of T4 available for your body to use.",
    "postprandial_glucose": "Blood sugar measured about 2 hours after eating.",
    "random_glucose": "Blood sugar measured at any time, regardless of meals.",
    "hematocrit": "The percentage of your blood made up of red blood cells.",
    "mcv": "The average size of your red blood cells.",
    "mch": "The average amount of hemoglobin inside each red blood cell.",
    "mchc": "How concentrated the hemoglobin is inside your red blood cells.",
    "rdw": "How much your red blood cells vary in size.",
    "esr": "How quickly red blood cells settle in a test tube — a general marker of inflammation.",
    "neutrophils_pct": "The most common white blood cell, usually first to respond to infection.",
    "lymphocytes_pct": "White blood cells that fight viruses and help produce antibodies.",
    "monocytes_pct": "White blood cells that clean up infections and dead cells.",
    "eosinophils_pct": "White blood cells involved in allergic reactions and parasite defense.",
    "basophils_pct": "The least common white blood cell, involved in allergic/inflammatory responses.",
    "alp": "An enzyme found in the liver, bones, and bile ducts.",
    "ggt": "A liver enzyme sensitive to bile duct issues and alcohol use.",
    "total_protein": "The combined amount of albumin and globulin proteins in your blood.",
    "albumin": "A protein made by the liver that helps maintain fluid balance.",
    "globulin": "A group of proteins involved in immune function and blood clotting.",
    "sodium": "An electrolyte that helps regulate fluid balance and nerve/muscle function.",
    "potassium": "An electrolyte important for heart rhythm and muscle function.",
    "chloride": "An electrolyte that helps maintain fluid and acid-base balance.",
    "uric_acid": "A waste product from the breakdown of purines in food and cells.",
    "serum_iron": "The amount of iron currently circulating in your blood.",
    "ferritin": "A protein that stores iron — reflects your body's iron reserves.",
    "tibc": "A measure of how much iron your blood could carry if fully saturated.",
    "transferrin_saturation": "The percentage of your iron-carrying protein that's currently loaded with iron.",
    "vitamin_d": "Supports bone health and immune function; often low with limited sun exposure.",
    "vitamin_b12": "Supports nerve function and red blood cell production.",
    "pulse": "Your heart rate — how many times your heart beats per minute.",
    "respiratory_rate": "How many breaths you take per minute.",
    "body_temperature": "Your core body temperature.",
    "systolic_bp": "The pressure in your arteries when your heart beats.",
    "diastolic_bp": "The pressure in your arteries when your heart rests between beats.",
}

QUALITATIVE_DESCRIPTIONS: dict[str, str] = {
    "hiv_screening": "Checks for antibodies your body produces in response to HIV infection.",
    "hbsag_screening": "Checks for a protein on the surface of the Hepatitis B virus.",
    "syphilis_screening": "Checks for antibodies associated with syphilis infection.",
    "hepatitis_c_screening": "Checks for antibodies your body produces in response to Hepatitis C infection.",
    "dengue_ns1": "Detects a dengue virus protein present early in infection.",
    "dengue_igm": "Checks for antibodies indicating a recent or current dengue infection.",
    "malaria_antigen": "Checks for proteins from the malaria parasite in your blood.",
    "covid_19": "Checks for the virus that causes COVID-19.",
    "typhidot_igg": "Checks for longer-term antibodies associated with typhoid (Salmonella typhi) infection.",
    "typhidot_igm": "Checks for antibodies indicating a recent or current typhoid infection.",
}

_VALUE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")
_VALUE_PATTERN_COMMA_OK = re.compile(r"(\d+(?:[.,]\d+)?)")

# Blood pressure is a compound systolic/diastolic reading (e.g.
# "140/90 mmHg") — it doesn't fit LabParameter's one-value-per-parameter
# shape, so it gets its own small extractor, producing two ordinary
# LabValue-shaped entries (systolic + diastolic) that flow through the
# rest of the pipeline like any other recognized value. General adult
# "normal" bands per AHA — see docs/report_analyzer/README.md.
_BP_ALIAS = re.compile(r"blood pressure", re.IGNORECASE)
_BP_VALUE_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")


def extract_lab_values(text: str) -> list[dict]:
    """Scans extracted report text line by line. Each parameter is matched
    at most once (the first line where one of its aliases is found), so a
    reference-range line repeating the parameter's name later doesn't
    overwrite an already-found value.
    """
    results = []
    matched_keys = set()

    for line in text.splitlines():
        line_lower = line.lower()
        for param in LAB_PARAMETERS:
            if param.key in matched_keys:
                continue

            match = _find_alias_match(param, line_lower)
            if match is None:
                continue

            value = _extract_value_after(line, match.end(), param.allow_comma_decimal)
            if value is None:
                continue

            if param.normalize_if_above is not None and value > param.normalize_if_above:
                value = value / 1000

            results.append({
                "key": param.key,
                "label": param.label,
                "category": param.category,
                "description": PARAMETER_DESCRIPTIONS.get(param.key, ""),
                "value": value,
                "unit": param.unit,
                "reference_low": param.reference_low,
                "reference_high": param.reference_high,
            })
            matched_keys.add(param.key)

    results.extend(_extract_blood_pressure(text))
    return results


def _extract_blood_pressure(text: str) -> list[dict]:
    alias_match = _BP_ALIAS.search(text)
    if alias_match is None:
        return []

    line_end = text.find("\n", alias_match.end())
    if line_end == -1:
        line_end = len(text)

    value_match = _BP_VALUE_PATTERN.search(text, alias_match.end(), line_end)
    if value_match is None:
        # e.g. a malformed/incomplete "140/mmHg" reading missing the
        # diastolic number — don't guess, just don't recognize it.
        return []

    systolic, diastolic = float(value_match.group(1)), float(value_match.group(2))
    return [
        {
            "key": "systolic_bp", "label": "Systolic Blood Pressure", "category": "vitals",
            "description": PARAMETER_DESCRIPTIONS["systolic_bp"],
            "value": systolic, "unit": "mmHg", "reference_low": 90, "reference_high": 120,
        },
        {
            "key": "diastolic_bp", "label": "Diastolic Blood Pressure", "category": "vitals",
            "description": PARAMETER_DESCRIPTIONS["diastolic_bp"],
            "value": diastolic, "unit": "mmHg", "reference_low": 60, "reference_high": 80,
        },
    ]


def _find_alias_match(param: LabParameter, line_lower: str) -> Optional[re.Match]:
    for alias in param.aliases:
        match = re.search(alias, line_lower)
        if match:
            return match
    return None


def _extract_value_after(line: str, offset: int, allow_comma_decimal: bool = False) -> Optional[float]:
    pattern = _VALUE_PATTERN_COMMA_OK if allow_comma_decimal else _VALUE_PATTERN
    value_match = pattern.search(line, offset)
    if not value_match:
        return None
    try:
        return float(value_match.group(1).replace(",", "."))
    except ValueError:
        return None


def classify_lab_values(values: list[dict]) -> list[dict]:
    classified = []
    for v in values:
        if v["value"] < v["reference_low"]:
            status = "low"
        elif v["value"] > v["reference_high"]:
            status = "high"
        else:
            status = "normal"
        classified.append({**v, "status": status})
    return classified


@dataclass(frozen=True)
class QualitativeTest:
    key: str
    label: str
    category: str
    aliases: tuple
    # Tokens for a screening-negative vs screening-positive result. Both
    # lists are searched in the same window; whichever token occurs
    # earliest in the text wins — this correctly handles "Reactive" being
    # a substring that also appears inside "Non-Reactive" (word-boundary
    # regex matches both; position, not pattern order, decides).
    normal_tokens: tuple
    abnormal_tokens: tuple


# Common infectious-disease screening panel tests (e.g. the "Safe Sex" /
# pre-marital / routine screening bundles Indian diagnostic labs commonly
# report as Reactive/Non-Reactive or Positive/Negative rather than a
# number). Added after testing against a real Dr Lal PathLabs report that
# was entirely this test type — see docs/report_analyzer/README.md.
QUALITATIVE_TESTS: tuple[QualitativeTest, ...] = (
    QualitativeTest(
        "hiv_screening", "HIV Screening (Antibody)", "infectious_screening",
        (r"hiv rapid screening", r"hiv\b.{0,20}screening test", r"hiv[\s-]?1/2"),
        normal_tokens=(r"non[\s-]?reactive", r"\bnegative\b", r"not detected"),
        abnormal_tokens=(r"\breactive\b", r"\bpositive\b", r"\bdetected\b"),
    ),
    QualitativeTest(
        "hbsag_screening", "Hepatitis B Surface Antigen (HBsAg)", "infectious_screening",
        (r"hepatitis b surface antigen", r"\bhbsag\b"),
        normal_tokens=(r"non[\s-]?reactive", r"\bnegative\b"),
        abnormal_tokens=(r"\breactive\b", r"\bpositive\b"),
    ),
    QualitativeTest(
        "syphilis_screening", "Syphilis Screening (RPR/VDRL)", "infectious_screening",
        (r"rpr\s*\(rapid plasma reagin\)", r"\brpr\b", r"\bvdrl\b"),
        normal_tokens=(r"non[\s-]?reactive", r"\bnegative\b"),
        abnormal_tokens=(r"\breactive\b", r"\bpositive\b"),
    ),
    QualitativeTest(
        "hepatitis_c_screening", "Hepatitis C Virus Antibody", "infectious_screening",
        (r"hepatitis c virus antibod", r"anti[\s-]?hcv", r"\bhcv\b.{0,20}antibod"),
        normal_tokens=(r"non[\s-]?reactive", r"\bnegative\b"),
        abnormal_tokens=(r"\breactive\b", r"\bpositive\b"),
    ),
    # Dengue NS1/IgM specifically (not IgG): both indicate a current or
    # recent infection, same as the tests above. Dengue IgG is
    # deliberately NOT included — on its own it commonly just means a
    # *past* infection (long-term immunity), a materially different and
    # far less urgent finding than "reactive" on every other test in this
    # table, and QUALITATIVE_ABNORMAL_NOTICE's "contact your doctor
    # promptly" framing below would misrepresent that. See docs/
    # report_analyzer/README.md for this and the other qualitative gaps
    # (Widal/typhoid is titer-based, not Reactive/Non-Reactive, and isn't
    # handled by this framework at all yet).
    QualitativeTest(
        "dengue_ns1", "Dengue NS1 Antigen", "infectious_screening",
        (r"dengue ns1 antigen", r"\bns1\b.{0,20}antigen"),
        normal_tokens=(r"non[\s-]?reactive", r"\bnegative\b"),
        abnormal_tokens=(r"\breactive\b", r"\bpositive\b"),
    ),
    QualitativeTest(
        "dengue_igm", "Dengue IgM Antibody", "infectious_screening",
        (r"dengue igm antibod", r"dengue\b.{0,20}igm\b"),
        normal_tokens=(r"non[\s-]?reactive", r"\bnegative\b"),
        abnormal_tokens=(r"\breactive\b", r"\bpositive\b"),
    ),
    QualitativeTest(
        "malaria_antigen", "Malaria Antigen", "infectious_screening",
        (r"malaria antigen", r"malaria parasite.{0,20}(rapid|antigen)"),
        normal_tokens=(r"\bnegative\b", r"non[\s-]?reactive"),
        abnormal_tokens=(r"\bpositive\b", r"\breactive\b"),
    ),
    QualitativeTest(
        "covid_19", "COVID-19 (SARS-CoV-2)", "infectious_screening",
        (r"covid[\s-]?19", r"sars[\s-]?cov[\s-]?2"),
        normal_tokens=(r"\bnegative\b", r"non[\s-]?reactive", r"not detected"),
        abnormal_tokens=(r"\bpositive\b", r"\breactive\b", r"\bdetected\b"),
    ),
    # Typhidot — a qualitative rapid-card IgG/IgM test for typhoid
    # (Salmonella typhi), reported as Negative/Positive. Distinct from the
    # classic Widal test, which reports a titer ("1:160") rather than a
    # plain result and still isn't handled by this qualitative framework —
    # see docs/report_analyzer/README.md. Added after a real Redcliffe
    # Labs report used this exact test.
    QualitativeTest(
        "typhidot_igg", "Typhoid IgG (Typhidot)", "infectious_screening",
        (r"typhi\s*dot.{0,40}igg", r"salmonella typhi igg"),
        normal_tokens=(r"\bnegative\b", r"non[\s-]?reactive"),
        abnormal_tokens=(r"\bpositive\b", r"\breactive\b"),
    ),
    QualitativeTest(
        "typhidot_igm", "Typhoid IgM (Typhidot)", "infectious_screening",
        (r"typhi\s*dot.{0,40}igm", r"salmonella typhi igm"),
        normal_tokens=(r"\bnegative\b", r"non[\s-]?reactive"),
        abnormal_tokens=(r"\bpositive\b", r"\breactive\b"),
    ),
)

# How far past a test-name match to look for its result, cut short at the
# report's own "Interpretation"/legend section so a later, unrelated
# legend row (e.g. "| Reactive | Indicates presence of...") is never
# mistaken for the patient's own result.
_QUALITATIVE_WINDOW_CHARS = 400
_INTERPRETATION_BOUNDARY = re.compile(r"\binterpretation\b", re.IGNORECASE)


def extract_qualitative_results(text: str) -> list[dict]:
    results = []
    matched_keys = set()

    for test in QUALITATIVE_TESTS:
        if test.key in matched_keys:
            continue

        alias_match = _find_first_alias(test.aliases, text)
        if alias_match is None:
            continue

        window_end = min(alias_match.end() + _QUALITATIVE_WINDOW_CHARS, len(text))
        boundary_match = _INTERPRETATION_BOUNDARY.search(text, alias_match.end(), window_end)
        if boundary_match:
            window_end = boundary_match.start()
        window_text = text[alias_match.end():window_end]

        status = _classify_qualitative_window(test, window_text)
        if status is None:
            continue

        results.append({
            "key": test.key,
            "label": test.label,
            "category": test.category,
            "description": QUALITATIVE_DESCRIPTIONS.get(test.key, ""),
            "status": status,
        })
        matched_keys.add(test.key)

    return results


def _find_first_alias(aliases: tuple, text: str) -> Optional[re.Match]:
    earliest = None
    for alias in aliases:
        match = re.search(alias, text, re.IGNORECASE)
        if match and (earliest is None or match.start() < earliest.start()):
            earliest = match
    return earliest


def _earliest_match_start(patterns: tuple, text: str) -> Optional[int]:
    positions = [m.start() for m in (re.search(p, text, re.IGNORECASE) for p in patterns) if m]
    return min(positions) if positions else None


def _classify_qualitative_window(test: QualitativeTest, window_text: str) -> Optional[str]:
    normal_pos = _earliest_match_start(test.normal_tokens, window_text)
    abnormal_pos = _earliest_match_start(test.abnormal_tokens, window_text)
    if normal_pos is None and abnormal_pos is None:
        return None
    if abnormal_pos is None:
        return "normal"
    if normal_pos is None:
        return "abnormal"
    return "normal" if normal_pos <= abnormal_pos else "abnormal"
