#헌혈 내역 조회 화면 API
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.donation_record import DonationRecordResponse
from app.schemas.user import SignupUser
from app.services.rate_limit import rate_limit
from app.services.donation_repository import list_donation_records_page
from app.routers.donations._shared import to_response

router = APIRouter(prefix="/donations", tags=["donations"])


#[버튼: 홈 화면의 D-day 블럭 클릭 -> 헌혈 내역 조회 화면 진입]
@router.get("", response_model=List[DonationRecordResponse])
def get_donation_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    # 조회라 쓰기 API(분당 10회)보다는 넉넉하게 - 그래도 무제한은 아니게 막아둔다.
    user: SignupUser = Depends(rate_limit(max_calls=60, window_seconds=60)),
):
    """
    지금까지 등록한 헌혈 기록을 최신순으로 반환한다 (기본 20개, 최대 100개씩).
    기록이 하나도 없으면 빈 배열([])을 반환한다 -> 프론트가 이걸 보고 '기록없음' 화면을 띄우면 됨.
    더 볼 기록이 있으면 offset을 20, 40, ...으로 늘려가며 다음 페이지를 요청하면 된다.
    """
    records = list_donation_records_page(db, user.internal_id, limit=limit, offset=offset)
    return [to_response(r) for r in records]
