#API 응답형식 정의하는 pydantic 스키마
from typing import List
from pydantic import BaseModel


class HomeResponse(BaseModel):
    nickname: str
    blood_type: str            # ABO
    rh_type: str                # Rh
    next_donation_dday: str     # 예: "D-1", "D-DAY", "정보 없음"
    predicted_dates: List[str]
    predicted_volumes: List[int]   # 보유량 점추정(유닛 수). horizon 28일이라 길이 28
    # 경보(하락) 판정에는 점추정이 아니라 이 값을 쓴다. 항상 predicted_volumes 이하.
    # 신뢰구간이 아니므로 "95% 확률" 류의 문구로 표시하면 안 된다 (app/services/ai_client.py 참고).
    alert_signals: List[int]
    current_status: str         # 관심 / 주의 / 경계 / 심각
    ai_comment: str
    risk_probability: float     # 0~1, 예: 다음 위기단계로 격상될 가능성
    next_status: str
