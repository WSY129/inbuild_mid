"""
예측 기반 알림(부족 경보) 배치가 유저별 발송 이력을 추적하는 테이블.
설정 화면의 frequency(재수신 주기)/resend_count(재수신 횟수)를 지키려면 "지금 경보가
진행 중인지", "마지막으로 언제 보냈는지", "이번 경보에서 몇 번 보냈는지"를 기억해야 한다
(app/services/notification_batch.py 참고).
"""
from sqlalchemy import Column, Integer, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base


class NotificationState(Base):
    """
    유저당 1행. 혈액형은 바뀌지 않고(회원 정보 수정 화면에 없음) 유저당 하나이므로
    혈액형별로 나눌 필요가 없다.
    """
    __tablename__ = "notification_state"

    user_internal_id = Column(Integer, primary_key=True)  # = blood_link.db의 users.id
    alert_active = Column(Boolean, nullable=False, default=False)  # 현재 '부족 경보' 상태가 이어지는 중인지
    sent_count = Column(Integer, nullable=False, default=0)  # 이번 경보에서 지금까지 보낸 횟수
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
