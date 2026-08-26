"""
회원가입팀(inbuild_mid)이 로그인 시 발급한 accessToken(JWT)을 검증해서 현재 사용자를 식별한다.

프론트는 로그인 응답의 accessToken을 `Authorization: Bearer <token>` 헤더에 실어 보내면 된다.
이전의 X-User-Id 헤더 방식은 값만 바꾸면 남의 설정을 조회/변경할 수 있어서 폐기했다.

⚠️ 토큰 payload의 sub는 '로그인 아이디'(users.user_id)이고, 이 값은 회원 정보 수정 화면에서
   사용자가 직접 바꿀 수 있다. 그래서 sub는 사용자를 찾는 용도로만 쓰고,
   설정 데이터의 키로는 절대 쓰지 않는다 (변하지 않는 users.id를 쓴다 - user_settings.py 참고).
"""
import asyncio

import jwt
#pyjwt. 회원가입팀 auth.py와 같은 라이브러리/알고리즘(HS256)을 쓴다.

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
#HTTPBearer: Authorization 헤더에서 "Bearer <token>" 형식을 파싱해주는 FastAPI 헬퍼.
#            헤더가 아예 없거나 형식이 틀리면 여기서 403으로 걸러진다.

from app.config import settings
from app.schemas.user import SignupUser
from app.services.user_repository import get_user_by_id

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> SignupUser:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다. 다시 로그인해주세요.",
        )
    except jwt.InvalidTokenError:
        #서명 불일치(양쪽 JWT_SECRET_KEY가 다른 경우 포함), 형식 오류 등 나머지 전부
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )

    login_id = payload.get("sub")
    if not login_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )

    # get_user_by_id는 sqlite3를 동기로 호출한다. get_current_user는 인증된 요청마다
    # 매번 거치는 경로라, 그대로 await 없이 부르면 그 파일 I/O가 끝날 때까지
    # 이벤트 루프 전체가 막힌다. 별도 스레드로 돌려서 블로킹을 피한다.
    user = await asyncio.to_thread(get_user_by_id, login_id)
    if user is None:
        #서명이 유효한데 사용자가 없다 = 아이디를 변경한 뒤 프론트가 새 accessToken으로
        #교체하지 않고 예전 토큰을 계속 쓰고 있는 상황. 404가 아니라 재로그인을 유도한다.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자입니다. 다시 로그인해주세요.",
        )
    return user
