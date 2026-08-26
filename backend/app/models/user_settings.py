#설정 화면 내의 데이터를 저장할 테이블의 설계도

from sqlalchemy import Column, String, Boolean, Integer, DateTime
from sqlalchemy.sql import func
#파이썬 내에서 SQL문자열을 쓰지 않고 ORM을 통해 DB를 다루기 위해 SQLAlchemy를 사용

from app.database import Base
#모든 테이블 클래스는 base를 상속해야 이 클래스가 진짜 테이블인줄로 인식


class UserSettings(Base):
    """
    설정 화면 데이터.

    기본키는 blood_link.db의 `users.id`(INTEGER AUTOINCREMENT)를 그대로 쓴다.
    ⚠️ 로그인 아이디(users.user_id)를 키로 쓰면 안 된다. 회원 정보 수정 화면에서
       사용자가 아이디를 바꾸면 그 사용자의 알림 설정이 통째로 미아가 되고,
       다음 요청에서 기본값 행이 새로 생겨버린다. users.id는 변하지 않으므로 안전하다.
    """
    __tablename__ = "user_settings"

    user_internal_id = Column(Integer, primary_key=True, index=True)  # = users.id
    notification_enabled = Column(Boolean, nullable=False, default=True)
    notification_enabled_since = Column(DateTime(timezone=True), nullable=True)  # 마지막으로 '켬'으로 바뀐 시각. 꺼지면 None (미션 '알림지기' 판정용 - mission_service.py 참고)
    sensitivity = Column(String, nullable=False, default="보통")       # 민감 / 보통 / 둔함
    frequency = Column(String, nullable=False, default="3")            # 1/2/3/7/14/재수신하지않음
    resend_count = Column(Integer, nullable=True, default=3)           # 1~5, frequency가 '재수신하지않음'이면 None
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
