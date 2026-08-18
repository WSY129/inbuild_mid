#설정값 조회용 API
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
#get_db: FastAPI의 Depends로 주입되는 헬퍼. DB 세션을 생성하고, 요청이 끝나면 세션을 종료하는 역할

from app.schemas.settings_schema import SettingsResponse
from app.schemas.user import SignupUser
#schemas 파일에 있는 settings_schema.py, user.py에서 정의한 Pydantic 모델을 import

from app.services.auth import get_current_user
#사용자 검증용 헬퍼 -> 남의 설정값을 조회 못하게 토큰검증

from app.routers.settings._shared import get_or_create_settings, to_response

router = APIRouter(prefix="/settings", tags=["settings"])
#이 라우터 내부의 모든 엔드포인트는 /settings로 시작, Swagger UI에서 settings라는 그룹으로 묶임

@router.get("", response_model=SettingsResponse)    #/settings 뒤에 추가 경로 붙지 않음
def get_settings(
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """설정 화면 진입 시 현재 값(알림 수신 동의, 민감도, 수신 주기, 재수신 횟수) 조회."""
    settings_row = get_or_create_settings(db, user.internal_id)
    return to_response(settings_row)
