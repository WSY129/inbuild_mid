#푸시 알림 수신용 디바이스 토큰 등록 (로그인 직후 프론트가 호출)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device_token import DeviceToken
from app.schemas.settings_schema import DeviceTokenRequest
from app.schemas.user import SignupUser
from app.services.auth import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


#settings/device-token경로
@router.post("/device-token", status_code=204)
def register_device_token(
    payload: DeviceTokenRequest,
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    """
    프론트가 FCM SDK로 발급받은 토큰을 등록한다.
    token은 전역 유일(테이블 유니크 제약)이므로, 이미 등록된 토큰이면(기기 재사용 또는
    같은 기기에서 계정 전환) 소유자를 현재 유저로 갱신하는 upsert로 처리한다.
    """
    existing = db.query(DeviceToken).filter(DeviceToken.token == payload.token).first()
    if existing is not None:
        existing.user_internal_id = user.internal_id
        existing.platform = payload.platform
    else:
        db.add(
            DeviceToken(
                user_internal_id=user.internal_id,
                token=payload.token,
                platform=payload.platform,
            )
        )
    db.commit()
