from unittest.mock import MagicMock, patch

from app.ai.inference.lab_report_analysis import (
    LAB_PARAMETERS, PARAMETER_DESCRIPTIONS, QUALITATIVE_DESCRIPTIONS, QUALITATIVE_TESTS,
    classify_lab_values, extract_lab_values, extract_qualitative_results,
)
from app.ai.inference.image_ocr import extract_text_from_image
from app.ai.inference.report_explanation import generate_plain_language_explanation
from app.ai.inference.report_parsing import validate_and_extract_text
from app.ai.safety.report_safety import build_report_summary
from app.core.config import settings


def _build_minimal_pdf(lines: list[str]) -> bytes:
    """Hand-rolled minimal single-page PDF (no external PDF-writer
    dependency) with one line of text per Td/Tj — just enough structure
    for pdfplumber/pdfminer.six to parse selectable text back out.
    """
    content_lines = []
    y = 750
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content_lines.append(f"BT /F1 10 Tf 40 {y} Td ({escaped}) Tj ET")
        y -= 14
    content_stream = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream + b"\nendstream",
    ]

    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(body)
    xref_lines = [b"xref", f"0 {len(objects) + 1}".encode(), b"0000000000 65535 f "]
    for off in offsets[1:]:
        xref_lines.append(f"{off:010d} 00000 n ".encode())
    body += b"\n".join(xref_lines) + b"\n"
    body += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF"
    )
    return bytes(body)


# --- validate_and_extract_text ---

def test_extract_text_rejects_unsupported_content_type():
    try:
        validate_and_extract_text(b"some content", "text/plain")
        assert False, "Should have rejected an unsupported content type"
    except ValueError as e:
        assert "Unsupported file type" in str(e)


def test_extract_text_dispatches_images_to_ocr():
    with patch(
        "app.ai.inference.report_parsing.extract_text_from_image",
        return_value="Hemoglobin 10.5 g/dL",
    ) as mock_ocr:
        text = validate_and_extract_text(b"fake-image-bytes", "image/png")
    assert text == "Hemoglobin 10.5 g/dL"
    mock_ocr.assert_called_once_with(b"fake-image-bytes", "image/png")


def test_extract_text_rejects_empty_file():
    try:
        validate_and_extract_text(b"", "application/pdf")
        assert False, "Should have rejected empty contents"
    except ValueError as e:
        assert "empty" in str(e)


def test_extract_text_rejects_oversized_file():
    oversized = b"%PDF-1.4\n" + b"0" * (15 * 1024 * 1024 + 1)
    try:
        validate_and_extract_text(oversized, "application/pdf")
        assert False, "Should have rejected an oversized file"
    except ValueError as e:
        assert "too large" in str(e)


def test_extract_text_rejects_corrupted_pdf():
    try:
        validate_and_extract_text(b"%PDF-1.4\nnot actually a valid pdf structure", "application/pdf")
        assert False, "Should have rejected a corrupted PDF"
    except ValueError as e:
        assert "Could not read this PDF" in str(e)


def test_extract_text_happy_path():
    pdf_bytes = _build_minimal_pdf(["Hemoglobin  10.5  g/dL  (12.0-17.5)"])
    text = validate_and_extract_text(pdf_bytes, "application/pdf")
    assert "Hemoglobin" in text
    assert "10.5" in text


def test_extract_text_falls_back_to_ocr_for_scanned_pdf_with_no_text_layer():
    pdf_bytes = _build_minimal_pdf([])  # valid PDF, zero lines of text -> no text layer
    with patch(
        "app.ai.inference.report_parsing.extract_text_from_image",
        return_value="Hemoglobin 10.5 g/dL",
    ) as mock_ocr:
        text = validate_and_extract_text(pdf_bytes, "application/pdf")
    assert text == "Hemoglobin 10.5 g/dL"
    mock_ocr.assert_called_once()


def test_extract_text_scanned_pdf_without_gemini_key_raises_clear_error():
    pdf_bytes = _build_minimal_pdf([])
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = ""
    try:
        try:
            validate_and_extract_text(pdf_bytes, "application/pdf")
            assert False, "Should have raised when OCR isn't configured"
        except ValueError as e:
            assert "scanned document isn't available" in str(e)
    finally:
        settings.GEMINI_API_KEY = original


# --- extract_text_from_image (Gemini vision OCR — mocked, no real network calls) ---

def test_ocr_rejects_unsupported_content_type():
    try:
        extract_text_from_image(b"bytes", "application/pdf")
        assert False, "Should have rejected a non-image content type"
    except ValueError as e:
        assert "Unsupported file type" in str(e)


def test_ocr_rejects_empty_file():
    try:
        extract_text_from_image(b"", "image/png")
        assert False, "Should have rejected empty contents"
    except ValueError as e:
        assert "empty" in str(e)


def test_ocr_rejects_oversized_file():
    oversized = b"0" * (15 * 1024 * 1024 + 1)
    try:
        extract_text_from_image(oversized, "image/png")
        assert False, "Should have rejected an oversized file"
    except ValueError as e:
        assert "too large" in str(e)


def test_ocr_raises_when_no_api_key_configured():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = ""
    try:
        try:
            extract_text_from_image(b"fake-bytes", "image/png")
            assert False, "Should have raised when no API key is configured"
        except ValueError as e:
            assert "isn't available right now" in str(e)
    finally:
        settings.GEMINI_API_KEY = original


def test_ocr_returns_transcribed_text_on_success():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-key"
    try:
        mock_response = MagicMock(text="Hemoglobin  10.5  g/dL")
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        with patch("google.genai.Client", return_value=mock_client):
            text = extract_text_from_image(b"fake-image-bytes", "image/png")
        assert text == "Hemoglobin  10.5  g/dL"
    finally:
        settings.GEMINI_API_KEY = original


def test_ocr_raises_on_api_failure():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-key"
    try:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("network error")
        with patch("google.genai.Client", return_value=mock_client):
            try:
                extract_text_from_image(b"fake-image-bytes", "image/png")
                assert False, "Should have raised on API failure"
            except ValueError as e:
                assert "Couldn't read text from this image" in str(e)
    finally:
        settings.GEMINI_API_KEY = original


def test_ocr_raises_on_empty_transcription():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-key"
    try:
        mock_response = MagicMock(text="")
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        with patch("google.genai.Client", return_value=mock_client):
            try:
                extract_text_from_image(b"fake-image-bytes", "image/png")
                assert False, "Should have raised when no text was transcribed"
            except ValueError as e:
                assert "No text could be read" in str(e)
    finally:
        settings.GEMINI_API_KEY = original


# --- PARAMETER_DESCRIPTIONS / QUALITATIVE_DESCRIPTIONS completeness ---
# A parameter silently missing its plain-language description wouldn't
# fail any extraction test (extraction would still find the right number
# and status) — it would just quietly ship a blank instead of the one
# thing this feature is actually supposed to add. Checked exhaustively
# against the real tables here, not just the handful of keys the other
# tests happen to exercise.

def test_every_lab_parameter_has_a_description():
    missing = [p.key for p in LAB_PARAMETERS if not PARAMETER_DESCRIPTIONS.get(p.key)]
    assert missing == []


def test_blood_pressure_keys_have_descriptions():
    assert PARAMETER_DESCRIPTIONS.get("systolic_bp")
    assert PARAMETER_DESCRIPTIONS.get("diastolic_bp")


def test_every_qualitative_test_has_a_description():
    missing = [t.key for t in QUALITATIVE_TESTS if not QUALITATIVE_DESCRIPTIONS.get(t.key)]
    assert missing == []


# --- extract_lab_values / classify_lab_values ---

def test_extract_and_classify_mixed_values():
    text = (
        "Complete Blood Count\n"
        "Hemoglobin   10.5   g/dL   (12.0-17.5)\n"
        "Total Cholesterol   220   mg/dL   (<200)\n"
        "TSH   2.1   mIU/L   (0.4-4.0)\n"
    )
    raw = extract_lab_values(text)
    keys = {v["key"] for v in raw}
    assert keys == {"hemoglobin", "total_cholesterol", "tsh"}

    classified = classify_lab_values(raw)
    by_key = {v["key"]: v for v in classified}
    assert by_key["hemoglobin"]["status"] == "low"

    # The plain-English "what this measures" line is the actual
    # jargon-translation value-add of this tool over just reading the raw
    # report — regression guard that it's actually populated, not silently
    # dropped, and not gated on abnormal status (shown for every value).
    for v in classified:
        assert v["description"], f"{v['key']} is missing its plain-language description"
    assert by_key["total_cholesterol"]["status"] == "high"
    assert by_key["tsh"]["status"] == "normal"


def test_extract_ignores_unrecognized_lines():
    text = "Patient Name: John Doe\nDate of Birth: 1990-01-01\n"
    assert extract_lab_values(text) == []


def test_extract_does_not_double_match_ast_inside_other_words():
    # "breakfast" contains the substring "ast" but must not be picked up as
    # an AST lab value.
    text = "Fasting sample collected after breakfast at 8 AM.\n"
    raw = extract_lab_values(text)
    assert not any(v["key"] == "ast" for v in raw)


def test_extract_matches_each_parameter_only_once():
    text = "Hemoglobin  9.0  g/dL\nHemoglobin (repeat)  9.2  g/dL\n"
    raw = extract_lab_values(text)
    assert len([v for v in raw if v["key"] == "hemoglobin"]) == 1
    assert raw[0]["value"] == 9.0


# --- WBC/platelet "thousands" scale (real bug: a report reading TLC as
# "5.7 10^3/uL" was compared directly against a reference range meant for
# the full absolute count, misclassifying a genuinely normal 5,700/uL WBC
# count as "Low" against 4000-11000) ---

def test_wbc_thousands_notation_classifies_correctly():
    # This is the exact real-world case that surfaced the bug: a report
    # prints "5.7" with a "x10^3/uL" unit alongside it (the near-universal
    # modern hematology-analyzer convention). The canonical range is now
    # in that same scale, so no conversion is needed — 5.7 is genuinely
    # within 4-11.
    text = "TLC   5.7   10^3/uL   4 - 10\n"
    raw = extract_lab_values(text)
    wbc = next(v for v in raw if v["key"] == "wbc")
    assert wbc["value"] == 5.7
    assert classify_lab_values([wbc])[0]["status"] == "normal"


def test_wbc_raw_absolute_count_gets_normalized_down():
    # A report that instead prints the full absolute count ("5700/uL", no
    # thousands notation) must be scaled down to match the canonical
    # thousands-scale range, or it reads as wildly, obviously "High".
    text = "WBC Count   5700   /uL   4000 - 11000\n"
    raw = extract_lab_values(text)
    wbc = next(v for v in raw if v["key"] == "wbc")
    assert wbc["value"] == 5.7
    assert classify_lab_values([wbc])[0]["status"] == "normal"


def test_platelet_thousands_notation_classifies_correctly():
    # Also the real case: 147 (x10^3/uL) is genuinely just below the
    # 150-450 canonical range — correctly "low", not the wildly wrong
    # "147 platelets total" the old raw-count-scale range would have
    # implied.
    text = "Platelet Count   147   10^3/uL   150 - 410\n"
    raw = extract_lab_values(text)
    platelet = next(v for v in raw if v["key"] == "platelet")
    assert platelet["value"] == 147.0
    assert classify_lab_values([platelet])[0]["status"] == "low"


def test_platelet_raw_absolute_count_gets_normalized_down():
    text = "Platelet Count   147000   /uL   150000 - 410000\n"
    raw = extract_lab_values(text)
    platelet = next(v for v in raw if v["key"] == "platelet")
    assert platelet["value"] == 147.0
    assert classify_lab_values([platelet])[0]["status"] == "low"


def test_wbc_high_value_within_thousands_scale_not_over_normalized():
    # A plausible but elevated thousands-scale reading (e.g. 15 x10^3/uL,
    # a real leukocytosis case) must NOT get divided by 1000 just because
    # it's above the reference range — normalize_if_above's threshold (500
    # for WBC) is far above any plausible thousands-scale value, precisely
    # so this doesn't happen.
    text = "TLC   15.2   10^3/uL   4 - 10\n"
    raw = extract_lab_values(text)
    wbc = next(v for v in raw if v["key"] == "wbc")
    assert wbc["value"] == 15.2
    assert classify_lab_values([wbc])[0]["status"] == "high"


# --- vitals (general check-up reports, not just lab panels) ---

def test_extract_vitals_pulse_and_respiratory_rate():
    text = "VITALS\nPulse: 76 bpm\nRespiratory rt: 16/min\n"
    raw = extract_lab_values(text)
    by_key = {v["key"]: v for v in raw}
    assert by_key["pulse"]["value"] == 76.0
    assert by_key["respiratory_rate"]["value"] == 16.0


def test_extract_temperature_handles_comma_decimal():
    # Real-world OCR/European formatting: "36,8" instead of "36.8".
    text = "Temperature 36,8 C\n"
    raw = extract_lab_values(text)
    assert len(raw) == 1
    assert raw[0]["key"] == "body_temperature"
    assert raw[0]["value"] == 36.8


def test_extract_temperature_still_handles_period_decimal():
    text = "Temperature 38.5 C\n"
    raw = extract_lab_values(text)
    assert raw[0]["value"] == 38.5


def test_extract_blood_pressure_systolic_and_diastolic():
    text = "Blood pressure 140/90 mmHg\n"
    raw = extract_lab_values(text)
    classified = classify_lab_values(raw)
    by_key = {v["key"]: v for v in classified}
    assert by_key["systolic_bp"]["value"] == 140.0
    assert by_key["systolic_bp"]["status"] == "high"
    assert by_key["diastolic_bp"]["value"] == 90.0
    assert by_key["diastolic_bp"]["status"] == "high"


def test_extract_blood_pressure_normal():
    text = "Blood pressure 110/70 mmHg\n"
    classified = classify_lab_values(extract_lab_values(text))
    by_key = {v["key"]: v for v in classified}
    assert by_key["systolic_bp"]["status"] == "normal"
    assert by_key["diastolic_bp"]["status"] == "normal"


def test_extract_blood_pressure_skips_malformed_reading_without_diastolic():
    # Real case found via testing: a source report missing the diastolic
    # number entirely ("140/mmHg") — must not guess a value, just skip it.
    text = "Blood pressure 140/mmHg\n"
    raw = extract_lab_values(text)
    assert not any(v["key"] in ("systolic_bp", "diastolic_bp") for v in raw)


def test_platelet_count_thousands_comma_not_misread_as_decimal():
    # Regression guard for allow_comma_decimal being opt-in (default
    # False): a platelet count with a thousands-separator comma must keep
    # its existing (already-documented, pre-existing) truncate-at-comma
    # behavior — value stops at "152" — rather than the new comma-decimal
    # parameter's "175" would give "17,5" -> 17.5 for a value like this.
    # If comma-decimal ever leaked into this parameter, "152,500" would
    # instead misparse as 152.5, which this asserts against.
    text = "Platelet Count 152,500 /uL\n"
    raw = extract_lab_values(text)
    platelet = next(v for v in raw if v["key"] == "platelet")
    assert platelet["value"] == 152.0


# --- extended panel coverage (CBC differential/indices, LFT, KFT, thyroid,
# glucose variants, iron studies, vitamins) — added after researching
# standard panel terminology/ranges (see docs/report_analyzer/README.md
# for sources), to grow real-world coverage without waiting for each gap
# to surface one report at a time. ---

def test_extract_total_t3_t4_do_not_collide_with_free_t3_t4():
    # The core collision risk: "Free T3" contains the substring "T3", and
    # a naive `\bt3\b` alias would double-count the same number under both
    # "T3 (Total)" (range 80-220) and "Free T3" (range 2.3-4.2) — very
    # different scales, so a collision here isn't just a duplicate, it's a
    # wrong "critically low total T3" reading that was never reported.
    text = "Free T3   3.5   pg/mL\nFree T4   1.2   ng/dL\nT3 (Total)   150   ng/dL\nT4 (Total)   8.0   mcg/dL\n"
    raw = extract_lab_values(text)
    by_key = {v["key"]: v["value"] for v in raw}
    assert by_key == {"free_t3": 3.5, "free_t4": 1.2, "t3_total": 150.0, "t4_total": 8.0}


def test_extract_mch_does_not_collide_with_mchc():
    text = "MCH   29   pg\nMCHC   34   g/dL\nMCV   88   fL\n"
    raw = extract_lab_values(text)
    by_key = {v["key"]: v["value"] for v in raw}
    assert by_key == {"mch": 29.0, "mchc": 34.0, "mcv": 88.0}


def test_extract_serum_iron_does_not_collide_with_tibc():
    text = "Total Iron Binding Capacity   300   ug/dL\nSerum Iron   80   ug/dL\n"
    raw = extract_lab_values(text)
    by_key = {v["key"]: v["value"] for v in raw}
    assert by_key == {"tibc": 300.0, "serum_iron": 80.0}


def test_extract_cbc_differential_and_indices():
    text = (
        "Hematocrit   42   %\n"
        "RDW   13   %\n"
        "ESR   15   mm/hr\n"
        "Neutrophils   55   %\n"
        "Lymphocytes   35   %\n"
        "Monocytes   5   %\n"
        "Eosinophils   3   %\n"
        "Basophils   1   %\n"
    )
    raw = extract_lab_values(text)
    keys = {v["key"] for v in raw}
    assert keys == {
        "hematocrit", "rdw", "esr", "neutrophils_pct", "lymphocytes_pct",
        "monocytes_pct", "eosinophils_pct", "basophils_pct",
    }


def test_extract_liver_panel_extended():
    text = (
        "Alkaline Phosphatase   90   IU/L\n"
        "GGT   25   IU/L\n"
        "Total Protein   7.0   g/dL\n"
        "Albumin   4.2   g/dL\n"
        "Globulin   2.8   g/dL\n"
    )
    raw = extract_lab_values(text)
    classified = classify_lab_values(raw)
    by_key = {v["key"]: v["status"] for v in classified}
    assert by_key == {"alp": "normal", "ggt": "normal", "total_protein": "normal", "albumin": "normal", "globulin": "normal"}


def test_extract_kidney_electrolytes_and_uric_acid():
    text = "Sodium   140   mmol/L\nPotassium   4.2   mmol/L\nChloride   100   mmol/L\nUric Acid   5.5   mg/dL\n"
    raw = extract_lab_values(text)
    keys = {v["key"] for v in raw}
    assert keys == {"sodium", "potassium", "chloride", "uric_acid"}


def test_extract_glucose_variants():
    text = "Post Prandial Glucose   130   mg/dL\nRandom Blood Glucose   250   mg/dL\n"
    raw = extract_lab_values(text)
    classified = classify_lab_values(raw)
    by_key = {v["key"]: v["status"] for v in classified}
    assert by_key["postprandial_glucose"] == "normal"
    assert by_key["random_glucose"] == "high"


def test_extract_vitamin_d3_variant_and_b12():
    text = "Vitamin D3   45   ng/mL\nVitamin B12   350   pg/mL\n"
    raw = extract_lab_values(text)
    keys = {v["key"] for v in raw}
    assert keys == {"vitamin_d", "vitamin_b12"}


def test_extract_qualitative_dengue_ns1_and_igm_but_not_igg():
    # Dengue IgG is deliberately not a recognized test at all (see
    # QUALITATIVE_TESTS's comment) — it usually reflects past infection,
    # not a current one, so it shouldn't get the same "reactive means
    # contact your doctor promptly" framing as an acute-infection marker.
    text = (
        "Dengue NS1 Antigen\nNon-Reactive\nInterpretation\n"
        "Dengue IgM Antibody\nReactive\nInterpretation\n"
        "Dengue IgG Antibody\nReactive\nInterpretation\n"
    )
    results = extract_qualitative_results(text)
    by_key = {r["key"]: r["status"] for r in results}
    assert by_key == {"dengue_ns1": "normal", "dengue_igm": "abnormal"}
    assert "dengue_igg" not in by_key


def test_extract_qualitative_malaria_and_covid():
    text = (
        "Malaria Antigen (P.vivax/P.falciparum)\nNegative\nInterpretation\n"
        "COVID-19 (SARS-CoV-2) RT-PCR\nNot Detected\nInterpretation\n"
    )
    results = extract_qualitative_results(text)
    by_key = {r["key"]: r["status"] for r in results}
    assert by_key == {"malaria_antigen": "normal", "covid_19": "normal"}


def test_extract_qualitative_typhidot_igg_and_igm():
    # Mirrors the real Redcliffe Labs report's layout: two separate
    # TYPHI DOT/ SALMONELLA TYPHI lines (IgG then IgM), each followed by
    # its own method line and result, then a shared interpretation table.
    text = (
        "TYPHI DOT/ SALMONELLA TYPHI IgG\n"
        "Qualilative immunoassay,rapid card\n"
        "Negative - Negative\n"
        "TYPHI DOT/ SALMONELLA TYPHI IgM\n"
        "Qualilative immunoassay,rapid card\n"
        "Negative - Negative\n"
        "Interpretation:\n"
        "Positive Indicates presence of IgM & IgG antibodies against Salmonella typhi.\n"
        "Negative Indicates absence of IgM & IgG antibodies against Salmonella spp.\n"
    )
    results = extract_qualitative_results(text)
    by_key = {r["key"]: r["status"] for r in results}
    assert by_key == {"typhidot_igg": "normal", "typhidot_igm": "normal"}


# --- extract_qualitative_results (infectious-disease screening panels) ---

def test_qualitative_hiv_non_reactive_same_line():
    text = (
        "Test Name Results Units Bio. Ref. Interval\n"
        "HIV RAPID SCREENING TEST Non-Reactive\n"
        "(Lateral Flow Chromatography)\n"
        "-----------------------------------------------------------------------\n"
        "| Final Result : Negative Negative |\n"
        "-----------------------------------------------------------------------\n"
        "-------------------------------------------------------------------\n"
        "| REMARKS | INTERPRETATION |\n"
        "|--------------|----------------------------------------------------|\n"
        "| Reactive | Indicates Presence of antibodies to HIV 1/2 virus |\n"
        "| Non-Reactive | Indicates absence of antibodies to HIV 1/2 virus |\n"
    )
    results = extract_qualitative_results(text)
    assert len(results) == 1
    assert results[0]["key"] == "hiv_screening"
    assert results[0]["status"] == "normal"


def test_qualitative_hbsag_multiline_header_and_doubled_result():
    text = (
        "Test Name Results Units Bio. Ref. Interval\n"
        "HEPATITIS B SURFACE ANTIGEN (HBsAg) RAPID \n"
        "SCREENING TEST\n"
        "(Sandwich Immunochromatography)\n"
        "Non-Reactive Non-Reactive\n"
        "Interpretation\n"
        "| Reactive | Indicates presence of Hepatitis B Surface Antigen. |\n"
        "| Non-Reactive | Indicates absence of Hepatitis B Surface Antigen. |\n"
    )
    results = extract_qualitative_results(text)
    assert len(results) == 1
    assert results[0]["key"] == "hbsag_screening"
    assert results[0]["status"] == "normal"


def test_qualitative_rpr_ignores_dilution_ratio_line():
    text = (
        "Test Name Results Units Bio. Ref. Interval\n"
        "RPR (RAPID PLASMA REAGIN)\n"
        "(Slide Flocculation)\n"
        "RPR Serum Non Reactive\n"
        "RPR -in-Dilution 1 in 2\n"
        "Interpretation\n"
        "| Non-Reactive | Indicates absence of IgM & IgG antibodies |\n"
    )
    results = extract_qualitative_results(text)
    assert len(results) == 1
    assert results[0]["key"] == "syphilis_screening"
    assert results[0]["status"] == "normal"


def test_qualitative_flags_reactive_result_as_abnormal():
    text = (
        "Test Name Results Units Bio. Ref. Interval\n"
        "HEPATITIS B SURFACE ANTIGEN (HBsAg) RAPID SCREENING TEST\n"
        "(Sandwich Immunochromatography)\n"
        "Reactive Non-Reactive\n"
        "Interpretation\n"
    )
    results = extract_qualitative_results(text)
    assert len(results) == 1
    assert results[0]["status"] == "abnormal"


def test_qualitative_no_match_when_test_absent():
    text = "Complete Blood Count\nHemoglobin 13.5 g/dL\n"
    assert extract_qualitative_results(text) == []


# --- build_report_summary (qualitative screening results) ---

def test_summary_all_screening_results_normal():
    qualitative = [
        {"key": "hiv_screening", "label": "HIV Screening (Antibody)", "category": "infectious_screening", "status": "normal"},
    ]
    result = build_report_summary([], qualitative)
    assert "non-reactive/negative" in result["summary"]
    assert "Important:" not in result["summary"]
    assert result["questions_to_ask"] == []


def test_summary_flags_reactive_screening_result_with_urgent_notice():
    qualitative = [
        {"key": "hbsag_screening", "label": "Hepatitis B Surface Antigen (HBsAg)", "category": "infectious_screening", "status": "abnormal"},
    ]
    result = build_report_summary([], qualitative)
    assert "Hepatitis B Surface Antigen (HBsAg)" in result["summary"]
    assert "reactive/positive screening result" in result["summary"]
    assert "confirmatory testing" in result["summary"]
    assert "does not confirm a diagnosis" in result["summary"]
    assert any("confirmatory testing" in q for q in result["questions_to_ask"])


# --- build_report_summary ---

def test_summary_all_normal():
    classified = [
        {"key": "tsh", "label": "TSH", "category": "thyroid", "value": 2.0, "unit": "mIU/L",
         "reference_low": 0.4, "reference_high": 4.0, "status": "normal"},
    ]
    result = build_report_summary(classified)
    assert "typical reference ranges" in result["summary"]
    assert result["questions_to_ask"] == []
    assert "not a diagnosis" in result["disclaimer"]


def test_summary_flags_abnormal_and_generates_questions():
    classified = [
        {"key": "hemoglobin", "label": "Hemoglobin", "category": "cbc", "value": 10.5, "unit": "g/dL",
         "reference_low": 12.0, "reference_high": 17.5, "status": "low"},
        {"key": "tsh", "label": "TSH", "category": "thyroid", "value": 2.0, "unit": "mIU/L",
         "reference_low": 0.4, "reference_high": 4.0, "status": "normal"},
    ]
    result = build_report_summary(classified)
    assert "Hemoglobin" in result["summary"]
    assert "below the typical range" in result["summary"]
    assert result["questions_to_ask"] == [
        "What could be causing this change in my blood counts, and do I need any follow-up tests?"
    ]


def test_summary_no_recognized_values():
    result = build_report_summary([])
    assert "couldn't automatically recognize" in result["summary"]
    assert result["questions_to_ask"] == []


# --- generate_plain_language_explanation (Gemini call mocked — no real network calls) ---

_SAMPLE_CLASSIFIED = [
    {"key": "hemoglobin", "label": "Hemoglobin", "category": "cbc", "value": 10.5, "unit": "g/dL",
     "reference_low": 12.0, "reference_high": 17.5, "status": "low"},
]


def test_explanation_skipped_when_no_api_key():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = ""
    try:
        with patch("google.genai.Client") as mock_client_cls:
            result = generate_plain_language_explanation(_SAMPLE_CLASSIFIED, "1 of 1 value is low.")
            assert result is None
            mock_client_cls.assert_not_called()
    finally:
        settings.GEMINI_API_KEY = original


def test_explanation_returns_model_text_on_success():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-key"
    try:
        mock_interaction = MagicMock(output_text="Your hemoglobin is a little low. Consider discussing with your doctor.")
        mock_client = MagicMock()
        mock_client.interactions.create.return_value = mock_interaction
        with patch("google.genai.Client", return_value=mock_client) as mock_client_cls:
            result = generate_plain_language_explanation(_SAMPLE_CLASSIFIED, "1 of 1 value is low.")
            assert result == "Your hemoglobin is a little low. Consider discussing with your doctor."
            mock_client_cls.assert_called_once_with(api_key="test-key")
            _, kwargs = mock_client.interactions.create.call_args
            assert kwargs["model"]
            assert "Hemoglobin" in kwargs["input"]
    finally:
        settings.GEMINI_API_KEY = original


def test_explanation_returns_none_on_api_failure():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-key"
    try:
        mock_client = MagicMock()
        mock_client.interactions.create.side_effect = RuntimeError("network error")
        with patch("google.genai.Client", return_value=mock_client):
            result = generate_plain_language_explanation(_SAMPLE_CLASSIFIED, "1 of 1 value is low.")
            assert result is None
    finally:
        settings.GEMINI_API_KEY = original


def test_explanation_returns_none_on_empty_output():
    original = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "test-key"
    try:
        mock_interaction = MagicMock(output_text="")
        mock_client = MagicMock()
        mock_client.interactions.create.return_value = mock_interaction
        with patch("google.genai.Client", return_value=mock_client):
            result = generate_plain_language_explanation(_SAMPLE_CLASSIFIED, "1 of 1 value is low.")
            assert result is None
    finally:
        settings.GEMINI_API_KEY = original
