import sqlite3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.blood_predictor import get_blood_stock_predictions
from app.routers.home import get_home
from app.routers.settings import (
    get_settings,
    update_notification_toggle,
    update_sensitivity,
    update_frequency,
    update_resend_count,
)
from app.routers.donations import get_history, add_history
from app.routers.missions import get_missions, claim_mission

# 로컬 SQLite 테이블(알림 설정 등)은 이제 Alembic이 관리한다 (migrations/ 참고).
# create_all()은 기존 테이블에 새 컬럼/인덱스를 반영하지 못해서(=DB migration 도구
# 도입 전 겪었던 문제) 제거했다. 새로 이 프로젝트를 받으면 서버를 띄우기 전에
# `alembic upgrade head`를 먼저 실행해야 한다 (README "실행 방법" 참고).

app = FastAPI(title="헌혈 예측 알림 서비스 - 홈/설정 API")

# CORS: 프론트(다른 출처)에서 이 백엔드를 호출할 수 있게 허용.
# 이게 없으면 브라우저가 preflight(OPTIONS) 단계에서 요청을 차단한다.
# 프론트 개발 서버 주소가 바뀌면(포트 변경, 배포 등) 아래 목록에 추가할 것.
ALLOWED_ORIGINS = [
    "http://localhost:3000",    # React(CRA/Next.js) 기본 포트
    "http://127.0.0.1:3000",    # 같은 주소지만 브라우저는 별개 출처로 취급
    "http://localhost:5173",    # Vite 기본 포트
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],   # GET/PATCH/OPTIONS 등 전부 허용
    # X-User-Id는 표준 헤더가 아니라 직접 만든 헤더라, 여기서 허용하지 않으면
    # preflight에서 막힌다 (app/services/auth.py 참고).
    allow_headers=["*"],
)

#라우터 등록: 코드를 기능별 파일로 나눈 것을 여기서 한번에 모음
app.include_router(get_home.router)
app.include_router(get_settings.router)
app.include_router(update_notification_toggle.router)
app.include_router(update_sensitivity.router)
app.include_router(update_frequency.router)
app.include_router(update_resend_count.router)
app.include_router(get_history.router)
app.include_router(add_history.router)
app.include_router(get_missions.router)
app.include_router(claim_mission.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
def readiness_check():
    """
    /health와 달리 이 백엔드가 실제로 요청을 처리할 수 있는 상태인지 확인한다.
    - shared_db: 회원가입팀과 공유하는 blood_link.db에 읽기 전용으로 접근 가능한지
      (파일이 없거나 잠겨 있으면 모든 인증 요청이 실패하므로 배포 직후 확인용으로 유용하다)
    - ai_prediction_data: 예측용 CSV(app/services/blood_predictor.py)를 문제없이 읽을 수 있는지
      (최초 호출 시에만 계산하고 이후는 캐시를 그대로 쓰므로 비용이 거의 없다)
    로드밸런서/오케스트레이터가 이 엔드포인트로 "트래픽을 받아도 되는 상태인지" 판단하도록
    쓰는 용도라 /health(단순 생존 확인)와는 목적이 다르다.
    """
    checks = {}

    try:
        conn = sqlite3.connect(f"file:{settings.shared_db_path}?mode=ro", uri=True)
        try:
            conn.execute("SELECT 1 FROM users LIMIT 1")
        finally:
            conn.close()
        checks["shared_db"] = "ok"
    except Exception as exc:
        checks["shared_db"] = f"error: {exc}"

    try:
        get_blood_stock_predictions()
        checks["ai_prediction_data"] = "ok"
    except Exception as exc:
        checks["ai_prediction_data"] = f"error: {exc}"

    is_ready = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ok" if is_ready else "degraded", "checks": checks},
    )
