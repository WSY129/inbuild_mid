# inbuild_mid

# Blood Link — 회원가입/인증 백엔드

## 기술 스택
- Python, FastAPI
- SQLite3 (WAL 모드)
- Passlib (bcrypt) — 비밀번호 해싱
- PyJWT — 로그인 인증 토큰

## 폴더 구조
blood-link-backend/
├── main.py # API 엔드포인트 정의
├── auth.py # JWT 토큰 발급/검증
├── database.py # DB 연결 및 테이블 생성
├── .env # 비밀키 (git에는 안 올라감)


## 실행 방법
```bash
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn passlib[bcrypt] python-dotenv PyJWT

# .env 파일에 아래 값 설정
# JWT_SECRET_KEY=아무-랜덤-문자열

uvicorn main:app --reload --host 0.0.0.0
```
서버 실행 후 `http://localhost:8000/docs`에서 API 직접 테스트 가능.

## API 목록

| Method | 경로 | 설명 | 인증 필요 |
|---|---|---|---|
| GET | `/api/members/check-id` | 아이디 중복 확인 | X |
| POST | `/api/members/signup` | 회원가입 | X |
| POST | `/api/auth/login` | 로그인, 토큰 발급 | X |
| GET | `/api/users/me` | 내 정보 조회 | O |
| PATCH | `/api/users/me` | 내 정보 수정 (일부 필드만 전달 가능) | O |
| POST | `/api/auth/verify-password` | 비밀번호 재확인 | O |


## 주요 설계 포인트
- 비밀번호는 `bcrypt`로 해싱해서 저장 (평문 저장 안 함)
- 로그인 성공 시 JWT 토큰 발급, 이후 요청은 이 토큰으로 사용자를 식별
- 토큰에는 로그인 아이디가 아니라 DB의 고유 PK(불변값)를 담아서, 아이디를 변경해도 토큰이 깨지지 않음
- 회원정보 수정(PATCH)은 보낸 필드만 부분적으로 반영됨 (전체 재입력 불필요)
- SQLite WAL 모드 적용 — 다른 서버(예: 홈/설정 팀)가 동시에 이 DB를 읽어도 잠금 충돌 없음

