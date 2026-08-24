# Alembic이 autogenerate로 스키마 변경을 감지하려면 모든 모델 클래스가 import돼서
# Base.metadata에 등록된 상태여야 한다 (migrations/env.py가 이 패키지를 import한다).
from app.models import donation_record, mission_progress, user_settings  # noqa: F401
