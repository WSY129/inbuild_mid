"""
AI팀 혈액 예측 모델 연동.

AI팀 handover-2(달력 회귀 모델, app/services/blood_predictor.py로 연결)를 사용한다.
학습 데이터가 정적 CSV라 예측 계산은 CPU 바운드이므로 이벤트 루프를 막지 않도록
asyncio.to_thread로 실행한다 (blood_predictor 쪽에서 결과가 캐싱되므로 최초 1회만 무겁다).

주의:
- AI팀 자료는 ABO 혈액형(A/B/AB/O)만 구분하고 Rh는 구분하지 않는다. rh_type은
  현재 예측값 자체에는 영향을 주지 않는다.
- 위험단계(관심/주의/경계/심각) 판정에는 일일소요량 자료가 필요한데 AI팀이 아직 확보 중이다
  (handover-2/README.md 참고). 예측값은 유닛 수이고 경보 기준은 일수(관심 5일↓ / 주의 3일↓ /
  경계 2일↓ / 심각 1일↓)라 `보유일수 = 예측 유닛 ÷ 일일소요량` 변환이 필요하다.
  그 자료가 오기 전까지 current_status/next_status/risk_probability는 실제 판정으로
  교체할 수 없어 "판정 보류" 상태로 둔다.
  ※ AI팀 확인 요청 사항: 일일소요량이 고정 상수인지 날짜별 시계열인지에 따라 처리가 달라진다.
    시계열이면 28일 뒤 소요량도 함께 예측해야 하므로 담당 협의가 필요하다.

alert_signal(경보선) 취급 규칙 — handover-2/README.md에 명시된 제약이므로 지킬 것:
- 하락 경보 판정에는 점추정(predicted_volumes)이 아니라 alert_signals를 쓴다.
- 신뢰구간이 아니다. 홀드아웃 실측 커버리지가 44~55%에 불과해 "95% 확률로 이 위" 같은
  문구로 표시하면 안 된다. 그래서 risk_probability에 이 값을 확률로 환산해 넣지 않는다.
- 4개 혈액형의 일변화 상관이 0.87~0.93이라 독립 사건이 아니다. 혈액형별 탐지율을
  퍼센트로 합산하지 말 것.

28일 구간은 정확도가 뒤로 갈수록 떨어진다 (홀드아웃 상대오차, 4형 평균 / 혈액형별 최댓값):
  1~7일   5.2% / 5.9%   운영 판단
  8~21일  12.3% / 13.8%  경보 발동
  22~28일 12.7% / 15.5%  추세 참고만 — 경보 근거로 쓰지 않는다
A형이 세 구간 모두 최댓값이므로, 4형 공통 임계선을 잡을 때는 평균이 아니라 최댓값 기준으로 한다.
"""
import asyncio
from typing import TypedDict, List

from app.services.blood_predictor import get_blood_stock_predictions

# 경보 근거로 쓰지 않는 꼬리 구간(22~28일)의 시작 인덱스. ai_comment 문구에만 쓴다.
ALERT_HORIZON_DAYS = 21


class BloodPrediction(TypedDict):
    dates: List[str]
    predicted_volumes: List[int]
    alert_signals: List[int]      # 경보 판정용 임계선. 항상 predicted_volumes 이하
    current_status: str           # 관심 / 주의 / 경계 / 심각
    ai_comment: str
    risk_probability: float       # 0~1
    next_status: str


async def get_blood_prediction(blood_type: str, rh_type: str) -> BloodPrediction:
    response = await asyncio.to_thread(get_blood_stock_predictions)
    forecast = response["predictions"][blood_type]

    # round()는 단조증가라 alert_signal <= predicted_stock_quantity 관계가 정수 변환 후에도 유지된다.
    return {
        "dates": [day["date"] for day in forecast],
        "predicted_volumes": [round(day["predicted_stock_quantity"]) for day in forecast],
        "alert_signals": [round(day["alert_signal"]) for day in forecast],
        # TODO: 일일소요량 자료 확보 후 위험단계 판정 로직으로 교체 (handover-2/README.md 참고)
        "current_status": "판정 보류",
        "ai_comment": (
            f"{blood_type}형 보유량 {response['horizon_days']}일 예측 완료"
            f" ({response['as_of_date']} 기준). 경보 발동은 {ALERT_HORIZON_DAYS}일까지를 근거로 하며"
            f" 그 이후 구간은 추세 참고용입니다."
            f" 위험단계 판정은 일일소요량 자료 확보 후 반영됩니다."
        ),
        "risk_probability": 0.0,
        "next_status": "판정 보류",
    }
