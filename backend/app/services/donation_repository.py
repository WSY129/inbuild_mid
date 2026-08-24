"""
donation_records 테이블(이 백엔드가 직접 소유) 조회/저장 헬퍼.

app/routers/donations/*.py(내역 조회·추가 화면)와
app/routers/home/get_home.py(D-day 계산)가 공통으로 사용한다.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.donation_record import DonationRecord
from app.services.donation_method import resolve_donation_method_code


def list_donation_records(db: Session, user_internal_id: int) -> List[DonationRecord]:
    """
    미션 진행도 계산용 (총 헌혈 횟수, 방문 장소 수 등을 세려면 전체 기록이 필요하다).
    최근 헌혈일이 앞에 오도록 최신순 정렬. 개수 제한이 없으므로 화면에 그대로 노출하는
    용도로는 쓰지 말 것 - 조회 화면(GET /donations)은 list_donation_records_page를 쓴다.
    """
    return (
        db.query(DonationRecord)
        .filter(DonationRecord.user_internal_id == user_internal_id)
        .order_by(DonationRecord.donation_date.desc())
        .all()
    )


def list_donation_records_page(
    db: Session, user_internal_id: int, limit: int, offset: int
) -> List[DonationRecord]:
    """헌혈 내역 조회 화면(GET /donations)용. 최신순으로 limit/offset만큼만 가져온다."""
    return (
        db.query(DonationRecord)
        .filter(DonationRecord.user_internal_id == user_internal_id)
        .order_by(DonationRecord.donation_date.desc())
        .offset(offset)
        .limit(limit)
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
    # 스키마 검증(DonationRecordCreate.reject_unrecognized_method)을 이미 통과한 값이라
    # 여기서 코드가 없을 일은 없지만, "None을 조용히 저장"하는 대신 명시적으로 막아둔다
    # (assert 대신 예외를 쓰는 이유는 app/services/blood_predictor.py 참고).
    method_code = resolve_donation_method_code(donation_method)
    if method_code is None:
        raise ValueError(f"헌혈 방식 코드를 판정할 수 없습니다: {donation_method!r}")

    record = DonationRecord(
        user_internal_id=user_internal_id,
        donation_method=donation_method,
        donation_method_code=method_code.value,
        donation_date=donation_date,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
