#전체 알림 수신 토글 버튼 API
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.settings_schema import NotificationToggleRequest, SettingsResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.routers.settings._shared import get_or_create_settings, to_response

router = APIRouter(prefix="/settings", tags=["settings"])

#settings/notification경로
@router.patch("/notification", response_model=SettingsResponse)
def update_notification_toggle(
    payload: NotificationToggleRequest,
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """설정 화면 - '전체 알림 수신' 토글 버튼."""
    settings_row = get_or_create_settings(db, user.internal_id)

    if payload.notification_enabled and not settings_row.notification_enabled:
        # 꺼짐 -> 켜짐: 미션 '알림지기'(90일 유지) 카운트를 지금부터 새로 시작
        settings_row.notification_enabled_since = datetime.now(timezone.utc)
    elif not payload.notification_enabled:
        # 켜짐 -> 꺼짐(또는 이미 꺼짐): 유지 기록 리셋
        settings_row.notification_enabled_since = None

    settings_row.notification_enabled = payload.notification_enabled
    db.commit()
    db.refresh(settings_row)
    return to_response(settings_row)
