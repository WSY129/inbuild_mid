#미션/등급 화면 라우터가 참조하는 응답 pydantic 스키마
from typing import List, Optional

from pydantic import BaseModel


class GradeInfo(BaseModel):
    grade: str
    total_exp: int
    exp_to_next_grade: Optional[int]
    progress_ratio: float


class MissionProgress(BaseModel):
    key: str
    name: str
    category: str
    current: int
    target: int
    is_ready_to_claim: bool


class MissionsResponse(BaseModel):
    grade_info: GradeInfo
    missions: List[MissionProgress]


class ClaimMissionResponse(BaseModel):
    claimed_mission: str
    gained_exp: int
    grade_info: GradeInfo
