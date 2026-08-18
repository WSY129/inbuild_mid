from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers.home import get_home
from app.routers.settings import (
    get_settings,
    update_notification_toggle,
    update_sensitivity,
    update_frequency,
    update_resend_count,
)

# 로컬 SQLite 테이블 생성 (알림 설정 등 - 회원가입 정보는 여기서 저장하지 않음)
Base.metadata.create_all(bind=engine)

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


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
