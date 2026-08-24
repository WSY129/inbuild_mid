#헌혈 내역 조회 화면 API
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.donation_record import DonationRecordResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.services.donation_repository import list_donation_records
from app.routers.donations._shared import to_response

router = APIRouter(prefix="/donations", tags=["donations"])


#[버튼: 홈 화면의 D-day 블럭 클릭 -> 헌혈 내역 조회 화면 진입]
@router.get("", response_model=List[DonationRecordResponse])
def get_donation_history(
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """
    지금까지 등록한 헌혈 기록을 최신순으로 반환한다.
    기록이 하나도 없으면 빈 배열([])을 반환한다 -> 프론트가 이걸 보고 '기록없음' 화면을 띄우면 됨.
    """
    records = list_donation_records(db, user.internal_id)
    return [to_response(r) for r in records]
