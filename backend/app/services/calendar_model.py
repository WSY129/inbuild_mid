# 이 파일은 src/calendar_model.py 에서 자동 생성됩니다. 직접 고치지 마세요.
# 갱신: python src/sync_handover.py

"""달력 기반 일변화(Δ) 예측 모델.

설계 근거 (전부 실데이터 walk-forward로 검증한 관찰):
- 28일 앞 보유량은 랜덤워크에 가깝다      -> 수준은 마지막 관측값에 고정(앵커), 예측하지 않는다
- 요일/연휴 구조가 강하다                 -> 일변화(Δ)만 달력으로 예측해 누적한다
- 연휴는 길이에 따라 효과가 다르다        -> 휴무 덩어리 길이를 나눠 넣는다
- 설날/추석은 다른 공휴일과 다르다        -> 명절 항을 따로 둔다
- 연 패턴은 매끄럽지 않다(방학/명절)      -> 푸리에 대신 월 더미
- 연 계절성은 시간에 따라 변한다          -> 학습창 5년 (3년은 확실히 열세, 7년은 사실상 동률)
- 4개 혈액형 일변화 상관이 0.87~0.93      -> 계수를 공유해 추정한다(pooling), 스케일만 혈액형별
- 원 Δ의 lag-1 자기상관 +0.36, 달력 회귀
  후에도 잔차에 +0.24가 남는다             -> AR(1) 한 항을 지수 감쇠로 얹는다
- 앵커를 여러 날 평균내면 오히려 나빠진다 -> 마지막 1일만 쓴다

절대(Δ)와 곱셈(Δlog)을 수준에 따라 섞는 이유:
보유량 수준이 6,554~14,948로 2배 넘게 흔들린다. 절대 모델은 계절 하락폭을 '유닛'으로
배우므로 수준이 낮을 때 그 폭이 상대적으로 과해진다 — 실제로 시작 수준이 직전 1년
하위 25%인 fold에서 naive 대비 +4.4%까지 무너진다(정상 구간 +16.4%). 곱셈 모델은
반대로 저수준에서 +8.5%로 낫지만 정상 구간이 +13.2%로 떨어진다.
그래서 '현재 수준이 직전 1년 분포에서 몇 퍼센타일인가'로 두 예측을 섞는다.

주의 — pooling / 수준적응 / 학습창 같은 설계 선택은 walk-forward로 서로 구분되지 않는다.
독립 평가에서 확인된 것: 요일7+평일공휴일1+월11 = 19계수 단일 갈래(pooling·수준적응 없음)가
최저점 개선에서 현재 모델과 구분되지 않는다(짝지은 차이 CI 8/8 셀 모두 0 포함).
부품별로는 AR(1) 한 항만 일관되게 값한다(제거 시 2.4~5.4%p 악화).
"절대 갈래 단독은 저수준에서 역대 최저치를 밑돈다"고 적어뒀던 근거는 데이터에서 재현되지
않았다 — 수준가중 w<0.25인 fold 30개에서 그런 예측이 나온 횟수는 0회다.
따라서 두 갈래 혼합과 pooling은 **정당화되지 않은 복잡도**로 남아 있다. 축소 후보다.

추정되는 값의 수 (build_features의 열 23개와 혼동하지 말 것):
  회귀계수  23 x 2갈래(절대/곱셈)                    = 46  <- 4개 혈액형이 공유
  sigma / phi / 잔차표준편차  각 2갈래 x 4혈액형      = 24  <- 계열별
  수준가중 w  혈액형 4개                              =  4  <- 계열별
  합계 74. 혈액형 하나를 예측하는 데 실효 53개(공유 46 + 자기 것 7).

Holt-Winters는 370개(평활 3 + level + trend + 계절지수 365)를 반복 최적화로 맞추는데,
평가에 쓴 124회 적합 중 53회에서 수렴 경고가 났고 alpha가 85%에서 상한 1.0에 붙었다
(= 수준이 naive로 붕괴). 개수가 5분의 1로 준 것보다 중요한 차이는 추정 방식이다 —
여기는 최소제곱 닫힌 해라 경계해도, 수렴 실패도, 라이브러리 버전 민감성도 생기지 않는다.
"""

import numpy as np
import pandas as pd
import holidays

HORIZON = 28  # 예측 일수. src/config.py 와 같은 값이어야 한다

TRAIN_YEARS = 5
RUN_BUCKETS = (3, 4, 5)  # 휴무 덩어리 길이. 마지막 값은 '이상'을 뜻한다
MAX_PHI = 0.6            # AR(1) 계수 상한. 표본 요동으로 과하게 잡히는 것을 막는다
ALERT_Z = 0.3            # 경보선을 점추정에서 얼마나 내릴지. 탐지-오탐 순이득이 최대인 지점
LEVEL_WINDOW = 365       # '현재 수준이 높은가 낮은가'를 재는 창
RUN_PAD = 15             # 휴무 덩어리를 세기 위한 앞뒤 여유일. 국내 최장 연휴보다 넉넉히


def _off_run_length(is_off: np.ndarray) -> np.ndarray:
    """연속된 휴무일 덩어리의 길이를 각 날짜에 부여한다. 평일은 0.

    설날 5일 연휴와 광복절 하루는 재고에 미치는 영향이 완전히 다르므로 길이를 구분한다.
    """
    n = len(is_off)
    out = np.zeros(n, dtype=int)
    i = 0
    while i < n:
        if not is_off[i]:
            i += 1
            continue
        j = i
        while j < n and is_off[j]:
            j += 1
        out[i:j] = j - i
        i = j
    return out


def build_features(dates) -> np.ndarray:
    """달력만으로 결정되는 특징 행렬. 미래 날짜도 동일하게 계산되므로 누출이 없다.

    열 구성: 요일 7 + 평일공휴일 1 + 휴무덩어리길이 3 + 월 11 + 명절 1 = 23
    요일을 절편 없는 원핫으로 깔았으므로 월은 2월부터(기준=1월) 넣는다.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(dates))

    # 휴무 덩어리 길이는 창 밖으로 이어질 수 있다. 앞뒤로 패딩해 세고 원래 구간만 잘라 쓴다 —
    # 이걸 안 하면 28일 예측창 경계에 걸친 연휴가 짧게 잡혀 학습 때와 다른 특징이 된다.
    ext = pd.date_range(dates[0] - pd.Timedelta(days=RUN_PAD),
                        dates[-1] + pd.Timedelta(days=RUN_PAD), freq="D")
    kr = holidays.KR(years=range(ext.year.min(), ext.year.max() + 1))
    names = {d: n for d, n in kr.items()}
    ext_pub = np.array([d.date() in kr for d in ext])
    ext_run = _off_run_length(ext_pub | (ext.dayofweek.values >= 5))
    run = ext_run[RUN_PAD:RUN_PAD + len(dates)]

    is_pub = np.array([d.date() in kr for d in dates])
    dow = dates.dayofweek.values
    month = dates.month.values

    cols = [(dow == k).astype(float) for k in range(7)]
    cols.append((is_pub & (dow < 5)).astype(float))
    cols += [
        ((run >= L) if L == RUN_BUCKETS[-1] else (run == L)).astype(float)
        for L in RUN_BUCKETS
    ]
    cols += [(month == m).astype(float) for m in range(2, 13)]
    cols.append(np.array(
        [("설날" in names.get(d.date(), "")) or ("추석" in names.get(d.date(), ""))
         for d in dates], dtype=float))
    return np.column_stack(cols)


# build_features 열 구성의 이름표. 절제에서 열을 골라내는 데 쓴다.
# (열 순서를 바꾸면 여기도 바꿔야 한다 — __main__ 자체검증이 어긋남을 잡는다)
FEATURE_COLS = {"dow": range(0, 7), "pubhol": range(7, 8), "runlen": range(8, 11),
                "month": range(11, 22), "major": range(22, 23)}
# 절제 후보: 요일7 + 평일공휴일1 + 월11 = 19열 (휴무덩어리·명절 제거)
COLS_19 = [i for g in ("dow", "pubhol", "month") for i in FEATURE_COLS[g]]


def _pick(feat, cols):
    """cols=None이면 전체 열. 아니면 해당 열만 남긴다."""
    return feat if cols is None else feat[:, list(cols)]


def _window(arr, years=TRAIN_YEARS):
    w = int(365.25 * years)
    return arr[-w:] if len(arr) > w else arr


def _diff(series, log: bool):
    """log=True면 곱셈 갈래. 모든 경로가 여기를 지나므로 양수 검사를 여기 둔다."""
    s = np.asarray(series, dtype=float)
    if not log:
        return np.diff(s)
    if not (s > 0).all():
        raise ValueError("곱셈 갈래는 0 이하 값을 다룰 수 없다 (보유량에 0/음수가 있다)")
    return np.diff(np.log(s))


def fit_delta(dates, values, panel=None, train_years: int = TRAIN_YEARS,
              log: bool = False, cols=None) -> np.ndarray:
    """일변화를 달력 특징에 최소제곱 회귀한다.

    panel을 주면 여러 혈액형을 각자 표준편차로 정규화해 한 회귀에 쌓는다(계수 공유).
    상관이 0.87~0.93이라 표본이 4배가 되는 효과가 있고, 특히 약체인 B형이 개선된다.
    반환 계수는 '표준화 단위'이므로 쓸 때 해당 계열의 표준편차를 곱해야 한다.
    """
    feat = _pick(build_features(dates), cols)[1:]  # Δ는 첫날이 없으므로 한 칸 밀린다
    series = [np.asarray(values, dtype=float)] if panel is None else \
             [np.asarray(panel[c], dtype=float) for c in panel]
    # 길이가 어긋나면 _window가 계열마다 다른 구간을 잘라 미래 정보가 섞인다
    assert all(len(s) == len(dates) for s in series), "panel/dates 길이 불일치"

    X_parts, y_parts = [], []
    for s in series:
        d = _window(_diff(s, log), train_years)
        X_parts.append(_window(feat, train_years))
        y_parts.append(d / (d.std() or 1.0))  # 분산 0인 구간에서 조용히 NaN이 되지 않게
    return np.linalg.lstsq(np.vstack(X_parts), np.concatenate(y_parts), rcond=None)[0]


def _forecast_one(dates, values, horizon, panel, train_years, alert_z, log,
                  cols=None, use_ar1: bool = True):
    """절대(log=False) 또는 곱셈(log=True) 한 갈래의 예측 경로와 하한선.

    cols / use_ar1은 절제 실험 전용이다. 기본값이 운영 동작이므로
    predict_calendar를 그냥 부르면 아무것도 달라지지 않는다.
    """
    beta = fit_delta(dates, values, panel, train_years, log, cols)
    d = _window(_diff(values, log), train_years)
    sigma = d.std()  # 0이면 아래 step이 전부 0이 되어 앵커에서 평평한 직선 = naive로 되돌아간다

    resid = d - (_window(_pick(build_features(dates), cols)[1:], train_years) @ beta) * sigma
    # 상수 잔차면 corrcoef가 nan을 뱉고 np.clip(nan)도 nan이라 예측 전체가 NaN이 된다
    if use_ar1 and resid.std() > 0:
        phi = float(np.clip(np.nan_to_num(np.corrcoef(resid[:-1], resid[1:])[0, 1]), 0.0, MAX_PHI))
    else:
        phi = 0.0

    future = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    h = np.arange(1, horizon + 1)
    step = np.cumsum((_pick(build_features(future), cols) @ beta) * sigma + resid[-1] * phi ** h)
    band = alert_z * resid.std() * np.sqrt(h)

    if log:
        return future, values[-1] * np.exp(step), values[-1] * np.exp(step - band)
    return future, values[-1] + step, values[-1] + step - band


def level_weight(values, window: int = LEVEL_WINDOW) -> float:
    """현재 수준이 직전 window일 분포에서 차지하는 백분위. 0=최저, 1=최고.

    이 값이 그대로 절대 모델의 가중치가 된다 — 수준이 낮을수록 곱셈 쪽으로 기운다.
    """
    values = np.asarray(values, dtype=float)
    recent = values[-window:] if len(values) >= window else values
    return float((recent < values[-1]).mean())


def predict_calendar(dates, values, horizon: int = HORIZON, panel=None,
                     train_years: int = TRAIN_YEARS, alert_z: float = ALERT_Z,
                     cols=None, use_ar1: bool = True,
                     blend: bool = True) -> pd.DataFrame:
    """마지막 관측값을 앵커로 두고, 예측한 일변화를 누적해 horizon일치를 내놓는다.

    alert_signal은 경보 판정 전용 임계선이다. **예측구간이 아니다** — 실제값이 이 선
    아래로 내려갈 확률에 대한 보증이 없고, 홀드아웃 실측 커버리지는 44~55%다.
    점추정만으로 판정하면 큰 하락의 절반 이상을 놓치므로(탐지 42%), 이 선으로 판정하면
    50%까지 오른다(오탐은 14% -> 27%). 탐지-오탐 균형만 보고 고른 값이다.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates)))
    values = np.asarray(values, dtype=float)
    assert (values > 0).all(), "보유량에 0 이하가 있어 곱셈 갈래를 계산할 수 없다"

    args = (dates, values, horizon, panel, train_years, alert_z)
    kw = {"cols": cols, "use_ar1": use_ar1}
    future, p_abs, l_abs = _forecast_one(*args, log=False, **kw)
    if not blend:  # 절제: 절대 갈래 단독 (수준적응 없음)
        return pd.DataFrame({"date": future, "predicted_stock_quantity": p_abs,
                             "alert_signal": l_abs})
    _, p_log, l_log = _forecast_one(*args, log=True, **kw)

    w = level_weight(values)
    return pd.DataFrame({
        "date": future,
        "predicted_stock_quantity": w * p_abs + (1 - w) * p_log,
        "alert_signal": w * l_abs + (1 - w) * l_log,
    })


def pooled_forecaster(panel):
    """panel을 붙들고 (dates, values, horizon) 시그니처만 노출하는 예측 함수를 만든다.

    평가 하네스는 예측 함수에 학습 구간만 넘기므로, panel도 같은 길이로 잘라야
    미래 정보가 새지 않는다. 그 자르기를 여기서 강제한다.
    """
    panel = pd.DataFrame(panel).reset_index(drop=True)

    def forecast(dates, values, horizon: int = HORIZON) -> pd.DataFrame:
        n = len(values)
        assert n <= len(panel), "panel이 학습 구간보다 짧다"
        return predict_calendar(dates, values, horizon, panel=panel.iloc[:n])

    return forecast


def predict_naive(dates, values, horizon: int = HORIZON) -> pd.DataFrame:
    """베이스라인: 마지막 값을 그대로 유지한다.

    모델 비교표에 항상 포함해야 한다 — 이게 빠지면 성능을 과대평가하게 된다.
    평평한 직선이라 하락을 원리적으로 예측하지 못한다(탐지율 0%).
    """
    dates = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates)))
    future = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    const = np.repeat(float(values[-1]), horizon)
    return pd.DataFrame({
        "date": future,
        "predicted_stock_quantity": const,
        "alert_signal": const,
    })
