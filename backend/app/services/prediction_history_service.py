"""Read access to the user's saved risk-assessment results.

Every query is scoped to the owning user_id, so knowing another user's
record id is never enough to read or delete it (AGENTS.md Section 14).
"""
from typing import Any, Dict, Optional

from bson import ObjectId

from app.db.collections import prediction_repo

# condition key -> (patient-friendly label, assessment page key)
CONDITION_INFO = {
    "diabetes": ("Diabetes Risk Assessment", "diabetes"),
    "diabetes_pima": ("Diabetes Risk Assessment (lab values)", "diabetes"),
    "heart_disease": ("Heart Disease Risk Assessment", "heart"),
    "heart_disease_clinical": ("Heart Disease Risk Assessment (lab values)", "heart"),
    "liver_disease": ("Liver Disease Risk Assessment", "liver"),
    "liver_disease_ilpd": ("Liver Disease Risk Assessment (lab values)", "liver"),
    "liver_disease_lifestyle": ("Liver Disease Risk Assessment (lifestyle)", "liver"),
    "skin": ("Skin Image Assessment", "skin"),
}

# Filter keys the history page offers -> matching condition keys.
ASSESSMENT_FILTERS = {
    "diabetes": ["diabetes", "diabetes_pima"],
    "heart": ["heart_disease", "heart_disease_clinical"],
    "liver": ["liver_disease", "liver_disease_ilpd", "liver_disease_lifestyle"],
    "skin": ["skin"],
}

MAX_PAGE_SIZE = 50


def _to_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    condition = doc.get("condition", "")
    label, assessment = CONDITION_INFO.get(
        condition, (condition.replace("_", " ").title() or "Assessment", condition)
    )
    result = doc.get("result") or {}
    return {
        "id": str(doc["_id"]),
        "condition": condition,
        "condition_label": label,
        "assessment": assessment,
        "created_at": doc.get("created_at"),
        "risk_level": result.get("risk_level"),
        "risk_probability": result.get("risk_probability"),
        "is_elevated": result.get("is_elevated"),
        "message": result.get("message"),
        "label": result.get("clinical_label") or result.get("label"),
        "confidence_level": result.get("confidence_level"),
        "family_member_id": doc.get("family_member_id"),
        "family_member_name": doc.get("family_member_name") if doc.get("family_member_id") else None,
    }


async def list_history(
    user_id: str,
    assessment: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    query: Dict[str, Any] = {"user_id": user_id}
    if assessment:
        if assessment not in ASSESSMENT_FILTERS:
            raise ValueError("Unknown assessment type.")
        query["condition"] = {"$in": ASSESSMENT_FILTERS[assessment]}

    total = await prediction_repo.collection.count_documents(query)
    cursor = (
        prediction_repo.collection.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)
    return {
        "items": [_to_item(d) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def delete_history_item(user_id: str, prediction_id: str) -> bool:
    if not ObjectId.is_valid(prediction_id):
        return False
    res = await prediction_repo.collection.delete_one(
        {"_id": ObjectId(prediction_id), "user_id": user_id}
    )
    return res.deleted_count > 0
