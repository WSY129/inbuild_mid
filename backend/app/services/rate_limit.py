"""
아주 단순한 인메모리 rate limiter.

목적은 인증된 사용자가 쓰기 API(헌혈 기록 추가, 미션 클레임)를 짧은 시간에
반복 호출해서 DB에 부하를 주는 걸 막는 정도의 MVP 수준 방어다.

⚠️ 프로세스 메모리에만 카운트를 저장한다. uvicorn을 여러 워커/서버로 띄우면
   워커마다 카운트가 따로 세져서 실제 한도가 (설정값 × 워커 수)가 된다.
   진짜 다중 인스턴스로 배포하게 되면 Redis 등 공유 저장소 기반으로 교체할 것.
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Depends, HTTPException, status

from app.schemas.user import SignupUser
from app.services.auth import get_current_user


def rate_limit(max_calls: int, window_seconds: float):
    """
    사용 예: user: SignupUser = Depends(rate_limit(max_calls=10, window_seconds=60))
    get_current_user를 대체하는 게 아니라 감싸는 형태라, 반환값은 그대로 SignupUser다.

    ⚠️ 카운터(_call_history)는 이 함수 호출 하나당(=라우터 하나당) 별도로 만든다.
       모듈 전역 dict를 쓰면 user_internal_id만으로 키를 잡게 되어, 서로 다른
       엔드포인트(/donations, /missions/.../claim 등)가 같은 유저의 한도를 공유해버린다.
    """
    call_history: Dict[int, Deque[float]] = defaultdict(deque)

    def _dependency(user: SignupUser = Depends(get_current_user)) -> SignupUser:
        now = time.monotonic()
        history = call_history[user.internal_id]

        while history and now - history[0] > window_seconds:
            history.popleft()

        if len(history) >= max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
            )

        history.append(now)
        return user

    return _dependency
