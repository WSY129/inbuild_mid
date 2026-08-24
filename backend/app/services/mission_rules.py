"""
엑셀(헌혈_미션_등급_시스템.xlsx)에 정리된 미션·등급 기준을 코드 상수로 옮긴 파일.
이 파일은 순수 데이터만 담고 있고, DB나 다른 서비스에 의존하지 않는다.
실제 판정 로직(진행도 계산 등)은 이후 단계의 mission_service.py가 이 데이터를 참조해서 처리한다.
"""

# 미션 구분: "반복" = 조건 충족 시 무한 클리어 가능, "계정" = 계정당 1회만 클리어 가능
REPEAT = "반복"
ACCOUNT = "계정"

MISSIONS = [
    # ── 반복형 ──────────────────────────────────────────────
    {
        "key": "habit_donation",
        "category": REPEAT,
        "name": "헌혈을 습관으로!",
        "condition": "헌혈 1회 수행",
        "target_count": 1,
        "exp": 100,
    },
    {
        "key": "quick_donation",
        "category": REPEAT,
        "name": "속전속결",
        "condition": "헌혈 가능일 도래 후 1주일 내 헌혈 수행",
        "target_count": 1,
        "exp": 200,
    },
    {
        "key": "faceless_savior",
        "category": REPEAT,
        "name": "얼굴없는 구원자",
        "condition": "혈액 부족 알림 수신 후 1주일 내 헌혈 수행",
        "target_count": 1,
        "exp": 300,
    },
    {
        "key": "steady_heart",
        "category": REPEAT,
        "name": "꾸준한 마음",
        "condition": "1년 안에 3회 헌혈 수행",
        "target_count": 3,
        "exp": 500,
    },
    {
        "key": "blood_type_hero",
        "category": REPEAT,
        "name": "혈액형 히어로",
        "condition": "본인 혈액형이 부족 단계일 때 헌혈 수행",
        "target_count": 1,
        "exp": 400,
        "note": "적십자사 기준 위기단계: 부족 이상일 때 조건 충족. AI팀 위험단계 판정 완료 후 구현 가능(README TODO 참고).",
    },
    {
        "key": "seasonal_guardian",
        "category": REPEAT,
        "name": "계절의 파수꾼",
        "condition": "방학·명절 등 헌혈 감소 시기에 헌혈 수행",
        "target_count": 1,
        "exp": 300,
        "note": "여름/겨울방학(7~9월, 12~2월) + 추석·설날. 명절은 매년 날짜가 바뀌므로 연도별 날짜표 필요.",
    },
    # ── 계정형 ──────────────────────────────────────────────
    {"key": "first_step", "category": ACCOUNT, "name": "첫 발걸음", "condition": "첫 헌혈 수행", "target_count": 1, "exp": 100},
    {"key": "habituation", "category": ACCOUNT, "name": "습관화", "condition": "누적 헌혈 3회 수행", "target_count": 3, "exp": 500},
    {"key": "familiarity", "category": ACCOUNT, "name": "익숙함", "condition": "누적 헌혈 5회 수행", "target_count": 5, "exp": 700},
    {"key": "steadfastness", "category": ACCOUNT, "name": "우직함", "condition": "누적 헌혈 10회 수행", "target_count": 10, "exp": 1000},
    {"key": "unwavering_heart", "category": ACCOUNT, "name": "일편단심", "condition": "누적 헌혈 15회 수행", "target_count": 15, "exp": 2000},
    {"key": "selfless_devotion", "category": ACCOUNT, "name": "살신성인", "condition": "누적 헌혈 20회 수행", "target_count": 20, "exp": 3000},
    {
        "key": "all_rounder",
        "category": ACCOUNT,
        "name": "올라운더",
        "condition": "모든 헌혈 방식으로 1회씩 헌혈 수행",
        "target_count": 4,  # 전혈/혈장/혈소판/혈소판혈장 4종
        "exp": 1000,
    },
    {
        "key": "wanderer",
        "category": ACCOUNT,
        "name": "떠나는 발걸음",
        "condition": "3곳 이상의 헌혈의 집에서 헌혈 수행",
        "target_count": 3,
        "exp": 500,
    },
    {
        "key": "problem_solver",
        "category": ACCOUNT,
        "name": "해결사",
        "condition": "혈액 수급 위기단계가 심각 단계일 때 헌혈 완료",
        "target_count": 1,
        "exp": 1000,
        "note": "AI팀 위험단계 판정 완료 후 구현 가능.",
    },
    {
        "key": "good_start",
        "category": ACCOUNT,
        "name": "시작이 반이다",
        "condition": "사용자 정보(혈액형, 헌혈이력 등) 100% 입력 완료",
        "target_count": 1,
        "exp": 100,
    },
    {
        "key": "notification_keeper",
        "category": ACCOUNT,
        "name": "알림지기",
        "condition": "알림 활성화 상태 90일 유지",
        "target_count": 90,
        "exp": 1000,
        "note": "user_settings에 '언제부터 켜져 있었는지' 시각 필드가 아직 없음 — 추가 필요.",
    },
]

# 전혈은 미션 카운트에서 2회로 취급 (회복 기간이 4배 길기 때문)
WHOLE_BLOOD_COUNT_MULTIPLIER = 2

# 등급 시스템: 누적 EXP 기준 (마지막 MASTER는 자동 계산 대상이 아니라 별도 MVP 기준)
GRADE_THRESHOLDS = [
    ("BRONZE", 500),
    ("SILVER", 1500),
    ("GOLD", 4500),
    ("PLATINUM", 9500),
    ("DIAMOND", 19500),
]
FINAL_GRADE = "MASTER"  # DIAMOND 이후, MVP 기준 별도 부여 (자동 계산 X)