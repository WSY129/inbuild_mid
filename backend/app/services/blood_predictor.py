"""
AI팀 handover-2(달력 회귀 모델)를 백엔드에 연결한 모듈.
전국 적혈구제제 보유량을 혈액형별(A/B/AB/O)로 28일 앞까지 예측한다.

원본: handover-2/predict.py, handover-2/README.md (2026-08-22 전달)
이 파일은 원본 predict.py의 "CSV 적재 + 무결성 검사 + 응답 조립" 부분에 해당한다.
모델 본체는 app/services/calendar_model.py에 원본 그대로 벤더링해뒀다
(md5 ebd7b0b44682af7bd0e18d6832b23812). AI팀이 직접 수정을 금지했으므로 손대지 말 것 —
과거에 손으로 복제했다가 저장소와 갈라져 같은 데이터로 예측이 최대 32% 달라진 사례가 있다.
수정이 필요하면 AI팀에 재생성을 요청한다.

Holt-Winters(이전 전달본)에서 교체한 이유는 handover-2/README.md "왜 교체했나" 참고.
요약하면 이전 설정이 naive("어제 값 그대로") 베이스라인에 졌고, 124회 적합 중 53회에서
수렴 경고가 났다. 새 모델은 최소제곱 닫힌 해라 반복 최적화가 없고, 같은 입력이면
라이브러리 버전과 무관하게 같은 출력이 나온다. 그래서 requirements.txt의 버전 고정도 풀었다.

AI팀 권고는 "하루 한 번 배치로 돌리고 API는 결과 JSON만 읽기"인데, 학습 데이터가
정적 CSV(2025-12-31까지)라 프로세스 생애주기 동안 결과가 바뀌지 않으므로 배치 대신
최초 호출 시 1회만 계산해 모듈 전역에 캐싱한다(전체 4형 약 0.2초). CSV가 갱신되면
프로세스 재시작이 필요하다 — 갱신 주기가 짧아지면 그때 배치로 옮긴다.

주의: 위험단계(관심/주의/경계/심각) 판정에 필요한 일일소요량 자료는 아직 없어
      이 모듈은 예측 개수(유닛)와 경보선만 반환한다. 판정 로직은 app/services/ai_client.py 참고.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from app.services.calendar_model import HORIZON, predict_calendar

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "blood_stock_2016_2025.csv"
BLOOD_TYPES = ["A", "B", "AB", "O"]

_cache: Optional[dict] = None


class BloodStockDataError(ValueError):
    """CSV/예측 응답 무결성 검사 실패. python -O로 실행해도(assert가 사라지는 상황) 계속 동작해야
    하는 데이터 검증이라 assert 대신 명시적으로 예외를 던진다."""


def _load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """CSV를 읽고 기본 무결성을 확인한다. 깨진 입력으로 조용히 예측하지 않기 위함."""
    df = pd.read_csv(path, parse_dates=["date"])
    if not df["date"].diff()[1:].eq(pd.Timedelta(days=1)).all():
        raise BloodStockDataError("날짜가 연속이 아님")
    if df[BLOOD_TYPES].isna().any().any():
        raise BloodStockDataError("혈액형 컬럼에 결측 있음")
    if not df[BLOOD_TYPES].sum(axis=1).eq(df["total"]).all():
        raise BloodStockDataError("혈액형 합계가 total과 다름")
    # 곱셈 갈래(Δlog)가 0 이하를 다룰 수 없어 모델 쪽에서도 막지만, 여기서 먼저 걸러
    # 어느 단계에서 깨졌는지 알 수 있게 한다.
    if not (df[BLOOD_TYPES] > 0).all().all():
        raise BloodStockDataError("보유량에 0 이하가 있음")
    return df


def _build_response(df: pd.DataFrame) -> dict:
    response = {
        "as_of_date": df["date"].max().strftime("%Y-%m-%d"),
        "horizon_days": HORIZON,
        "predictions": {},
    }
    for bt in BLOOD_TYPES:
        # panel: 4개 혈액형을 함께 넘겨 달력 계수를 공유 추정한다(일변화 상관 0.87~0.93).
        pred = predict_calendar(df["date"], df[bt].values, panel=df[BLOOD_TYPES])
        response["predictions"][bt] = [
            {
                "date": r.date.strftime("%Y-%m-%d"),
                "predicted_stock_quantity": round(float(r.predicted_stock_quantity), 2),
                "alert_signal": round(float(r.alert_signal), 2),
            }
            for r in pred.itertuples()
        ]
    return response


def _validate(response: dict) -> dict:
    """원본 predict.py의 자체 점검. 스키마가 조용히 깨진 채 API로 나가는 것을 막는다."""
    if set(response["predictions"]) != set(BLOOD_TYPES):
        raise BloodStockDataError("예측 응답의 혈액형 구성이 예상과 다름")
    if not all(len(v) == HORIZON for v in response["predictions"].values()):
        raise BloodStockDataError(f"예측 응답 길이가 HORIZON({HORIZON})과 다름")
    for bt, rows in response["predictions"].items():
        if not all(r["alert_signal"] <= r["predicted_stock_quantity"] for r in rows):
            raise BloodStockDataError(f"{bt}: alert_signal이 predicted_stock_quantity보다 큼")
        if not all(r["predicted_stock_quantity"] > 0 for r in rows):
            raise BloodStockDataError(f"{bt}: predicted_stock_quantity에 0 이하가 있음")
        dates = [pd.Timestamp(r["date"]) for r in rows]
        if not all((b - a).days == 1 for a, b in zip(dates, dates[1:])):
            raise BloodStockDataError(f"{bt}: 날짜 불연속")
    return response


def get_blood_stock_predictions() -> dict:
    """혈액형별 28일 보유량 예측을 반환한다 (최초 호출 시 계산, 이후 캐싱).

    반환 형식은 handover-2/README.md의 출력 스키마와 동일:
        {"as_of_date": ..., "horizon_days": 28,
         "predictions": {"A": [{"date", "predicted_stock_quantity", "alert_signal"}, ...], ...}}
    """
    global _cache
    if _cache is None:
        _cache = _validate(_build_response(_load_data()))
    return _cache
