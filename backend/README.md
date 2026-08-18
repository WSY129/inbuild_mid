# 헌혈 예측 알림 서비스 — 홈/설정 백엔드 (FastAPI)

회원가입/로그인은 다른 팀(`inbuild_mid` 레포)이 이미 구현했고, 이 백엔드는 **홈 화면**과 **설정 화면**만 담당합니다.
사용자 프로필(닉네임, 혈액형, 헌혈이력 등)은 회원가입팀의 `blood_link.db`(SQLite)를 **직접 공유해서 읽기 전용으로 조회**합니다.

> ⚠️ **배포 시 반드시 확인**
> 이 백엔드는 회원가입팀이 발급한 accessToken(JWT, HS256)을 직접 검증합니다.
> **두 서버의 `JWT_SECRET_KEY` 값이 같아야** 합니다. 다르면 로그인은 되는데 이 백엔드의 모든 요청이 401로 떨어집니다.
> 키는 32바이트 이상으로 잡으세요 (PyJWT가 그보다 짧으면 경고를 냅니다).

## 구조

버튼(화면 액션) 하나당 파일 하나 원칙으로 구성했습니다.

```
backend/
├── app/
│   ├── main.py                              # 앱 엔트리포인트, 라우터 등록
│   ├── config.py                            # 환경변수 (회원가입/AI API 주소, DB 경로)
│   ├── database.py                          # SQLite 엔진/세션
│   ├── models/
│   │   └── user_settings.py                 # 알림 설정 DB 모델 (이 백엔드가 직접 관리하는 유일한 테이블)
│   ├── schemas/
│   │   ├── user.py                          # 회원가입팀 API 응답 스키마
│   │   ├── home.py                          # 홈 화면 응답 스키마
│   │   └── settings_schema.py               # 설정 화면 요청/응답 스키마
│   ├── services/
│   │   ├── user_repository.py               # blood_link.db의 users 테이블 읽기 전용 조회
│   │   ├── auth.py                          # 현재 사용자 식별 (accessToken(JWT) 서명 검증)
│   │   ├── ai_client.py                     # AI팀 혈액 예측 모델 연동 (blood_predictor 호출 + 응답 가공)
│   │   └── blood_predictor.py               # AI팀 Holt-Winters 모델 포팅 (app/data/ CSV로 보유량 예측)
│   └── routers/
│       ├── home/
│       │   └── get_home.py                  # [버튼: 홈 화면 진입] GET /home
│       └── settings/
│           ├── _shared.py                   # 버튼 파일들이 공유하는 헬퍼 (라우터 아님)
│           ├── get_settings.py               # [버튼: 설정 화면 진입] GET /settings
│           ├── update_notification_toggle.py # [버튼: 전체 알림 수신 토글] PATCH /settings/notification
│           ├── update_sensitivity.py         # [버튼: 알림 민감도 드롭다운] PATCH /settings/sensitivity
│           ├── update_frequency.py           # [버튼: 알람 수신 주기 드롭다운] PATCH /settings/frequency
│           └── update_resend_count.py        # [버튼: 재수신 횟수 드롭다운] PATCH /settings/resend-count
├── requirements.txt
└── .env.example
```

## 실행 방법

```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # 선택
pip install -r requirements.txt
cp .env.example .env

# blood_link.db를 이 프로젝트 폴더에 복사하거나, .env의 SHARED_DB_PATH를
# inbuild_mid 레포의 blood_link.db 절대경로로 지정
uvicorn app.main:app --reload --port 8000
```

- 헬스체크: `GET /health`
- API 문서(자동 생성): `http://localhost:8000/docs`

## 사용자 식별 방식 (JWT)

프론트엔드는 회원가입팀 로그인(`POST /api/auth/login`) 성공 시 받은 `accessToken`을,
이 백엔드(`/home`, `/settings/*`)를 호출할 때마다 `Authorization` 헤더에 실어 보내면 됩니다.

```
GET /home
Authorization: Bearer <accessToken>
```

이 백엔드는 토큰 서명을 검증한 뒤 payload의 `sub`(= 로그인 아이디)로
`blood_link.db`의 `users` 테이블을 조회합니다 (`app/services/auth.py`, `app/services/user_repository.py`).

### 저장 키는 로그인 아이디가 아니라 `users.id`

회원 정보 수정 화면에서 **로그인 아이디는 사용자가 직접 바꿀 수 있습니다.**
그래서 `user_settings` 테이블의 기본키는 로그인 아이디가 아니라
변하지 않는 `users.id`(INTEGER PK)를 씁니다. 아이디를 바꿔도 알림 설정이 그대로 따라옵니다.

### 아이디를 바꾸면 토큰도 갈아끼워야 합니다

회원가입팀의 `PATCH /api/users/me`는 아이디가 바뀐 경우에만 응답에 새 `accessToken`을 함께 내려줍니다.
프론트가 이걸 저장하지 않고 예전 토큰을 계속 쓰면, 서명은 유효하지만 `sub`가 없는 아이디를 가리키게 되어
이 백엔드가 401 `"존재하지 않는 사용자입니다. 다시 로그인해주세요."`를 돌려줍니다.

## 지금 남아있는 TODO

1. ~~**인증을 토큰 기반으로 전환**~~ — 완료. 회원가입팀이 JWT 발급을 붙였고, 이 백엔드도 검증으로 교체했습니다.

2. **AI 예측 — 위험단계 판정 (AI팀 대기)**
   - 모델 연동은 완료. AI팀 Holt-Winters 모델을 `app/services/blood_predictor.py`로 포팅했고,
     `app/data/blood_stock_2016_2025.csv`로 실제 보유량 예측이 나옵니다 (결과는 캐싱).
   - 남은 것: 위험단계(관심/주의/경계/심각) 판정에 **일일소요량 자료**가 필요한데 AI팀이 확보 중입니다.
     그때까지 `current_status`/`next_status`는 `"판정 보류"`, `risk_probability`는 `0.0` 고정입니다.
     자료가 오면 `ai_client.py`의 TODO 지점만 교체하면 됩니다.
   - AI팀 자료가 ABO(A/B/AB/O)만 구분하고 Rh는 구분하지 않아, `rh_type`은 현재 예측값에 반영되지 않습니다.

3. ~~**헌혈 방식 문자열 통일**~~ — 완료. 표기를 통일하는 대신 이쪽에서 흡수하기로 했습니다.
   `get_home.py`의 `resolve_donation_interval_days()`가 공백과 `성분헌혈` 접미사를 무시하고
   키워드로 판정하므로, 와이어프레임 표기(`혈소판`)와 PRD 표기(`혈소판성분헌혈`) 둘 다 받습니다.

4. **최근 헌혈 날짜 수정 경로 (회원가입팀 대기 — 2026-08-19 수요일 이후 반영 예정)**
   - 와이어프레임 `Set_3`에는 `최근 헌혈 날짜`가 추가됐지만, 회원가입팀의 `UpdateProfileRequest`와
     `GET /api/users/me`에는 아직 `donationDate`가 없음
   - 이게 들어와야 사용자가 헌혈 후 날짜를 갱신할 수 있고, 홈 화면 D-day가 정확해짐
   - 우리 쪽은 `user_repository.py`가 이미 `last_donation_date`를 읽고 있어서 추가 작업 없음

5. **확인 필요한 가정**
   - `last_donation_date` 형식을 `"YYYY-MM-DD"`로 가정함 — 실제 형식이 다르면 `get_home.py`의 `calculate_next_donation_dday()` 파싱 로직 수정 필요
   - `blood_link.db` 파일에 이 백엔드가 읽기 권한으로 접근할 수 있는 배포 구조라고 가정 (같은 서버/컨테이너 또는 공유 볼륨)
   - 회원가입팀이 쓰고 이 백엔드가 읽는 구조가 됐으므로, 동시 접근 시 `database is locked`가 나면
     `PRAGMA journal_mode=WAL` 적용을 회원가입팀과 협의할 것
