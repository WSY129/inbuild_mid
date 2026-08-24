"""
미션/등급 기능이 쓰는 새 테이블 2개의 설계도.
donation_records와 마찬가지로 이 백엔드 자체 DB(home_settings.db)에 저장되고,
회원가입팀의 blood_link.db와는 무관하다.
"""
from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func

from app.database import Base
from app.services.mission_rules import MISSIONS, ACCOUNT

_ACCOUNT_MISSION_KEYS = tuple(m["key"] for m in MISSIONS if m["category"] == ACCOUNT)


class UserExp(Base):
    """
    사용자별 누적 EXP. 등급(BRONZE~MASTER)은 이 값 하나로 계산되므로
    별도 컬럼으로 저장하지 않고, 조회할 때마다 mission_rules.GRADE_THRESHOLDS로 계산한다.
    """
    __tablename__ = "user_exp"

    user_internal_id = Column(Integer, primary_key=True)  # = blood_link.db의 users.id
    total_exp = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MissionClaim(Base):
    """
    '완료' 버튼을 눌러 실제로 EXP를 지급받은 기록.

    계정형 미션은 mission_key당 이 테이블에 행이 최대 1개만 있어야 하고(중복 클레임 방지),
    반복형 미션은 조건을 다시 채울 때마다 새 행이 계속 쌓인다.
    이 테이블에 쌓인 행 개수가 곧 '지금까지 몇 번 클리어했는지'가 된다.
    """
    __tablename__ = "mission_claims"

    id = Column(Integer, primary_key=True, index=True)
    user_internal_id = Column(Integer, nullable=False, index=True)
    mission_key = Column(String, nullable=False, index=True)  # mission_rules.MISSIONS의 "key"
    claimed_at = Column(DateTime(timezone=True), server_default=func.now())

    # 계정형 미션(mission_key가 _ACCOUNT_MISSION_KEYS에 속함)에 한해서만
    # (user_internal_id, mission_key) 조합이 유일해야 한다 - 계정당 1번만 클레임 가능하기 때문.
    # 반복형은 조건을 다시 채울 때마다 새 행이 계속 쌓여야 하므로 이 제약에서 제외한다.
    # '완료' 버튼 연타로 같은 계정형 미션이 동시에 두 번 커밋되는 경쟁 상태를 DB 단에서 막는다
    # (앱 레벨 조회-후-삽입만으로는 두 요청이 동시에 조회를 통과할 수 있다).
    __table_args__ = (
        Index(
            "uq_account_mission_claim_once",
            "user_internal_id",
            "mission_key",
            unique=True,
            sqlite_where=mission_key.in_(_ACCOUNT_MISSION_KEYS),
        ),
    )