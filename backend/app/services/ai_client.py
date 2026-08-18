"""
AI팀 혈액 예측 모델 연동.

AI팀 handover(Holt-Winters 모델, app/services/blood_predictor.py로 포팅)를 연결했다.
학습 데이터가 정적 CSV라 예측 계산은 CPU 바운드이므로 이벤트 루프를 막지 않도록
asyncio.to_thread로 실행한다 (blood_predictor 쪽에서 결과가 캐싱되므로 최초 1회만 무겁다).

주의:
- AI팀 자료는 ABO 혈액형(A/B/AB/O)만 구분하고 Rh는 구분하지 않는다. rh_type은
  현재 예측값 자체에는 영향을 주지 않는다.
- 위험단계(관심/주의/경계/심각) 판정에는 일일소요량 자료가 필요한데 AI팀이 아직 확보 중이다
  (handover/README.md 참고). 그 자료가 오기 전까지 current_status/next_status/risk_probability는
  실제 판정으로 교체할 수 없어 "판정 보류" 상태로 둔다.
"""
import asyncio
from typing import TypedDict, List

from app.services.blood_predictor import get_blood_stock_predictions


class BloodPrediction(TypedDict):
    dates: List[str]
    predicted_volumes: List[int]
    current_status: str          # 관심 / 주의 / 경계 / 심각
    ai_comment: str
    risk_probability: float       # 0~1
    next_status: str


async def get_blood_prediction(blood_type: str, rh_type: str) -> BloodPrediction:
    response = await asyncio.to_thread(get_blood_stock_predictions)
    forecast = response["predictions"][blood_type]

    return {
        "dates": [day["date"] for day in forecast],
        "predicted_volumes": [round(day["predicted_stock_quantity"]) for day in forecast],
        # TODO: 일일소요량 자료 확보 후 위험단계 판정 로직으로 교체 (handover/README.md 참고)
        "current_status": "판정 보류",
        "ai_comment": (
            f"{blood_type}형 보유량 {response['horizon_days']}일 예측 완료"
            f" ({response['as_of_date']} 기준). 위험단계 판정은 일일소요량 자료 확보 후 반영됩니다."
        ),
        "risk_probability": 0.0,
        "next_status": "판정 보류",
    }
