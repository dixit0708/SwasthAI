import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.v1.deps import get_current_user
from app.models.history import ReportDetailOut, ReportHistoryResponse
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


@router.get(
    "/history",
    summary="List the current user's analysed reports",
    response_model=ReportHistoryResponse,
)
async def report_history_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: UserOut = Depends(get_current_user),
):
    return await report_analysis_service.list_reports(current_user.id, page=page, page_size=page_size)


@router.get(
    "/history/{report_id}",
    summary="Get one analysed report in full",
    response_model=ReportDetailOut,
)
async def report_detail_endpoint(
    report_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    report = await report_analysis_service.get_report(current_user.id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.delete("/history/{report_id}", summary="Delete one analysed report")
async def delete_report_endpoint(
    report_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    deleted = await report_analysis_service.delete_report(current_user.id, report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted"}
