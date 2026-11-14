from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId

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


# ---------------------------------------------------------------------------
# History: every query is scoped to the owning user_id (AGENTS.md Section 14)
# ---------------------------------------------------------------------------

MAX_PAGE_SIZE = 50


def _flagged_count(result: Dict[str, Any]) -> int:
    numeric = sum(1 for v in result.get("values", []) if v.get("status") in ("low", "high"))
    qualitative = sum(1 for q in result.get("qualitative_results", []) if q.get("status") == "abnormal")
    return numeric + qualitative


async def list_reports(user_id: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    query = {"user_id": user_id}

    total = await medical_report_repo.collection.count_documents(query)
    cursor = (
        medical_report_repo.collection.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for doc in await cursor.to_list(length=page_size):
        result = doc.get("result") or {}
        items.append({
            "id": str(doc["_id"]),
            "filename": doc.get("filename") or "Report",
            "created_at": doc.get("created_at"),
            "summary": result.get("summary", ""),
            "values_count": len(result.get("values", [])) + len(result.get("qualitative_results", [])),
            "flagged_count": _flagged_count(result),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_report(user_id: str, report_id: str) -> Optional[Dict[str, Any]]:
    if not ObjectId.is_valid(report_id):
        return None
    doc = await medical_report_repo.collection.find_one({"_id": ObjectId(report_id), "user_id": user_id})
    if not doc:
        return None
    return {
        **(doc.get("result") or {}),
        "id": str(doc["_id"]),
        "filename": doc.get("filename") or "Report",
        "created_at": doc.get("created_at"),
    }


async def delete_report(user_id: str, report_id: str) -> bool:
    if not ObjectId.is_valid(report_id):
        return False
    res = await medical_report_repo.collection.delete_one({"_id": ObjectId(report_id), "user_id": user_id})
    return res.deleted_count > 0
