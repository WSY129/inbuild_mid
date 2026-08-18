from datetime import datetime, date, timedelta  
#문자열을 날짜로 바꾸기 위해 datetime 모듈 import

from typing import Optional
#Optional: 값이 없을 수도 있는 경우를 위해 import

from fastapi import APIRouter, Depends

from app.schemas.home import HomeResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.services.ai_client import get_blood_prediction

router = APIRouter(prefix="/home", tags=["home"])

# PRD 데이터 필드 정의표 기준: 전혈 +60일 / 성분헌혈(혈장·혈소판·혈소판혈장) +14일
WHOLE_BLOOD_INTERVAL_DAYS = 60
APHERESIS_INTERVAL_DAYS = 14


def resolve_donation_interval_days(donation_method: str) -> Optional[int]:
    """
    헌혈 방식 문자열 -> 다음 헌혈까지 필요한 간격(일). 모르는 값이면 None.

    같은 헌혈 방식을 팀마다 다르게 적고 있어서 문자열을 그대로 비교하면 안 된다.
      - 와이어프레임 Set_3 드롭다운: 전혈 / 혈소판 / 혈장 / 혈소판 혈장 / 헌혈 방식 모름
      - PRD 데이터 필드 정의표:      전혈 / 혈장성분헌혈 / 혈소판성분헌혈 / 혈소판혈장성분헌혈 / 모름
    회원가입팀은 이 값을 검증 없이 저장하기 때문에 프론트가 보내는 라벨이 그대로 DB에 들어온다.
    그래서 '성분헌혈' 접미사와 띄어쓰기를 무시하고 키워드로 판정한다.
    (표기가 또 바뀌어도 여기만 보면 되도록 딕셔너리 대신 함수로 뺌)
    """
    normalized = "".join(donation_method.split())  # 모든 공백 제거: "혈소판 혈장" == "혈소판혈장"

    if "모름" in normalized:
        return None
    if "전혈" in normalized:
        return WHOLE_BLOOD_INTERVAL_DAYS
    if "혈소판" in normalized or "혈장" in normalized:
        return APHERESIS_INTERVAL_DAYS
    return None  # 처음 보는 표기 - 틀린 D-day를 보여주느니 '정보 없음'으로 둔다


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
#-> get_current_user에서 토큰을 검증하고, 유효한 토큰이면 회원가입팀 API를 호출해 사용자 정보를 가져와 SignupUser 객체로 반환
@router.get("", response_model=HomeResponse)
async def get_home(user: SignupUser = Depends(get_current_user)):
    """
    홈 화면 데이터.
    - 닉네임/혈액형: 회원가입팀 API (토큰으로 조회)
    - 혈액량 예상 추이 / ai comment / 위기단계: AI팀 예측 모델 (현재는 더미, TODO)
    - 다음 헌혈 가능일: 이 백엔드에서 계산
    """
    prediction = await get_blood_prediction(user.bloodType, user.rhType)
    next_dday = calculate_next_donation_dday(user.donationDate, user.donationMethod)

    return HomeResponse(
        nickname=user.nickname,
        blood_type=user.bloodType,
        rh_type=user.rhType,
        next_donation_dday=next_dday,
        predicted_dates=prediction["dates"],
        predicted_volumes=prediction["predicted_volumes"],
        current_status=prediction["current_status"],
        ai_comment=prediction["ai_comment"],
        risk_probability=prediction["risk_probability"],
        next_status=prediction["next_status"],
    )
