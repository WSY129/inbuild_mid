"""
실제 푸시 발송(FCM)을 위한 디바이스 토큰 저장 테이블.

프론트가 FCM SDK로 발급받은 토큰을 로그인 직후 POST /settings/device-token으로 등록하고,
로그아웃 시 DELETE /settings/device-token으로 해제한다 (app/routers/settings 참고).
"""
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func

from app.database import Base


class DeviceToken(Base):
    """
    한 유저가 여러 기기(폰 교체, 웹+앱 동시 사용 등)를 가질 수 있어 유저당 여러 행이 가능하다.
    token 자체는 기기/앱 설치 단위로 FCM이 발급하므로 전역적으로 유일하다 - 같은 토큰으로
    다른 유저가 다시 등록하면(기기 재사용, 로그인 계정 전환) 기존 행의 소유자를 갱신한다
    (register_device_token.py의 upsert 로직 참고).
    """
    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_internal_id = Column(Integer, nullable=False, index=True)  # = blood_link.db의 users.id
    token = Column(String, nullable=False, unique=True, index=True)
    platform = Column(String, nullable=True)  # ios / android / web (프론트가 보내는 값 그대로 저장, 검증 안 함)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
