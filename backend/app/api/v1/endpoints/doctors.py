from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_user
from app.models.doctor import Doctor, DoctorSearchResponse, Specialty
from app.models.user import UserOut
from app.services import doctor_directory_service as directory
from app.services.doctor_directory_service import DoctorNotFound, InvalidSearch

router = APIRouter()


@router.get("/specialties", response_model=List[Specialty])
async def list_specialties():
    return directory.list_specialties()


# Search and details require login: consented doctors' phone numbers should
# not be harvestable by anonymous scrapers.
@router.get("/search", response_model=DoctorSearchResponse)
async def search_doctors(
    specialty: Optional[str] = Query(default=None, max_length=40),
    q: Optional[str] = Query(default=None, max_length=80, description="Name, clinic or area"),
    city: Optional[str] = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=1, le=directory.MAX_PAGE_SIZE),
    consented_only: bool = False,
    # Used only to sort by distance for this request; never stored or logged.
    lat: Optional[float] = Query(default=None, ge=-90, le=90),
    lng: Optional[float] = Query(default=None, ge=-180, le=180),
    _user: UserOut = Depends(get_current_user),
):
    try:
        return await directory.search_doctors(
            latitude=lat,
            longitude=lng,
            specialty=specialty or None,
            query=(q or "").strip() or None,
            city=(city or "").strip() or None,
            page=page,
            page_size=page_size,
            consented_only=consented_only,
        )
    except InvalidSearch as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{doctor_id}", response_model=Doctor)
async def get_doctor(doctor_id: str, _user: UserOut = Depends(get_current_user)):
    try:
        return await directory.get_doctor(doctor_id)
    except DoctorNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
