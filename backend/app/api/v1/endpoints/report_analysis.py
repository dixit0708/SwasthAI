import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.v1.deps import get_current_user
from app.models.report_analysis import ReportAnalysisOut
from app.models.user import UserOut
from app.services import report_analysis_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", summary="Analyze a lab report (PDF or image)", response_model=ReportAnalysisOut)
async def analyze_report_endpoint(
    file: UploadFile = File(...),
    current_user: UserOut = Depends(get_current_user),
):
    contents = await file.read()
    try:
        return await report_analysis_service.analyze_report(
            current_user.id, contents, file.content_type, file.filename or "report.pdf",
        )
    except ValueError as ve:
        # Validation errors from the extraction pipeline (bad file type,
        # empty/oversized file, unreadable or scanned PDF, etc.)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Report analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Report analysis failed. Please try again later.")
