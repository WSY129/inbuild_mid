import logging
from datetime import datetime, date, timedelta
#문자열을 날짜로 바꾸기 위해 datetime 모듈 import

from typing import Optional
#Optional: 값이 없을 수도 있는 경우를 위해 import

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.home import HomeResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.services.ai_client import get_blood_prediction
from app.services.donation_method import resolve_donation_interval_days
from app.services.donation_repository import get_latest_donation_record

router = APIRouter(prefix="/home", tags=["home"])
logger = logging.getLogger(__name__)

# 헌혈 방식 문자열 판정(resolve_donation_interval_days)은 mission_service.py와
# schemas/donation_record.py도 같이 쓰기 때문에 app/services/donation_method.py로 옮겼다.
# 여기서는 계속 같은 이름으로 재노출만 한다 (다른 파일에서 이 경로로 이미 import하고 있을 수 있어서).


def calculate_next_donation_dday(
    donation_date: Optional[str], donation_method: Optional[str]
) -> str:
    """다음 헌혈 가능일을 d-day 형식 문자열로 계산."""
    if not donation_date or not donation_method:
        return "정보 없음"

    interval = resolve_donation_interval_days(donation_method)
    if interval is None:  # "모름", 또는 우리가 모르는 표기
        return "정보 없음"

    last_date = datetime.strptime(donation_date, "%Y-%m-%d").date()
    next_date = last_date + timedelta(days=interval)
    remaining = (next_date - date.today()).days

    if remaining <= 0:
        return "D-DAY"
    return f"D-{remaining}"

#인증된 사용자만 접근 가능하도록 get_current_user를 Depends로 주입
#-> get_current_user에서 토큰을 검증하고, 유효한 토큰이면 blood_link.db를 조회해 사용자 정보를 SignupUser 객체로 반환
@router.get("", response_model=HomeResponse)
async def get_home(
    user: SignupUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    홈 화면 데이터.
    - 닉네임/혈액형: blood_link.db (토큰으로 조회)
    - 혈액량 예상 추이 / 경보선 / ai comment: AI팀 달력 회귀 예측 모델 (28일)
    - 위기단계: 일일소요량 자료 미확보로 아직 "판정 보류" (app/services/ai_client.py 참고)
    - 다음 헌혈 가능일: 이 백엔드에서 계산.
      app/routers/donations(헌혈 내역 기록 화면)로 등록한 기록이 하나라도 있으면
      그 중 가장 최근 헌혈일 기준으로, 아직 하나도 없으면 회원가입 시 입력한 값 기준으로 계산한다.

    AI 예측 서비스가 죽어 있어도 홈 화면 전체가 500으로 죽지 않도록,
    예측 실패는 잡아서 "판정 보류" 상태로 대체한다 (닉네임/혈액형/D-day는 그대로 내려간다).
    """
    try:
        prediction = await get_blood_prediction(user.bloodType, user.rhType)
    except Exception:
        logger.exception("AI 예측 조회 실패 - 판정 보류로 대체 (blood_type=%s)", user.bloodType)
        prediction = {
            "dates": [],
            "predicted_volumes": [],
            "alert_signals": [],
            "current_status": "판정 보류",
            "ai_comment": "예측 데이터를 일시적으로 불러올 수 없습니다.",
            "risk_probability": 0.0,
            "next_status": "판정 보류",
        }

    latest_record = get_latest_donation_record(db, user.internal_id)
    if latest_record:
        donation_date = latest_record.donation_date.strftime("%Y-%m-%d")
        donation_method = latest_record.donation_method
    else:
        donation_date = user.donationDate
        donation_method = user.donationMethod

    next_dday = calculate_next_donation_dday(donation_date, donation_method)

    return HomeResponse(
        nickname=user.nickname,
        blood_type=user.bloodType,
        rh_type=user.rhType,
        next_donation_dday=next_dday,
        predicted_dates=prediction["dates"],
        predicted_volumes=prediction["predicted_volumes"],
        alert_signals=prediction["alert_signals"],
        current_status=prediction["current_status"],
        ai_comment=prediction["ai_comment"],
        risk_probability=prediction["risk_probability"],
        next_status=prediction["next_status"],
    )
