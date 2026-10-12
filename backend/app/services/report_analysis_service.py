from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from app.ai.inference.lab_report_analysis import (
    classify_lab_values, extract_lab_values, extract_qualitative_results,
)
from app.ai.inference.report_explanation import generate_plain_language_explanation
from app.ai.inference.report_parsing import validate_and_extract_text
from app.ai.safety.report_safety import build_report_summary
from app.db.collections import medical_report_repo

ANALYZER_VERSION = "report-analyzer-rule-based-v1"


async def analyze_report(user_id: str, contents: bytes, content_type: str, filename: str) -> dict:
    """Extracts text from the uploaded PDF/image, matches it against the
    known lab parameter table, classifies each recognized value against a
    reference range, and stores the structured result against the owning
    user.

    The raw file itself is never persisted (AGENTS.md Section 12/48) — only
    the already-extracted, already-classified result is written to
    `medical_reports`, so there is no separate stored-file access-control
    surface to protect for this v1.

    Both `validate_and_extract_text` (PDF parsing, or Gemini OCR for an
    image/scanned PDF) and `generate_plain_language_explanation` (Gemini
    text) make *synchronous* network calls under the hood. Run off the
    event loop via `run_in_threadpool` — otherwise a single slow OCR/LLM
    call would block FastAPI's single-threaded event loop entirely,
    freezing every other in-flight request on the server, not just this
    one (found by testing: an image upload appeared to hang, and a second,
    concurrent request never even started until the first one finished).
    """
    text = await run_in_threadpool(validate_and_extract_text, contents, content_type)
    raw_values = extract_lab_values(text)
    classified_values = classify_lab_values(raw_values)
    qualitative_results = extract_qualitative_results(text)
    summary = build_report_summary(classified_values, qualitative_results)

    # Enhancement layer, not a dependency — see report_explanation.py's
    # module docstring for why a failure here must never fail the request.
    llm_explanation = await run_in_threadpool(
        generate_plain_language_explanation, classified_values, summary["summary"], qualitative_results,
    )

    response = {
        "values": classified_values,
        "qualitative_results": qualitative_results,
        "summary": summary["summary"],
        "llm_explanation": llm_explanation,
        "questions_to_ask": summary["questions_to_ask"],
        "disclaimer": summary["disclaimer"],
        "analyzer_version": ANALYZER_VERSION,
    }

    await medical_report_repo.create({
        "user_id": user_id,
        "filename": filename,
        "analyzer_version": ANALYZER_VERSION,
        "result": response,
        "created_at": datetime.now(timezone.utc),
    })

    return response
