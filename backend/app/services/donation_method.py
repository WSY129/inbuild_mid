"""
헌혈 방식 문자열 판정 로직.

원래 app/routers/home/get_home.py에 있었는데, app/services/mission_service.py와
app/schemas/donation_record.py(입력 검증)에서도 같은 판정이 필요해서 서비스 계층으로 옮겼다.
(라우터 파일이 다른 라우터/스키마의 의존 대상이 되는 건 방향이 뒤집힌 구조라 여기로 이동)

같은 헌혈 방식을 팀마다 다르게 적고 있어서 문자열을 그대로 비교하면 안 된다.
  - 와이어프레임 Set_3 드롭다운: 전혈 / 혈소판 / 혈장 / 혈소판 혈장 / 헌혈 방식 모름
  - PRD 데이터 필드 정의표:      전혈 / 혈장성분헌혈 / 혈소판성분헌혈 / 혈소판혈장성분헌혈 / 모름
회원가입팀은 이 값을 검증 없이 저장하기 때문에 프론트가 보내는 라벨이 그대로 DB에 들어온다.
그래서 '성분헌혈' 접미사와 띄어쓰기를 무시하고 키워드로 판정한다.
(표기가 또 바뀌어도 여기만 보면 되도록 딕셔너리 대신 함수로 뺌 — README TODO 3번 참고,
 표기를 한쪽으로 강제 통일하지 않고 이쪽에서 흡수하기로 한 결정을 유지한다)
"""
from typing import Optional

# PRD 데이터 필드 정의표 기준: 전혈 +60일 / 성분헌혈(혈장·혈소판·혈소판혈장) +14일
WHOLE_BLOOD_INTERVAL_DAYS = 60
APHERESIS_INTERVAL_DAYS = 14


def resolve_donation_interval_days(donation_method: str) -> Optional[int]:
    """헌혈 방식 문자열 -> 다음 헌혈까지 필요한 간격(일). 모르는 값이면 None."""
    normalized = "".join(donation_method.split())  # 모든 공백 제거: "혈소판 혈장" == "혈소판혈장"

    if "모름" in normalized:
        return None
    if "전혈" in normalized:
        return WHOLE_BLOOD_INTERVAL_DAYS
    if "혈소판" in normalized or "혈장" in normalized:
        return APHERESIS_INTERVAL_DAYS
    return None  # 처음 보는 표기 - 틀린 D-day를 보여주느니 '정보 없음'으로 둔다


def is_recognized_donation_method(donation_method: str) -> bool:
    """
    '헌혈 내역 기록' 화면(POST /donations)의 입력 검증용.
    이미 끝난 헌혈을 기록하는 화면이라 '모름'은 유효한 값이 아니고,
    위 함수가 간격을 계산할 수 있는 값(=우리가 아는 표기)만 통과시킨다.
    (전체 문자열을 자유 입력으로 두면 오타/처음 보는 표기가 조용히 '정보 없음'으로
     빠져서 홈 화면 D-day가 깨지므로, 여기서 먼저 걸러낸다)
    """
    return resolve_donation_interval_days(donation_method) is not None
