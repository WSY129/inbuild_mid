"""
AI팀 handover(predict.py, Holt-Winters 삼중지수평활)를 백엔드에 포팅한 모듈.
전국 적혈구제제 보유량을 혈액형별(A/B/AB/O)로 20일 앞까지 예측한다.

원본: handover/predict.py, handover/README.md (2026-08 전달)
학습 데이터가 정적 CSV(2025-12-31까지)라 프로세스 생애주기 동안 결과가 바뀌지 않으므로
최초 호출 시 1회만 계산해 모듈 전역에 캐싱한다. CSV가 갱신되면 프로세스 재시작이 필요하다.

주의: 위험단계(관심/주의/경계/심각) 판정에 필요한 일일소요량 자료는 아직 없어
      이 모듈은 예측 개수(유닛)만 반환한다. 판정 로직은 app/services/ai_client.py 참고.
"""
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "blood_stock_2016_2025.csv"
BLOOD_TYPES = ["A", "B", "AB", "O"]
HORIZON = 20  # 예측 일수 (알림 서비스 리드타임)
SEASONAL_PERIODS = 365  # 연 단위 계절성

_cache: Optional[dict] = None


def _load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    assert df["date"].diff()[1:].eq(pd.Timedelta(days=1)).all(), "날짜가 연속이 아님"
    assert not df[BLOOD_TYPES].isna().any().any(), "혈액형 컬럼에 결측 있음"
    assert df[BLOOD_TYPES].sum(axis=1).eq(df["total"]).all(), "혈액형 합계가 total과 다름"
    return df


def _predict_one(dates, values, horizon: int = HORIZON) -> pd.Series:
    series = pd.Series(
        np.asarray(values, dtype=float),
        index=pd.DatetimeIndex(pd.to_datetime(dates), freq="D"),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(
            series,
            trend="add",
            seasonal="add",
            seasonal_periods=SEASONAL_PERIODS,
            initialization_method="estimated",
        ).fit()
        return model.forecast(horizon)


def _build_response(df: pd.DataFrame) -> dict:
    response = {
        "as_of_date": df["date"].max().strftime("%Y-%m-%d"),
        "horizon_days": HORIZON,
        "predictions": {},
    }
    for bt in BLOOD_TYPES:
        pred = _predict_one(df["date"], df[bt].values)
        response["predictions"][bt] = [
            {"date": d.strftime("%Y-%m-%d"), "predicted_stock_quantity": round(float(v), 2)}
            for d, v in pred.items()
        ]
    return response


def get_blood_stock_predictions() -> dict:
    """혈액형별 20일 보유량 예측을 반환한다 (최초 호출 시 계산, 이후 캐싱).

    반환 형식은 handover/README.md의 출력 스키마와 동일:
        {"as_of_date": ..., "horizon_days": 20, "predictions": {"A": [...], "B": [...], ...}}
    """
    global _cache
    if _cache is None:
        _cache = _build_response(_load_data())
    return _cache
