from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.api.v1.deps import get_current_user
from app.models.family import (
    FamilyMemberCreate,
    FamilyMemberOut,
    FamilyMemberUpdate,
    FamilyOverviewOut,
    HealthMeasurementCreate,
    HealthMeasurementOut,
    MedicalHistoryCreate,
    MedicalHistoryUpdate,
    MedicalRecordCreate,
    MedicalRecordOut,
    MedicalRecordUpdate,
    MedicationCreate,
    MedicationOut,
    MedicationUpdate,
    TimelineEventOut,
)
from app.models.user import UserOut
from app.services import family_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=FamilyOverviewOut)
async def get_overview(current_user: UserOut = Depends(get_current_user)):
    return await family_service.get_family_overview(current_user.id)


# ---------------------------------------------------------------------------
# Family Members
# ---------------------------------------------------------------------------

@router.get("/members", response_model=List[FamilyMemberOut])
async def list_family_members(
    include_archived: bool = Query(False),
    current_user: UserOut = Depends(get_current_user),
):
    return await family_service.list_members(current_user.id, include_archived=include_archived)


@router.post("/members", response_model=FamilyMemberOut, status_code=status.HTTP_201_CREATED)
async def create_family_member(
    payload: FamilyMemberCreate,
    current_user: UserOut = Depends(get_current_user),
):
    try:
        return await family_service.create_member(current_user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/members/{member_id}", response_model=FamilyMemberOut)
async def get_family_member(
    member_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    member = await family_service.get_member(current_user.id, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")
    return member


@router.put("/members/{member_id}", response_model=FamilyMemberOut)
async def update_family_member(
    member_id: str,
    payload: FamilyMemberUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    member = await family_service.update_member(current_user.id, member_id, payload)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")
    return member


@router.delete("/members/{member_id}", status_code=status.HTTP_200_OK)
async def delete_family_member(
    member_id: str,
    cascade: bool = Query(True),
    current_user: UserOut = Depends(get_current_user),
):
    success = await family_service.delete_member(current_user.id, member_id, cascade=cascade)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")
    return {"message": "Family member deleted successfully"}


# ---------------------------------------------------------------------------
# Medical History (Per Member)
# ---------------------------------------------------------------------------

@router.post("/members/{member_id}/history", response_model=FamilyMemberOut, status_code=status.HTTP_201_CREATED)
async def add_medical_history(
    member_id: str,
    payload: MedicalHistoryCreate,
    current_user: UserOut = Depends(get_current_user),
):
    updated_member = await family_service.add_medical_history(current_user.id, member_id, payload)
    if not updated_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")
    return updated_member


@router.put("/members/{member_id}/history/{item_id}", response_model=FamilyMemberOut)
async def update_medical_history(
    member_id: str,
    item_id: str,
    payload: MedicalHistoryUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    updated_member = await family_service.update_medical_history(current_user.id, member_id, item_id, payload)
    if not updated_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical history item not found")
    return updated_member


@router.delete("/members/{member_id}/history/{item_id}", response_model=FamilyMemberOut)
async def delete_medical_history(
    member_id: str,
    item_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    updated_member = await family_service.delete_medical_history(current_user.id, member_id, item_id)
    if not updated_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical history item not found")
    return updated_member


# ---------------------------------------------------------------------------
# Medical Records & Document Upload
# ---------------------------------------------------------------------------

@router.get("/records", response_model=List[MedicalRecordOut])
async def list_medical_records(
    member_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort: str = Query("newest"),
    current_user: UserOut = Depends(get_current_user),
):
    return await family_service.list_records(
        current_user.id,
        member_id=member_id,
        category=category,
        search=search,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort,
    )


@router.post("/records", response_model=MedicalRecordOut, status_code=status.HTTP_201_CREATED)
async def create_medical_record(
    member_id: str = Form(...),
    title: str = Form(...),
    category: str = Form(...),
    record_date: str = Form(...),
    provider: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: UserOut = Depends(get_current_user),
):
    file_bytes = None
    original_filename = None
    content_type = None

    if file and file.filename:
        file_bytes = await file.read()
        original_filename = file.filename
        content_type = file.content_type

    payload = MedicalRecordCreate(
        member_id=member_id,
        title=title,
        category=category,
        record_date=record_date,
        provider=provider,
        notes=notes,
    )

    try:
        return await family_service.create_record(
            current_user.id,
            payload,
            file_bytes=file_bytes,
            original_filename=original_filename,
            content_type=content_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/records/{record_id}", response_model=MedicalRecordOut)
async def get_medical_record(
    record_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    record = await family_service.get_record(current_user.id, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found")
    return record


@router.get("/records/{record_id}/document")
async def get_medical_document(
    record_id: str,
    download: bool = Query(False),
    current_user: UserOut = Depends(get_current_user),
):
    doc_info = await family_service.get_document_file(current_user.id, record_id)
    if not doc_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical document not found or access denied",
        )

    file_path, filename, media_type = doc_info
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
        content_disposition_type=disposition,
    )


@router.put("/records/{record_id}", response_model=MedicalRecordOut)
async def update_medical_record(
    record_id: str,
    payload: MedicalRecordUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    updated = await family_service.update_record(current_user.id, record_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found")
    return updated


@router.delete("/records/{record_id}", status_code=status.HTTP_200_OK)
async def delete_medical_record(
    record_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    success = await family_service.delete_record(current_user.id, record_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found")
    return {"message": "Medical record deleted successfully"}


# ---------------------------------------------------------------------------
# Prescriptions & Medications
# ---------------------------------------------------------------------------

@router.get("/medications", response_model=List[MedicationOut])
async def list_medications(
    member_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: UserOut = Depends(get_current_user),
):
    return await family_service.list_medications(current_user.id, member_id=member_id, status=status)


@router.post("/medications", response_model=MedicationOut, status_code=status.HTTP_201_CREATED)
async def create_medication(
    payload: MedicationCreate,
    current_user: UserOut = Depends(get_current_user),
):
    try:
        return await family_service.create_medication(current_user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/medications/{medication_id}", response_model=MedicationOut)
async def update_medication(
    medication_id: str,
    payload: MedicationUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    updated = await family_service.update_medication(current_user.id, medication_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication record not found")
    return updated


@router.delete("/medications/{medication_id}", status_code=status.HTTP_200_OK)
async def delete_medication(
    medication_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    success = await family_service.delete_medication(current_user.id, medication_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication record not found")
    return {"message": "Medication record deleted successfully"}


# ---------------------------------------------------------------------------
# Health Measurements / Progress
# ---------------------------------------------------------------------------

@router.get("/measurements", response_model=List[HealthMeasurementOut])
async def list_measurements(
    member_id: Optional[str] = Query(None),
    metric_type: Optional[str] = Query(None),
    current_user: UserOut = Depends(get_current_user),
):
    return await family_service.list_measurements(
        current_user.id, member_id=member_id, metric_type=metric_type
    )


@router.post("/measurements", response_model=HealthMeasurementOut, status_code=status.HTTP_201_CREATED)
async def create_measurement(
    payload: HealthMeasurementCreate,
    current_user: UserOut = Depends(get_current_user),
):
    try:
        return await family_service.create_measurement(current_user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/measurements/{measurement_id}", status_code=status.HTTP_200_OK)
async def delete_measurement(
    measurement_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    success = await family_service.delete_measurement(current_user.id, measurement_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Measurement record not found")
    return {"message": "Measurement record deleted successfully"}


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

@router.get("/timeline", response_model=List[TimelineEventOut])
async def get_timeline(
    member_id: Optional[str] = Query(None),
    current_user: UserOut = Depends(get_current_user),
):
    return await family_service.get_member_timeline(current_user.id, member_id=member_id)
