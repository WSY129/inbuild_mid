"""
예측 기반 '혈액 부족' 알림 배치 - 실제 판단 로직.

매일 1회(app/services/notification_scheduler.py) 알림을 켜둔 전체 유저를 훑어서, 각자
설정(sensitivity/frequency/resend_count)에 맞춰 보낼지 말지를 정하고 FCM으로 발송한다.

경보 판정에 쓰는 신호는 위험단계(관심/주의/경계/심각, current_status)가 아니라 alert_signal이다.
app/services/ai_client.py에 적혀 있듯 위험단계 판정은 AI팀의 일일소요량 자료가 아직 없어
"판정 보류"로 막혀 있지만, alert_signal(경보선)은 이미 쓸 수 있는 신호이므로 그걸 쓴다
(predicted_volumes가 alert_signal 이하로 떨어지는 날이 있으면 "부족 조짐"으로 본다).

⚠️ 아래 두 매핑은 PRD/엑셀 정의표에 없어서 이 배치가 임의로 정한 가정이다
   (README "확인 필요한 가정" 참고, PRD에 정의가 생기면 교체할 것):

- sensitivity → 며칠짜리 구간을 볼지. ai_client.py의 정확도 구간(1~7일 운영판단 /
  8~21일 경보발동 / 22~28일 참고용, alert_signal을 경보 근거로 쓰지 않는 구간)을 기준으로 잡았다.
    민감 = 21일 내 아무 날이나 조짐 있으면 경보 (가장 이르게 감지)
    보통 = 14일 내
    둔함 = 7일 내 (운영 판단 구간에서 확실할 때만 경보)
- resend_count의 의미. "총 발송 횟수"가 아니라 "최초 발송 이후 추가로 재수신하는 횟수"로
  해석했다 (필드명이 '재수신 횟수'이지 '총 수신 횟수'가 아니라서). 즉 한 경보당 최대
  발송 횟수 = 1(최초) + resend_count.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.device_token import DeviceToken
from app.models.notification_state import NotificationState
from app.models.user_settings import UserSettings
from app.services.ai_client import get_blood_prediction, BloodPrediction
from app.services.push_client import send_push, PushNotConfiguredError
from app.services.user_repository import get_user_by_internal_id

logger = logging.getLogger(__name__)

SENSITIVITY_WINDOW_DAYS = {"민감": 21, "보통": 14, "둔함": 7}
DEFAULT_WINDOW_DAYS = SENSITIVITY_WINDOW_DAYS["보통"]


def _is_alert(prediction: BloodPrediction, window_days: int) -> bool:
    volumes = prediction["predicted_volumes"][:window_days]
    signals = prediction["alert_signals"][:window_days]
    return any(volume <= signal for volume, signal in zip(volumes, signals))


def _should_resend(settings_row: UserSettings, state: NotificationState, now: datetime) -> bool:
    """alert_active(=이미 경보 중)일 때만 호출된다. frequency/resend_count 규칙에 맞으면 True."""
    if settings_row.frequency == "재수신하지않음":
        return False  # 최초 1건만 보내고 이 경보에서는 더 안 보냄

    resends_done = state.sent_count - 1
    if settings_row.resend_count is not None and resends_done >= settings_row.resend_count:
        return False

    last_sent = state.last_sent_at
    if last_sent is None:
        return True
    if last_sent.tzinfo is None:  # SQLite는 DateTime(timezone=True)도 naive로 돌려준다 (다른 곳과 동일 패턴)
        last_sent = last_sent.replace(tzinfo=timezone.utc)

    return (now - last_sent).days >= int(settings_row.frequency)


def _get_or_create_state(db: Session, user_internal_id: int) -> NotificationState:
    state = db.get(NotificationState, user_internal_id)
    if state is None:
        state = NotificationState(user_internal_id=user_internal_id)
        db.add(state)
        db.flush()
    return state


def _run_for_user(
    db: Session,
    settings_row: UserSettings,
    prediction_cache: Dict[str, BloodPrediction],
    now: datetime,
) -> None:
    user = get_user_by_internal_id(settings_row.user_internal_id)
    if user is None:
        return  # 탈퇴 등으로 회원가입팀 DB에서 이미 지워짐 - 우리 쪽 설정 행만 고아로 남아있는 상태

    tokens = [
        row.token
        for row in db.query(DeviceToken)
        .filter(DeviceToken.user_internal_id == settings_row.user_internal_id)
        .all()
    ]
    if not tokens:
        return

    if user.bloodType not in prediction_cache:
        prediction_cache[user.bloodType] = asyncio.run(get_blood_prediction(user.bloodType, user.rhType))
    prediction = prediction_cache[user.bloodType]

    window_days = SENSITIVITY_WINDOW_DAYS.get(settings_row.sensitivity, DEFAULT_WINDOW_DAYS)
    state = _get_or_create_state(db, settings_row.user_internal_id)

    if not _is_alert(prediction, window_days):
        if state.alert_active:
            # 예측이 회복돼 경보가 풀림 - 다음에 다시 나빠지면 새 경보로 취급하도록 리셋
            state.alert_active = False
            state.sent_count = 0
            db.commit()
        return

    is_new_episode = not state.alert_active
    if not is_new_episode and not _should_resend(settings_row, state, now):
        return

    try:
        invalid_tokens = send_push(
            tokens,
            title="헌혈 부족 예보",
            body=f"{user.bloodType}형 보유량이 앞으로 {window_days}일 내 부족해질 조짐이 보여요. 헌혈로 도와주세요!",
            data={"type": "blood_shortage_alert", "blood_type": user.bloodType},
        )
    except PushNotConfiguredError:
        logger.warning(
            "FCM 미설정 - user_internal_id=%s 발송 건너뜀 (.env의 FCM_CREDENTIALS_PATH 확인)",
            settings_row.user_internal_id,
        )
        return

    if invalid_tokens:
        db.query(DeviceToken).filter(DeviceToken.token.in_(invalid_tokens)).delete(synchronize_session=False)

    state.alert_active = True
    state.sent_count = 1 if is_new_episode else state.sent_count + 1
    state.last_sent_at = now
    db.commit()


def run_notification_batch() -> None:
    """스케줄러(app/services/notification_scheduler.py)가 매일 호출하는 진입점."""
    now = datetime.now(timezone.utc)
    prediction_cache: Dict[str, BloodPrediction] = {}
    db = SessionLocal()
    try:
        settings_rows = db.query(UserSettings).filter(UserSettings.notification_enabled.is_(True)).all()
        for settings_row in settings_rows:
            try:
                _run_for_user(db, settings_row, prediction_cache, now)
            except Exception:
                db.rollback()
                logger.exception(
                    "알림 배치 처리 실패 (user_internal_id=%s)", settings_row.user_internal_id
                )
    finally:
        db.close()
