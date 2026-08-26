#푸시 알림 수신용 디바이스 토큰 해제 (로그아웃 시 프론트가 호출)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device_token import DeviceToken
from app.schemas.settings_schema import DeviceTokenRequest
from app.schemas.user import SignupUser
from app.services.auth import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


#settings/device-token경로
@router.delete("/device-token", status_code=204)
def unregister_device_token(
    payload: DeviceTokenRequest,
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """
    로그아웃 시 이 기기로의 발송을 멈춘다.
    다른 유저 소유의 토큰을 지우지 못하도록 user_internal_id도 함께 필터링한다
    (README "인가" 원칙과 동일하게, 항상 토큰으로 조회한 본인 데이터만 건드린다).
    없는 토큰이거나 이미 다른 유저 소유로 바뀐 토큰이어도 조용히 204로 끝낸다 -
    로그아웃 흐름에서 "지울 게 이미 없음"은 에러가 아니다.
    """
    db.query(DeviceToken).filter(
        DeviceToken.token == payload.token,
        DeviceToken.user_internal_id == user.internal_id,
    ).delete()
    db.commit()
