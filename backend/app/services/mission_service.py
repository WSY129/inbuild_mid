"""
등급 계산 로직. 사용자의 누적 EXP(app.models.mission_progress.UserExp.total_exp)를 받아
현재 등급, 다음 등급까지 남은 EXP, 진행률을 계산한다.
"""
from app.services.mission_rules import GRADE_THRESHOLDS, FINAL_GRADE, MISSIONS, WHOLE_BLOOD_COUNT_MULTIPLIER
from app.services.donation_method import resolve_donation_interval_days
from datetime import datetime, timedelta, timezone


def get_grade_info(total_exp: int) -> dict:
    """
    등급 시스템은 구간별이 아니라 '누적' 기준이다.
    예: 300exp → BRONZE 구간(0~500) 안에 있고, SILVER까지 200 남음.
    19500(DIAMOND 상한) 이상이면 MASTER (MVP 심사 대상이라 자동으로는 다음 단계 계산 안 함).
    """
    floor = 0
    for grade_name, ceiling in GRADE_THRESHOLDS:
        if total_exp < ceiling:
            return {
                "grade": grade_name,
                "total_exp": total_exp,
                "exp_to_next_grade": ceiling - total_exp,
                "progress_ratio": (total_exp - floor) / (ceiling - floor),
            }
        floor = ceiling

    return {
        "grade": FINAL_GRADE,
        "total_exp": total_exp,
        "exp_to_next_grade": None,
        "progress_ratio": 1.0,
    }


# ── 미션 진행도 계산 (헌혈 기록 기반, 계정형 8개) ──────────────────────────

def _normalize_method(donation_method: str) -> str:
    return donation_method.replace(" ", "").replace("성분헌혈", "").replace("성분", "")


def _donation_count(records) -> int:
    """전혈은 2회로 카운트해서 합산한 총 헌혈 횟수."""
    total = 0
    for r in records:
        total += WHOLE_BLOOD_COUNT_MULTIPLIER if _normalize_method(r.donation_method) == "전혈" else 1
    return total


# 헌혈 기록(donation_records)의 총 횟수만으로 진행도를 계산할 수 있는 계정형 미션들.
COUNT_BASED_MISSION_KEYS = {
    "first_step": lambda records: _donation_count(records),
    "habituation": lambda records: _donation_count(records),
    "familiarity": lambda records: _donation_count(records),
    "steadfastness": lambda records: _donation_count(records),
    "unwavering_heart": lambda records: _donation_count(records),
    "selfless_devotion": lambda records: _donation_count(records),
    "wanderer": lambda records: len({r.location_name for r in records}),
    "all_rounder": lambda records: len({_normalize_method(r.donation_method) for r in records}),
}


def get_donation_based_mission_progress(records) -> list:
    """
    헌혈 기록만으로 진행도를 계산할 수 있는 계정형 미션 8개의 현재 진행도.
    (반복형 미션, AI 위험단계/명절 날짜/알림 유지기간이 필요한 미션은 다음 단계에서 처리)
    """
    missions_by_key = {m["key"]: m for m in MISSIONS}
    result = []
    for key, counter in COUNT_BASED_MISSION_KEYS.items():
        mission = missions_by_key[key]
        current = counter(records)
        target = mission["target_count"]
        result.append({
            "key": key,
            "name": mission["name"],
            "category": mission["category"],
            "current": min(current, target),
            "target": target,
            "is_ready_to_claim": current >= target,
        })
    return result


# ── '시작이 반이다' 미션 (사용자 정보 100% 입력 완료) ──────────────────────

def get_profile_completion_progress(user) -> dict:
    """
    이미 인증 단계에서 받아온 SignupUser 객체의 필드만 보고 판정한다.
    blood_link.db를 다시 조회할 필요가 없다.
    '혈액형, 헌혈이력 등 정보 입력'을 닉네임/혈액형(ABO,Rh)/최근 헌혈일·방식 5개 항목으로 본다.
    """
    required_fields = [user.nickname, user.bloodType, user.rhType, user.donationDate, user.donationMethod]
    is_complete = all(bool(v) for v in required_fields)
    return {
        "key": "good_start",
        "name": "시작이 반이다",
        "category": "계정",
        "current": 1 if is_complete else 0,
        "target": 1,
        "is_ready_to_claim": is_complete,
    }



# ── '헌혈을 습관으로!' 미션 (반복형, 헌혈 1회 수행) ─────────────────────────

def get_habit_donation_progress(records, last_claimed_at) -> dict:
    """
    반복형 미션이라 '지금까지 총 몇 번 헌혈했나'로는 판정할 수 없다.
    마지막으로 이 미션을 클레임한 시각(last_claimed_at) 이후에 새로 등록된
    헌혈 기록이 하나라도 있으면 완료 가능. 한 번도 클레임한 적 없으면
    (last_claimed_at=None) 기록이 하나라도 있으면 완료 가능.
    """
    mission = next(m for m in MISSIONS if m["key"] == "habit_donation")

    if last_claimed_at is None:
        new_records = records
    else:
        new_records = [r for r in records if r.created_at > last_claimed_at]

    is_ready = len(new_records) > 0
    return {
        "key": "habit_donation",
        "name": mission["name"],
        "category": mission["category"],
        "current": 1 if is_ready else 0,
        "target": 1,
        "is_ready_to_claim": is_ready,
    }


# ── '꾸준한 마음' 미션 (반복형, 1년 안에 3회 헌혈 수행) ─────────────────────

def get_steady_heart_progress(records, last_claimed_at) -> dict:
    """
    마지막 클레임 이후 등록된 헌혈 기록들을 날짜순으로 봤을 때,
    연속된 3건의 donation_date 차이가 365일 이내인 묶음이 하나라도 있으면 완료 가능.
    (떨어진 3건이 1년 안에 들어온다면 그 사이 연속된 3건은 항상 그보다 더 촘촘하므로,
     정렬 후 연속된 3개씩만 확인하면 충분하다.)
    """
    mission = next(m for m in MISSIONS if m["key"] == "steady_heart")

    if last_claimed_at is None:
        candidates = records
    else:
        candidates = [r for r in records if r.created_at > last_claimed_at]

    dates = sorted(r.donation_date for r in candidates)

    is_ready = any(
        (dates[i + 2] - dates[i]).days <= 365
        for i in range(len(dates) - 2)
    )

    # 3건 이상 있어도 1년 조건을 못 채우면 '3/3'으로 잘못 보이지 않도록 2로 캡핑한다.
    current = 3 if is_ready else min(len(dates), 2)

    return {
        "key": "steady_heart",
        "name": mission["name"],
        "category": mission["category"],
        "current": current,
        "target": 3,
        "is_ready_to_claim": is_ready,
    }


# ── '속전속결' 미션 (반복형, 헌혈 가능일 도래 후 1주일 내 헌혈) ─────────────

def get_quick_donation_progress(records, last_claimed_at, fallback_donation_date, fallback_donation_method) -> dict:
    """
    donation_records를 날짜순으로 짚어가며, 각 기록의 '직전 헌혈'(이전 기록, 없으면
    회원가입 정보) 기준으로 헌혈 가능일을 계산하고, 그로부터 7일 안에 헌혈했는지 본다.
    마지막 클레임 이후 새로 등록된(created_at 기준) 기록에서만 조건을 찾는다.
    """
    mission = next(m for m in MISSIONS if m["key"] == "quick_donation")

    sorted_records = sorted(records, key=lambda r: r.donation_date)

    fallback_date = None
    if fallback_donation_date:
        fallback_date = datetime.strptime(fallback_donation_date, "%Y-%m-%d").date()

    is_ready = False
    for i, record in enumerate(sorted_records):
        if last_claimed_at is not None and record.created_at <= last_claimed_at:
            continue  # 마지막 클레임 이전에 등록된 기록은 이미 써먹은 것으로 본다

        if i == 0:
            prev_date, prev_method = fallback_date, fallback_donation_method
        else:
            prev = sorted_records[i - 1]
            prev_date, prev_method = prev.donation_date, prev.donation_method

        if not prev_date or not prev_method:
            continue  # 비교할 직전 헌혈 정보가 없음

        interval = resolve_donation_interval_days(prev_method)
        if interval is None:
            continue

        eligible_date = prev_date + timedelta(days=interval)
        if eligible_date <= record.donation_date <= eligible_date + timedelta(days=7):
            is_ready = True
            break

    return {
        "key": "quick_donation",
        "name": mission["name"],
        "category": mission["category"],
        "current": 1 if is_ready else 0,
        "target": 1,
        "is_ready_to_claim": is_ready,
    }



# ── '알림지기' 미션 (계정형, 알림 활성화 상태 90일 유지) ────────────────────

def get_notification_keeper_progress(user_settings) -> dict:
    """
    user_settings: app.models.user_settings.UserSettings 인스턴스 (아직 없으면 None -> 미완료).
    notification_enabled_since가 비어있어도(가입 시 기본값 True라 한 번도 토글 안 했을 수 있음)
    notification_enabled가 True면 created_at을 시작점으로 대신 쓴다.
    """
    mission = next(m for m in MISSIONS if m["key"] == "notification_keeper")
    target = mission["target_count"]

    if user_settings is None or not user_settings.notification_enabled:
        current_days = 0
    else:
        since = user_settings.notification_enabled_since or user_settings.created_at
        # SQLite는 DateTime(timezone=True) 컬럼도 tzinfo 없이 돌려준다 - aware로 맞춰준다
        # (안 하면 aware - naive 뺄셈에서 TypeError)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        current_days = max(0, (datetime.now(timezone.utc) - since).days)

    return {
        "key": "notification_keeper",
        "name": mission["name"],
        "category": mission["category"],
        "current": min(current_days, target),
        "target": target,
        "is_ready_to_claim": current_days >= target,
    }