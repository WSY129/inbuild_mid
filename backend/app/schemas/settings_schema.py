#설정 관련 라우터가 공통으로 참조하는 요청/응답 데이터 계약 한번에 정리해둔 pydantic 스키마
from typing import Optional, Literal
from pydantic import BaseModel, Field

Sensitivity = Literal["민감", "보통", "둔함"]
Frequency = Literal["1", "2", "3", "7", "14", "재수신하지않음"]


class SettingsResponse(BaseModel):
    notification_enabled: bool
    sensitivity: Sensitivity
    frequency: Frequency
    resend_count: Optional[int]


class NotificationToggleRequest(BaseModel):
    notification_enabled: bool


class SensitivityUpdateRequest(BaseModel):
    sensitivity: Sensitivity


class FrequencyUpdateRequest(BaseModel):
    frequency: Frequency


class ResendCountUpdateRequest(BaseModel):
    resend_count: int = Field(ge=1, le=5)
