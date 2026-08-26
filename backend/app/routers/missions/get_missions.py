"""헌혈 미션 리스트 화면 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.mission import MissionsResponse
from app.schemas.user import SignupUser
from app.services.auth import get_current_user
from app.services.donation_repository import list_donation_records
from app.services.mission_service import (
    get_grade_info,
    get_donation_based_mission_progress,
    get_profile_completion_progress,
    get_habit_donation_progress,
    get_steady_heart_progress,
    get_quick_donation_progress,
    get_notification_keeper_progress,
)
from app.models.mission_progress import UserExp, MissionClaim
from app.models.user_settings import UserSettings

router = APIRouter(prefix="/missions", tags=["missions"])


def _last_claimed_at(db: Session, user_internal_id: int, mission_key: str):
    claim = (
        db.query(MissionClaim)
        .filter(MissionClaim.user_internal_id == user_internal_id, MissionClaim.mission_key == mission_key)
        .order_by(MissionClaim.claimed_at.desc())
        .first()
    )
    return claim.claimed_at if claim else None


#[버튼: 홈 화면 → 미션 리스트 화면 진입]
@router.get("", response_model=MissionsResponse)
def get_missions(
    db: Session = Depends(get_db),
    user: SignupUser = Depends(get_current_user),
):
    user_exp = db.query(UserExp).filter(UserExp.user_internal_id == user.internal_id).first()
    total_exp = user_exp.total_exp if user_exp else 0

    records = list_donation_records(db, user.internal_id)
    user_settings = db.query(UserSettings).filter(UserSettings.user_internal_id == user.internal_id).first()

    return {
        "grade_info": get_grade_info(total_exp),
        "missions": (
            get_donation_based_mission_progress(records)
            + [get_profile_completion_progress(user)]
            + [get_habit_donation_progress(records, _last_claimed_at(db, user.internal_id, "habit_donation"))]
            + [get_steady_heart_progress(records, _last_claimed_at(db, user.internal_id, "steady_heart"))]
            + [get_quick_donation_progress(
                records,
                _last_claimed_at(db, user.internal_id, "quick_donation"),
                user.donationDate,
                user.donationMethod,
            )]
            + [get_notification_keeper_progress(user_settings)]
        ),
    }