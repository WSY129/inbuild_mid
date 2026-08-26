"""
환경변수 설정.
회원가입 서버(inbuild_mid)와 이 백엔드(홈/설정)는 별도의 두 서버로 배포된다.
프론트는 두 개의 API 주소를 나눠서 호출한다.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

 
class Settings(BaseSettings):
    # 회원가입팀의 blood_link.db를 읽기 전용으로 공유해서 사용자 프로필을 조회한다.
    # 이 백엔드와 같은 파일시스템(같은 서버 또는 공유 볼륨)에 두거나, 절대경로로 지정할 것.
    shared_db_path: str = "./blood_link.db"

    # 회원가입팀(inbuild_mid)이 로그인 시 토큰에 서명할 때 쓰는 키/알고리즘.
    # 같은 토큰을 이 백엔드가 검증하므로 두 서버의 값이 반드시 일치해야 한다.
    # 기본값을 두지 않아서, 값이 없으면 앱이 뜨는 시점에 바로 실패한다.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"

    # 이 백엔드가 직접 관리하는 로컬 데이터 (알림 설정 등) - blood_link.db와는 별도 파일
    database_url: str = "sqlite:///./home_settings.db"

    # 실제 푸시 발송(FCM)에 쓰는 Firebase 서비스 계정 키 JSON 파일 경로.
    # 비워두면 발송 시도 시 PushNotConfiguredError로 실패한다 (app/services/push_client.py).
    # 앱 기동 자체는 막지 않는다 - 이 키가 아직 없어도 나머지 API는 정상 동작해야 하므로.
    fcm_credentials_path: str = ""

    # 예측 기반 알림 배치(app/services/notification_scheduler.py)를 매일 실행할 시각(0~23, 서버 로컬 시간).
    notification_batch_hour: int = 9

    # FastAPI의 Pydantic 모델이 .env 파일을 읽도록 설정
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


