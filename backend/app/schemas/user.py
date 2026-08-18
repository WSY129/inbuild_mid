from typing import Optional
from pydantic import BaseModel


class SignupUser(BaseModel):
    """
    회원가입팀이 보내준 필드명 그대로 매핑.

    ⚠️ id(로그인 아이디)는 회원 정보 수정 화면에서 사용자가 직접 바꿀 수 있는 값이다.
       이 백엔드가 알림 설정을 저장할 때는 절대 이 값을 키로 쓰면 안 되고,
       변하지 않는 internal_id(users.id)를 써야 한다.
    """
    internal_id: int                    # users.id (INTEGER PK) - 불변, 우리 쪽 저장 키
    id: str                             # users.user_id (로그인 아이디) - 사용자가 변경 가능
    nickname: str
    bloodType: str                      # A / B / O / AB
    rhType: str                         # Rh+ / Rh- / 모름
    birthdate: str
    donationDate: Optional[str] = None      # 최근 헌혈일, "YYYY-MM-DD" 가정
    donationMethod: Optional[str] = None    # 전혈 / 혈장성분헌혈 / 혈소판성분헌혈 / 혈소판혈장성분헌혈 / 모름
