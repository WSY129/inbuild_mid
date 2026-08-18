#알림 재수신 횟수 설정 버튼 API
from fastapi import APIRouter, Depends, HTTPException, status
#HTTPException, status: 에러코드와 예외처리할 때 사용

from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.settings_schema import ResendCountUpdateRequest, SettingsResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.routers.settings._shared import get_or_create_settings, to_response

router = APIRouter(prefix="/settings", tags=["settings"])

#settings/resend-count경로
@router.patch("/resend-count", response_model=SettingsResponse)
def update_resend_count(
    payload: ResendCountUpdateRequest,
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """
    설정 화면 - '재수신 횟수' 드롭다운 버튼.
    알람 수신 주기가 '재수신하지않음'일 때는 비활성화 상태이므로 변경을 막는다.
    -> HTTPException 필요(아래 if문)
    """
    settings_row = get_or_create_settings(db, user.internal_id)

    if settings_row.frequency == "재수신하지않음":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="알람 수신 주기가 '재수신하지않음'일 때는 재수신 횟수를 설정할 수 없습니다.",
        )

    settings_row.resend_count = payload.resend_count
    db.commit()
    db.refresh(settings_row)
    return to_response(settings_row)
