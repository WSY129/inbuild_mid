#알림 수신 주기 설정 버튼 API
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.settings_schema import FrequencyUpdateRequest, SettingsResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.routers.settings._shared import get_or_create_settings, to_response

router = APIRouter(prefix="/settings", tags=["settings"])

#patch: 기존 데이터 일부만 수정
#settings/frequency경로
@router.patch("/frequency", response_model=SettingsResponse)
def update_frequency(
    payload: FrequencyUpdateRequest,    #클라이언트가 보낸 데이터
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """
    설정 화면 - '알람 수신 주기' 드롭다운 버튼.
    '재수신하지않음'을 선택하면 재수신 횟수는 자동 비활성화(None)된다 (PRD 데이터 필드 정의표 규칙).
    """
    settings_row = get_or_create_settings(db, user.internal_id)  #_shared.py의 헬퍼를 통해 DB에서 조회, 없으면 기본값 생성
    settings_row.frequency = payload.frequency  # 클라이언트가 보낸 수신주기 값으로 업데이트

    if payload.frequency == "재수신하지않음":
        settings_row.resend_count = None
    elif settings_row.resend_count is None:
        settings_row.resend_count = 3  # 다시 활성화될 때 기본값 복구

    db.commit()     #DB에 확정저장
    db.refresh(settings_row)    #DB가 채워준 값 최신상태로 파이썬 객체에 동기화
    return to_response(settings_row)    #클라이언트에게 보여줄 수 있는 형태로 변환하여 반환
