#혈액 알림 민감도 설정 버튼 API
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.settings_schema import SensitivityUpdateRequest, SettingsResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.routers.settings._shared import get_or_create_settings, to_response

router = APIRouter(prefix="/settings", tags=["settings"])

#settings/sensitivity경로
@router.patch("/sensitivity", response_model=SettingsResponse)
def update_sensitivity(
    payload: SensitivityUpdateRequest,
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """설정 화면 - '혈액 알림 민감도' 드롭다운 버튼. (민감→주의, 보통→경계, 둔함→심각 기준으로 알림 발송)"""
    settings_row = get_or_create_settings(db, user.internal_id)
    settings_row.sensitivity = payload.sensitivity
    db.commit()
    db.refresh(settings_row)
    return to_response(settings_row)
