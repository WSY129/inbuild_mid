"""헌혈 미션 리스트 화면의 '완료' 버튼 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.mission import ClaimMissionResponse
from app.schemas.user import SignupUser
from app.services.rate_limit import rate_limit
from app.services.donation_repository import list_donation_records
from app.services.mission_service import (
    get_donation_based_mission_progress,
    get_profile_completion_progress,
    get_habit_donation_progress,
    get_steady_heart_progress,
    get_quick_donation_progress,
    get_notification_keeper_progress,
    get_grade_info,
    COUNT_BASED_MISSION_KEYS,
)
from app.services.mission_rules import MISSIONS, ACCOUNT
from app.models.mission_progress import MissionClaim, UserExp
from app.models.user_settings import UserSettings

router = APIRouter(prefix="/missions", tags=["missions"])

_missions_by_key = {m["key"]: m for m in MISSIONS}


def _last_claimed_at(db: Session, user_internal_id: int, mission_key: str):
    claim = (
        db.query(MissionClaim)
        .filter(MissionClaim.user_internal_id == user_internal_id, MissionClaim.mission_key == mission_key)
        .order_by(MissionClaim.claimed_at.desc())
        .first()
    )
    return claim.claimed_at if claim else None


#[버튼: 미션 리스트 화면의 빨간 '완료' 버튼]
@router.post("/{mission_key}/claim", response_model=ClaimMissionResponse)
def claim_mission(
    mission_key: str,
    db: Session = Depends(get_db),
    user: SignupUser = Depends(rate_limit(max_calls=20, window_seconds=60)),
):
    if mission_key not in _missions_by_key:
        raise HTTPException(status_code=404, detail="존재하지 않는 미션입니다.")

    mission = _missions_by_key[mission_key]

    # 계정형은 평생 1번만 — 반복형은 이 체크를 건너뛰고 진행도 계산으로 판단한다.
    if mission["category"] == ACCOUNT:
        already_claimed = (
            db.query(MissionClaim)
            .filter(MissionClaim.user_internal_id == user.internal_id, MissionClaim.mission_key == mission_key)
            .first()
        )
        if already_claimed:
            raise HTTPException(status_code=400, detail="이미 완료한 미션입니다.")

    if mission_key == "good_start":
        progress = get_profile_completion_progress(user)
    elif mission_key == "habit_donation":
        records = list_donation_records(db, user.internal_id)
        progress = get_habit_donation_progress(records, _last_claimed_at(db, user.internal_id, mission_key))
    elif mission_key == "steady_heart":
        records = list_donation_records(db, user.internal_id)
        progress = get_steady_heart_progress(records, _last_claimed_at(db, user.internal_id, mission_key))
    elif mission_key == "quick_donation":
        records = list_donation_records(db, user.internal_id)
        progress = get_quick_donation_progress(
            records,
            _last_claimed_at(db, user.internal_id, mission_key),
            user.donationDate,
            user.donationMethod,
        )
    elif mission_key == "notification_keeper":
        user_settings = db.query(UserSettings).filter(UserSettings.user_internal_id == user.internal_id).first()
        progress = get_notification_keeper_progress(user_settings)
    elif mission_key in COUNT_BASED_MISSION_KEYS:
        records = list_donation_records(db, user.internal_id)
        progress = {p["key"]: p for p in get_donation_based_mission_progress(records)}[mission_key]
    else:
        raise HTTPException(status_code=400, detail="아직 지원하지 않는 미션입니다.")

    if not progress["is_ready_to_claim"]:
        raise HTTPException(status_code=400, detail="아직 조건을 채우지 못했습니다.")

    db.add(MissionClaim(
        user_internal_id=user.internal_id,
        mission_key=mission_key,
        evidence_id=progress.get("evidence_id"),  # 반복형만 값이 있음 (mission_progress.py 유니크 제약 참고)
    ))

    user_exp = db.query(UserExp).filter(UserExp.user_internal_id == user.internal_id).first()
    if user_exp is None:
        user_exp = UserExp(user_internal_id=user.internal_id, total_exp=mission["exp"])
        db.add(user_exp)
    else:
        # "읽어서 파이썬에서 더하고 다시 쓰기"(+=) 대신 DB가 원자적으로 계산하게 한다.
        # 같은 미션 중복 클레임은 위 유니크 제약이 막아주지만, 이 유저가 서로 다른 미션
        # 두 개를 정확히 동시에 클레임하는 경우는 그 제약에 안 걸리는데, += 방식이면
        # 두 요청이 같은 옛날 값을 읽어서 한쪽 지급이 덮어써질(유실될) 수 있다.
        db.query(UserExp).filter(UserExp.user_internal_id == user.internal_id).update(
            {UserExp.total_exp: UserExp.total_exp + mission["exp"]}
        )

    try:
        db.commit()
    except IntegrityError:
        # 계정형은 같은 미션을, 반복형은 같은 헌혈 기록(evidence_id)을 두 요청이 거의 동시에
        # 클레임하면 둘 다 위의 already_claimed/진행도 조회를 통과할 수 있다 - 커밋 시점의
        # 유니크 제약(mission_progress.py 참고)이 최종 방어선이라 여기서 잡아 409로 돌려준다
        # (EXP 이중 지급 방지).
        db.rollback()
        raise HTTPException(status_code=409, detail="이미 완료한 미션입니다.")

    db.refresh(user_exp)  # 위 원자적 update()는 세션의 user_exp 객체를 자동으로 갱신하지 않는다

    return {
        "claimed_mission": mission_key,
        "gained_exp": mission["exp"],
        "grade_info": get_grade_info(user_exp.total_exp),
    }