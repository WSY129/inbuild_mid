#헌혈 내역(기록) 화면 라우터가 참조하는 요청/응답 pydantic 스키마
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.services.donation_method import is_recognized_donation_method


class DonationRecordCreate(BaseModel):
    """
    '헌혈 내역 기록' 화면(방식+날짜 드롭다운) + 장소 선택 화면에서 '확인'을 누르면 보내는 데이터.

    donation_date: 프론트의 년/월/일 드롭다운 값을 "YYYY-MM-DD" 문자열로 합쳐서 보내면 된다
                    (예: "2026-01-05"). pydantic이 자동으로 date로 변환/검증한다.
    donation_method: 전혈 / 혈장성분헌혈 / 혈소판성분헌혈 등. app/services/donation_method.py의
                      키워드 판정 로직이 공백/접미사 표기 차이(와이어프레임 vs PRD)를 흡수하므로
                      값 형식 자체를 하나로 강제하진 않지만, 그 판정 로직이 아예 모르는 문자열
                      (오타, "모름" 등)은 여기서 422로 막는다 — 안 막으면 홈 화면 D-day가
                      조용히 "정보 없음"으로 빠진다.
    latitude/longitude: 지도에서 좌표까지 짚었으면 같이 보내고, 없으면 생략 가능.
    """
    donation_method: str = Field(min_length=1, max_length=50)
    donation_date: date
    location_name: str = Field(min_length=1, max_length=100)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @field_validator("donation_method")
    @classmethod
    def reject_unrecognized_method(cls, value: str) -> str:
        value = value.strip()
        if not is_recognized_donation_method(value):
            raise ValueError(
                "인식할 수 없는 헌혈 방식입니다. (전혈 / 혈장성분헌혈 / 혈소판성분헌혈 / 혈소판혈장성분헌혈 중 하나여야 합니다)"
            )
        return value

    #헌혈 기록은 '이미 한 헌혈'을 남기는 것이므로 미래 날짜는 받지 않는다.
    #프론트 년/월/일 드롭다운에서 올해 이후를 고를 수 있으면 여기서 422로 걸린다.
    #(막지 않으면 홈 화면 D-day가 아직 하지도 않은 헌혈 기준으로 계산돼버린다)
    @field_validator("donation_date")
    @classmethod
    def reject_future_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("헌혈일은 오늘 이후 날짜로 입력할 수 없습니다.")
        return value


class DonationRecordResponse(BaseModel):
    id: int
    donation_method: str
    donation_date: date
    location_name: str
    latitude: Optional[float]
    longitude: Optional[float]
