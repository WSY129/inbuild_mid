#헌혈 내역(기록) 화면 데이터를 저장할 테이블의 설계도

from sqlalchemy import Column, Integer, String, Date, Float, DateTime
from sqlalchemy.sql import func

from app.database import Base


class DonationRecord(Base):
    """
    유저가 '헌혈 내역 기록' 화면에서 직접 추가한 헌혈 기록.

    회원가입 때 입력한 last_donation_date/method(blood_link.db)와는 별개의 데이터다.
    이 테이블에 기록이 없는 유저는 아직 이 기능으로 아무것도 추가하지 않은 상태이고,
    그런 경우 홈 화면 D-day는 지금처럼 회원가입 정보를 그대로 쓴다 (app/routers/home/get_home.py 참고).
    """
    __tablename__ = "donation_records"

    id = Column(Integer, primary_key=True, index=True)
    user_internal_id = Column(Integer, nullable=False, index=True)  # = blood_link.db의 users.id
    donation_method = Column(String, nullable=False)  # 전혈 / 혈장성분헌혈 / 혈소판성분헌혈 등 (문자열 그대로 저장, 판정은 app/services/donation_method.py의 키워드 매칭이 담당)
    donation_date = Column(Date, nullable=False)
    location_name = Column(String, nullable=False)    # 지도에서 선택한 장소의 표시명 (지도 SDK 자체는 프론트 담당)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
