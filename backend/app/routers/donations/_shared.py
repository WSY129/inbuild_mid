"""
헌혈 내역(기록) 화면의 버튼 파일들이 공통으로 쓰는 헬퍼.
버튼 파일 자체는 아니므로 라우터를 등록하지 않음.
"""
from app.models.donation_record import DonationRecord
from app.schemas.donation_record import DonationRecordResponse


#DB 안의 객체를 DonationRecordResponse로 변환하는 헬퍼 -> 앱 화면에 보여줄 수 있는 형태로 변환
def to_response(record: DonationRecord) -> DonationRecordResponse:
    return DonationRecordResponse(
        id=record.id,
        donation_method=record.donation_method,
        donation_method_code=record.donation_method_code,
        donation_date=record.donation_date,
        location_name=record.location_name,
        latitude=record.latitude,
        longitude=record.longitude,
    )
