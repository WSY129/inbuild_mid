"""
FCM(Firebase Cloud Messaging)으로 실제 푸시를 발송하는 얇은 래퍼.

firebase-admin SDK가 서비스 계정 키(app/config.py의 fcm_credentials_path)로 인증한다.
이 키는 Firebase 콘솔에서 발급받아야 하는 값이라 저장소에 커밋하지 않고 .env로 경로만 지정한다
(.env.example 참고). 키가 아직 없는 환경(로컬 개발 등)에서도 앱 기동/나머지 API는 그대로
동작해야 하므로, SDK 초기화는 최초 발송 시점에 지연 실행한다.
"""
import logging
from typing import Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import settings

logger = logging.getLogger(__name__)

_app: Optional[firebase_admin.App] = None

# FCM이 "이 토큰은 더 이상 못 씀"이라고 알려주는 에러 코드.
# 이 경우에만 device_tokens에서 지운다 - 일시적 에러(QUOTA_EXCEEDED, UNAVAILABLE 등)까지
# 지우면 다음 배치에서 되살릴 방법이 없다 (재등록은 프론트가 다시 로그인/앱 실행할 때만 일어남).
_INVALID_TOKEN_ERROR_CODES = {"NOT_FOUND", "UNREGISTERED", "INVALID_ARGUMENT"}


class PushNotConfiguredError(RuntimeError):
    """FCM_CREDENTIALS_PATH가 설정되지 않아 발송할 수 없는 상태."""


def _get_app() -> firebase_admin.App:
    global _app
    if _app is None:
        if not settings.fcm_credentials_path:
            raise PushNotConfiguredError(
                "FCM_CREDENTIALS_PATH가 설정되지 않았습니다. .env에 Firebase 서비스 계정 키 경로를 지정하세요."
            )
        cred = credentials.Certificate(settings.fcm_credentials_path)
        _app = firebase_admin.initialize_app(cred)
    return _app


def send_push(tokens: List[str], title: str, body: str, data: Optional[Dict[str, str]] = None) -> List[str]:
    """
    tokens에 동일한 알림을 멀티캐스트로 발송한다.
    반환값: 더 이상 유효하지 않아 device_tokens에서 지워야 하는 토큰 목록.
    tokens가 비어있으면 FCM을 호출하지 않고 빈 리스트를 반환한다 (호출부에서 빈 리스트 필터링 생략 가능).
    """
    if not tokens:
        return []

    app = _get_app()
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=tokens,
    )
    response = messaging.send_each_for_multicast(message, app=app)

    invalid_tokens = []
    for token, result in zip(tokens, response.responses):
        if result.success:
            continue
        code = getattr(result.exception, "code", None)
        if code in _INVALID_TOKEN_ERROR_CODES:
            invalid_tokens.append(token)
        else:
            logger.warning("FCM 발송 실패 (token=%s...): %s", token[:8], result.exception)
    return invalid_tokens
