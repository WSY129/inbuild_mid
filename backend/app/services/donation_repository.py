"""
donation_records 테이블(이 백엔드가 직접 소유) 조회/저장 헬퍼.

app/routers/donations/*.py(내역 조회·추가 화면)와
app/routers/home/get_home.py(D-day 계산)가 공통으로 사용한다.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.donation_record import DonationRecord


def list_donation_records(db: Session, user_internal_id: int) -> List[DonationRecord]:
    """헌혈 내역 조회 화면용. 최근 헌혈일이 앞에 오도록 최신순 정렬."""
    return (
        db.query(DonationRecord)
        .filter(DonationRecord.user_internal_id == user_internal_id)
        .order_by(DonationRecord.donation_date.desc())
        .all()
    )


def get_latest_donation_record(db: Session, user_internal_id: int) -> Optional[DonationRecord]:
    """
    홈 화면 D-day 계산용. 이 유저의 기록 중 '실제 헌혈일'이 가장 최근인 것 1건.
    (등록한 순서가 아니라 donation_date 기준 — 지난 헌혈을 뒤늦게 입력해도
     이미 더 최근 헌혈 기록이 있으면 D-day가 그걸로 유지되도록 하기 위함)
    기록이 하나도 없으면 None (호출한 쪽에서 회원가입 정보로 폴백).
    """
    return (
        db.query(DonationRecord)
        .filter(DonationRecord.user_internal_id == user_internal_id)
        .order_by(DonationRecord.donation_date.desc())
        .first()
    )


def create_donation_record(
    db: Session,
    user_internal_id: int,
    donation_method: str,
    donation_date: date,
    location_name: str,
    latitude: Optional[float],
    longitude: Optional[float],
) -> DonationRecord:
    record = DonationRecord(
        user_internal_id=user_internal_id,
        donation_method=donation_method,
        donation_date=donation_date,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
