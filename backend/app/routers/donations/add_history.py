#헌혈 내역 기록(방식+날짜+장소) 추가 버튼 API
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.donation_record import DonationRecordCreate, DonationRecordResponse
from app.schemas.user import SignupUser
from app.services.rate_limit import rate_limit
from app.services.donation_repository import create_donation_record
from app.routers.donations._shared import to_response

router = APIRouter(prefix="/donations", tags=["donations"])


#[버튼: 헌혈 내역 기록 화면에서 방식+날짜 선택 -> 장소 선택까지 마친 뒤 '확인']
@router.post("", response_model=DonationRecordResponse, status_code=status.HTTP_201_CREATED)
def add_donation_record(
    payload: DonationRecordCreate,
    db: Session = Depends(get_db),
    user: SignupUser = Depends(rate_limit(max_calls=10, window_seconds=60)),
):
    """
    새 헌혈 기록을 저장한다. 지도에서 장소를 선택하는 화면 자체는 프론트(+지도 SDK) 담당이고,
    이 API는 그 결과(장소명, 좌표)를 방식/날짜와 함께 받아 저장하는 역할만 한다.

    저장된 기록은 이후 GET /donations 목록과 홈 화면(GET /home)의 D-day 계산에
    바로 반영된다 (해당 유저의 가장 최근 헌혈일 기준으로 재계산됨).
    """
    record = create_donation_record(
        db,
        user_internal_id=user.internal_id,
        donation_method=payload.donation_method,
        donation_date=payload.donation_date,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return to_response(record)
