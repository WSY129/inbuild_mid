#전체 알림 수신 토글 버튼 API
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
    settings_row.notification_enabled = payload.notification_enabled
    db.commit()
    db.refresh(settings_row)
    return to_response(settings_row)
