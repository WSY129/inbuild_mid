# 헌혈 예측 알림 서비스 — 홈/설정 백엔드 (FastAPI)

회원가입/로그인은 다른 팀(`inbuild_mid` 레포)이 이미 구현했고, 이 백엔드는 **홈 화면**, **설정 화면**,
**헌혈 내역 기록**, **미션/등급**을 담당합니다.
사용자 프로필(닉네임, 혈액형, 헌혈이력 등)은 회원가입팀의 `blood_link.db`(SQLite)를 **직접 공유해서 읽기 전용으로 조회**합니다.

> ⚠️ **배포 시 반드시 확인**
> 이 백엔드는 회원가입팀이 발급한 accessToken(JWT, HS256)을 직접 검증합니다.
> **두 서버의 `JWT_SECRET_KEY` 값이 같아야** 합니다. 다르면 로그인은 되는데 이 백엔드의 모든 요청이 401로 떨어집니다.
> 키는 32바이트 이상으로 잡으세요 (PyJWT가 그보다 짧으면 경고를 냅니다).

## 구조

버튼(화면 액션) 하나당 라우터 파일 하나, 그 라우터가 쓰는 로직은 `services/`,
데이터 계약은 `schemas/`, 테이블 정의는 `models/`로 나누는 원칙으로 구성했습니다.

```
backend/
├── app/
│   ├── main.py                              # 앱 엔트리포인트, 라우터 등록
│   ├── config.py                            # 환경변수 (회원가입/AI API 주소, DB 경로)
│   ├── database.py                          # 이 백엔드 자체 SQLite 엔진/세션 (home_settings.db)
│   ├── models/
│   │   ├── user_settings.py                 # 알림 설정 테이블
│   │   ├── donation_record.py               # 헌혈 내역 기록 테이블
│   │   └── mission_progress.py              # 미션 클레임 이력 / 누적 EXP 테이블
│   ├── schemas/
│   │   ├── user.py                          # blood_link.db users 테이블 매핑 스키마
│   │   ├── home.py                          # 홈 화면 응답 스키마
│   │   ├── settings_schema.py               # 설정 화면 요청/응답 스키마
│   │   ├── donation_record.py               # 헌혈 내역 기록 요청/응답 스키마
│   │   └── mission.py                       # 미션/등급 응답 스키마
│   ├── services/
│   │   ├── user_repository.py               # blood_link.db의 users 테이블 읽기 전용 조회 (mode=ro)
│   │   ├── auth.py                          # 현재 사용자 식별 (accessToken(JWT) 서명 검증)
│   │   ├── rate_limit.py                    # 쓰기 API 남용 방지용 인메모리 rate limiter
│   │   ├── donation_method.py               # 헌혈 방식 문자열 판정 (표기 차이 흡수) — 여러 곳에서 공용
│   │   ├── donation_repository.py           # donation_records 테이블 조회/저장
│   │   ├── mission_rules.py                 # 미션·등급 기준 상수 (엑셀 정의표를 코드로 옮김)
│   │   ├── mission_service.py               # 미션 진행도/등급 계산 로직
│   │   ├── ai_client.py                     # AI팀 혈액 예측 모델 연동 (blood_predictor 호출 + 응답 가공)
│   │   ├── blood_predictor.py               # 예측 실행 래퍼 (app/data/ CSV 적재·검증 + 28일 예측 캐싱)
│   │   └── calendar_model.py                # AI팀 달력 회귀 모델 본체 — 원본 사본, 직접 수정 금지
│   └── routers/
│       ├── home/
│       │   └── get_home.py                  # [버튼: 홈 화면 진입] GET /home
│       ├── settings/
│       │   ├── _shared.py                   # 버튼 파일들이 공유하는 헬퍼 (라우터 아님)
│       │   ├── get_settings.py               # [버튼: 설정 화면 진입] GET /settings
│       │   ├── update_notification_toggle.py # [버튼: 전체 알림 수신 토글] PATCH /settings/notification
│       │   ├── update_sensitivity.py         # [버튼: 알림 민감도 드롭다운] PATCH /settings/sensitivity
│       │   ├── update_frequency.py           # [버튼: 알람 수신 주기 드롭다운] PATCH /settings/frequency
│       │   ├── update_resend_count.py        # [버튼: 재수신 횟수 드롭다운] PATCH /settings/resend-count
│       │   ├── register_device_token.py      # [로그인 직후] POST /settings/device-token (FCM 토큰 등록)
│       │   └── unregister_device_token.py    # [로그아웃 시] DELETE /settings/device-token (FCM 토큰 해제)
│       ├── donations/
│       │   ├── _shared.py                   # 버튼 파일들이 공유하는 헬퍼 (라우터 아님)
│       │   ├── get_history.py                # [버튼: 헌혈 내역 조회 화면 진입] GET /donations
│       │   └── add_history.py                # [버튼: 헌혈 내역 기록 '확인'] POST /donations
│       └── missions/
│           ├── get_missions.py               # [버튼: 미션 리스트 화면 진입] GET /missions
│           └── claim_mission.py              # [버튼: 미션 '완료'] POST /missions/{mission_key}/claim
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
alembic upgrade head   # 이 백엔드 자체 DB(home_settings.db) 테이블/인덱스 생성
uvicorn app.main:app --reload --port 8000
```

- 헬스체크: `GET /health`
- 준비 상태(공유 DB·AI 예측 데이터 접근 가능 여부): `GET /ready`
- API 문서(자동 생성): `http://localhost:8000/docs`

## DB 스키마 변경 (Alembic)

이 백엔드 자체 DB(`home_settings.db`)의 테이블/컬럼/인덱스는 [Alembic](https://alembic.sqlalchemy.org/)이 관리한다.
`app/main.py`는 더 이상 `Base.metadata.create_all()`을 호출하지 않는다 — 그 방식은 없는 테이블만
만들고 이미 있는 테이블은 안 건드려서, 기존 DB 파일에는 새 컬럼/인덱스가 반영되지 않는 문제가 있었다
(예: 미션 중복 클레임 방지 인덱스가 로컬 DB에 자동으로 안 생기던 문제 — 지금은 이 방식으로 해결됨).

```bash
# 모델(app/models/*.py) 변경 후:
alembic revision --autogenerate -m "설명"   # migrations/versions/에 마이그레이션 파일 생성
# 생성된 파일을 열어서 확인할 것 - 특히 mission_progress.py의 sqlite_where 부분 유니크
# 인덱스처럼 SQLite 전용 기능은 autogenerate가 놓칠 수 있어 손으로 보정이 필요할 수 있다.
alembic upgrade head                        # 로컬 DB에 적용

# 팀원이 새 커밋을 받았을 때(마이그레이션 파일이 추가됐다면):
alembic upgrade head
```

SQLite는 컬럼 삭제/제약 변경 등 대부분의 `ALTER TABLE`을 직접 지원하지 않아서, `migrations/env.py`에서
batch 모드(`render_as_batch=True`)를 켜뒀다 (Alembic이 내부적으로 "새 테이블 생성 → 데이터 복사 →
교체"로 우회 처리). DB 접속 정보는 `alembic.ini`가 아니라 `app/config.py`(`.env`의 `DATABASE_URL`)를
그대로 가져다 쓰므로 `.env`만 관리하면 된다.

## 사용자 식별 방식 (JWT)

프론트엔드는 회원가입팀 로그인(`POST /api/auth/login`) 성공 시 받은 `accessToken`을,
이 백엔드(`/home`, `/settings/*`, `/donations`, `/missions/*`)를 호출할 때마다
`Authorization` 헤더에 실어 보내면 됩니다.

```
GET /home
Authorization: Bearer <accessToken>
```

이 백엔드는 토큰 서명과 만료시간을 검증한 뒤 payload의 `sub`(= 로그인 아이디)로
`blood_link.db`의 `users` 테이블을 조회합니다 (`app/services/auth.py`, `app/services/user_repository.py`).
이 조회는 별도 스레드(`asyncio.to_thread`)에서 돌려서, 매 요청마다 발생하는 동기 파일 I/O가
이벤트 루프를 막지 않도록 합니다. 연결도 `mode=ro`로 열어 이 프로세스가 실수로도
회원가입팀 DB에 쓰기를 할 수 없게 막아뒀습니다.

인가(Authorization)는 별도 권한 테이블 없이, 모든 라우터가 URL/바디로 받은 값이 아니라
**항상 이 조회로 얻은 `user.internal_id`로만** 자기 데이터를 조회/수정하는 방식으로 처리합니다.
그래서 다른 사용자의 헌혈기록·설정·미션에 접근하는 경로 자체가 존재하지 않습니다.

### 저장 키는 로그인 아이디가 아니라 `users.id`

회원 정보 수정 화면에서 **로그인 아이디는 사용자가 직접 바꿀 수 있습니다.**
그래서 `user_settings`, `donation_records`, `user_exp`, `mission_claims` 테이블의 키는
로그인 아이디가 아니라 변하지 않는 `users.id`(`SignupUser.internal_id`)를 씁니다.
아이디를 바꿔도 알림 설정/헌혈기록/미션 진행도가 그대로 따라옵니다.

### 아이디를 바꾸면 토큰도 갈아끼워야 합니다

회원가입팀의 `PATCH /api/users/me`는 아이디가 바뀐 경우에만 응답에 새 `accessToken`을 함께 내려줍니다.
프론트가 이걸 저장하지 않고 예전 토큰을 계속 쓰면, 서명은 유효하지만 `sub`가 없는 아이디를 가리키게 되어
이 백엔드가 401 `"존재하지 않는 사용자입니다. 다시 로그인해주세요."`를 돌려줍니다.

## 안정성/보안 관련 방어 로직

멘토 리뷰(홈/설정/헌혈기록/미션 API)를 반영해서 추가한 것들입니다.

- **`/home`이 AI 예측 실패로 통째로 죽지 않습니다.** `get_blood_prediction()` 호출을 try/except로
  감싸서, 실패하면 예측 관련 필드만 "판정 보류"로 채우고 닉네임/혈액형/D-day는 정상 응답합니다
  (`app/routers/home/get_home.py`).
- **`/home`이 잘못된 날짜 형식으로 죽지 않습니다.** D-day 계산에 쓰는 `donation_date`가
  헌혈 기록이 하나도 없을 때는 회원가입팀 DB(`blood_link.db`)의 검증되지 않은 원시 문자열로
  폴백되는데, `"YYYY-MM-DD"`가 아니어도 파싱 실패를 잡아 "정보 없음"으로 대체하고 경고 로그만
  남깁니다 (`app/routers/home/get_home.py`).
- **`GET /settings`는 조회만 합니다.** 예전에는 설정이 없으면 조회 중에 새 행을 만들었는데,
  GET에 부작용이 있으면 캐시/재시도/모니터링에서 예측하기 어려워집니다. 이제 행이 없으면
  DB에 쓰지 않고 기본값만 응답하고, 실제 저장은 사용자가 설정을 하나라도 바꿔 PATCH를
  호출할 때 일어납니다 (`app/routers/settings/_shared.py`, `app/routers/settings/get_settings.py`).
- **헌혈 방식 입력을 검증합니다.** `POST /donations`의 `donation_method`는 여전히 와이어프레임/PRD
  두 표기를 다 받지만(표기를 하나로 강제 통일하지 않기로 한 기존 결정 유지), `app/services/donation_method.py`가
  판정할 수 없는 문자열(오타, "모름" 등)은 422로 거부합니다. 위경도도 범위를 검증합니다
  (`app/schemas/donation_record.py`).
- **미션 완료 이중 지급을 막습니다.** 계정형 미션은 `mission_claims`에
  `(user_internal_id, mission_key)` 부분 유니크 인덱스를, 반복형 미션(`habit_donation`,
  `steady_heart`, `quick_donation`)은 이번 클레임의 근거가 된 헌혈 기록을 `evidence_id`로 저장해
  `(user_internal_id, mission_key, evidence_id)` 부분 유니크 인덱스를 걸었습니다. 같은 미션(또는
  반복형이면 같은 헌혈 기록)을 거의 동시에 두 번 클레임해도 DB 단에서 하나는 거부되게 했습니다
  (409로 응답). 앱 레벨의 "이미 클레임했는지"/진행도 조회만으로는 두 요청이 동시에 통과할 수 있어서
  최종 방어선으로 추가했습니다 (`app/models/mission_progress.py`, `app/services/mission_service.py`,
  `app/routers/missions/claim_mission.py`).
  > 기존 DB에 이 인덱스들과 `evidence_id` 컬럼을 반영하려면 `alembic upgrade head`를 실행하세요
  > (위 "DB 스키마 변경(Alembic)" 참고). Alembic 도입 전에 만든 DB 파일이라면 먼저
  > `alembic stamp <이 인덱스 이전 리비전>`으로 현재 상태를 맞춰줘야 합니다.
- **쓰기 API에 인메모리 rate limit을 걸었습니다.** `POST /donations`(분당 10회),
  `POST /missions/{key}/claim`(분당 20회) — 단일 프로세스 배포를 가정한 MVP 수준 방어입니다.
  여러 워커/서버로 스케일아웃하면 워커별로 카운트가 따로 세지니, 그땐 Redis 등 공유 저장소
  기반으로 바꿔야 합니다 (`app/services/rate_limit.py`).
- **설정 최초 생성 시 경쟁 상태를 처리합니다.** 같은 유저의 동시 요청이 둘 다 "설정 없음"으로 보고
  동시에 insert를 시도해도, 뒤에 커밋 실패한 쪽은 방금 만들어진 행을 다시 읽어옵니다
  (`app/routers/settings/_shared.py`).

## 실제 푸시 발송 (FCM)

이전에는 이 백엔드가 "알림 켜짐/꺼짐" 설정값만 저장하고, 실제 발송(FCM/APNs 서버 호출)은
없었습니다. 서버 키를 클라이언트에 둘 수 없어 발송 자체는 프론트가 아니라 이 백엔드가
담당해야 하므로, 아래 세 가지를 추가했습니다.

1. **디바이스 토큰 등록/해제** — 프론트가 Firebase SDK로 발급받은 FCM 토큰을 로그인 직후
   `POST /settings/device-token`으로 등록하고, 로그아웃 시 `DELETE /settings/device-token`으로
   해제합니다 (`app/models/device_token.py`, `app/routers/settings/register_device_token.py`,
   `unregister_device_token.py`). 한 유저가 여러 기기를 등록할 수 있고, 같은 토큰으로 다른
   유저가 다시 등록하면(기기 재사용) 소유자를 갱신하는 upsert로 처리합니다.
2. **FCM 발송 클라이언트** — `app/services/push_client.py`가 `firebase-admin` SDK를 얇게
   감쌉니다. `.env`의 `FCM_CREDENTIALS_PATH`(Firebase 서비스 계정 키 JSON 경로, 저장소에
   커밋 금지)가 비어있으면 발송 시점에 `PushNotConfiguredError`만 던지고 나머지 기능(배치
   포함)은 정상 동작합니다 — 키를 아직 발급받지 못한 로컬 개발 환경에서도 서버가 죽지 않게
   하기 위함입니다.
3. **예측 기반 알림 배치** — `app/services/notification_batch.py` + `notification_scheduler.py`.
   매일(`NOTIFICATION_BATCH_HOUR`, 기본 9시) 알림을 켜둔 전체 유저를 훑어서, 각자의
   `sensitivity`/`frequency`/`resend_count` 설정에 맞춰 "혈액 부족 조짐" 푸시를 보낼지
   판단합니다. rate_limit.py/blood_predictor.py와 같은 이유로 별도 워커 없이 앱 프로세스
   안에서 APScheduler로 돌리는 단일 프로세스 배포 가정입니다 — 여러 워커로 스케일아웃하면
   배치가 중복 실행되니 그 전에 외부 스케줄러나 단일 워커 실행 방식으로 바꿔야 합니다.

   ⚠️ **PRD/엑셀 정의표에 없어서 이 배치가 임의로 정한 가정** (기획 확정되면 교체할 것,
   `app/services/notification_batch.py` 상단 docstring 참고):
   - 경보 판정 신호는 위험단계(관심/주의/경계/심각)가 아니라 `alert_signal`입니다.
     위험단계 판정은 AI팀 일일소요량 자료 대기 중이라 아직 "판정 보류"이기 때문입니다
     (아래 TODO 2번 참고). `predicted_volumes`가 `alert_signal` 이하로 떨어지는 날이
     예측 구간 안에 있으면 "부족 조짐"으로 봅니다.
   - `sensitivity`는 몇 일짜리 구간을 볼지로 해석했습니다: 민감=21일 / 보통=14일 / 둔함=7일
     (AI팀 정확도 구간 - 1~7일 운영판단, 8~21일 경보발동, 22~28일 참고용 - 기준).
   - `resend_count`는 "최초 발송 이후 추가로 재수신하는 횟수"로 해석했습니다. 즉 경보 하나당
     최대 발송 횟수 = 1(최초) + resend_count이고, `frequency`(일)마다 한 번씩 재발송합니다.
     `frequency == "재수신하지않음"`이면 최초 1건만 보냅니다.
   - 경보가 풀렸다가(예측이 회복) 다시 나빠지면 새 경보로 취급해 재수신 횟수를 리셋합니다.

## 지금 남아있는 TODO

1. ~~**인증을 토큰 기반으로 전환**~~ — 완료. 회원가입팀이 JWT 발급을 붙였고, 이 백엔드도 검증으로 교체했습니다.

2. **AI 예측 — 위험단계 판정 (AI팀 대기)**
   - 모델 연동은 완료. AI팀 2차 전달본(달력 회귀)을 붙였습니다. 모델 본체는
     `app/services/calendar_model.py`에 원본 그대로 두고(직접 수정 금지),
     `app/services/blood_predictor.py`가 `app/data/blood_stock_2016_2025.csv`를 읽어
     **28일** 예측을 만듭니다 (결과는 프로세스 단위 캐싱, 전체 4형 약 0.2초).
   - **Holt-Winters에서 교체했습니다.** 이전 설정이 "어제 값 그대로"(naive) 베이스라인에 졌고,
     124회 적합 중 53회에서 수렴 경고가 났습니다. 새 모델은 최소제곱 닫힌 해라 반복 최적화가
     없어서 라이브러리 버전에 따라 결과가 흔들리지 않습니다 — `requirements.txt`의 버전 고정도
     이때 함께 풀고 `statsmodels`/`scipy`를 뺐습니다(`holidays` 추가).
   - **응답 스키마가 바뀌었습니다.** horizon이 20일 → 28일이라 `predicted_dates`/`predicted_volumes`
     길이가 28이 되고, 경보 판정용 `alert_signals` 배열이 새로 나갑니다.
     프론트는 하락 경보를 점추정이 아니라 `alert_signals`로 판정해야 합니다.
     이 값은 **신뢰구간이 아닙니다** — 홀드아웃 실측 커버리지가 44~55%라 "95% 확률" 류의
     문구로 표시하면 안 됩니다.
   - 정확도가 뒤로 갈수록 떨어집니다. 1~7일은 운영 판단, 8~21일은 경보 발동,
     22~28일은 추세 참고만(경보 근거로 쓰지 않기). 혈액형별 상대오차 최댓값은 각각
     5.9% / 13.8% / 15.5%이고 세 구간 모두 A형이 가장 나쁩니다.
   - 남은 것: 위험단계(관심/주의/경계/심각) 판정에 **일일소요량 자료**가 필요한데 AI팀이 확보 중입니다.
     예측값은 유닛 수이고 판정 기준은 일수라 `보유일수 = 예측 유닛 ÷ 일일소요량` 변환이 필요합니다.
     그때까지 `current_status`/`next_status`는 `"판정 보류"`, `risk_probability`는 `0.0` 고정입니다.
     자료가 오면 `ai_client.py`의 TODO 지점만 교체하면 됩니다.
     (AI팀에 확인할 것: 일일소요량이 고정 상수인지 날짜별 시계열인지. 시계열이면 28일 뒤
     소요량도 예측해야 해서 담당 협의가 필요합니다.)
   - `as_of_date`는 CSV 마지막 실측일(2025-12-31)이라 예측 구간도 그 다음날부터입니다.
     CSV가 갱신되지 않으면 홈 화면 그래프의 날짜가 과거로 남습니다.
   - AI팀 자료가 ABO(A/B/AB/O)만 구분하고 Rh는 구분하지 않아, `rh_type`은 현재 예측값에 반영되지 않습니다.
   - 위 두 미션(`blood_type_hero`, `problem_solver`)과 "얼굴없는 구원자"(`faceless_savior`)는
     위험단계 판정이 나와야 구현 가능합니다 (`app/services/mission_rules.py` 참고).

3. ~~**헌혈 방식 문자열 통일**~~ — 완료. 표기를 통일하는 대신 이쪽에서 흡수하기로 했습니다.
   `app/services/donation_method.py`의 `resolve_donation_interval_days()`가 공백과 `성분헌혈` 접미사를
   무시하고 키워드로 판정하므로, 와이어프레임 표기(`혈소판`)와 PRD 표기(`혈소판성분헌혈`) 둘 다 받습니다.
   `POST /donations`는 여기에 더해 아예 판정 불가능한 문자열만 422로 거릅니다.

4. **최근 헌혈 날짜 수정 경로 (회원가입팀 대기 — 2026-08-19 수요일 이후 반영 예정)**
   - 와이어프레임 `Set_3`에는 `최근 헌혈 날짜`가 추가됐지만, 회원가입팀의 `UpdateProfileRequest`와
     `GET /api/users/me`에는 아직 `donationDate`가 없음
   - 이게 들어와야 사용자가 헌혈 후 날짜를 갱신할 수 있고, 홈 화면 D-day가 정확해짐
   - 우리 쪽은 `user_repository.py`가 이미 `last_donation_date`를 읽고 있어서 추가 작업 없음

5. **미션 '알림지기' 계산의 전제**
   - `notification_enabled_since`가 없어도(가입 후 한 번도 토글 안 한 경우) `created_at`을 시작점으로
     대신 쓰는데, 이건 "가입 시점부터 알림이 켜져 있었다"는 가정입니다. 실제 기본값 정책이 바뀌면
     `get_notification_keeper_progress()`(`app/services/mission_service.py`)도 같이 봐야 합니다.

6. **확인 필요한 가정**
   - `last_donation_date` 형식을 `"YYYY-MM-DD"`로 가정함 — 실제 형식이 다르면 `get_home.py`의 `calculate_next_donation_dday()` 파싱 로직 수정 필요
   - `blood_link.db` 파일에 이 백엔드가 읽기 권한으로 접근할 수 있는 배포 구조라고 가정 (같은 서버/컨테이너 또는 공유 볼륨)
   - 회원가입팀이 쓰고 이 백엔드가 읽는 구조가 됐으므로, 동시 접근 시 `database is locked`가 나면
     `PRAGMA journal_mode=WAL` 적용을 회원가입팀과 협의할 것
   - `rate_limit.py`는 단일 프로세스 기준입니다. 배포를 여러 인스턴스로 늘릴 계획이 있다면
     그 전에 공유 저장소 기반으로 교체할 것.
   - 실제 배포 전에 `FCM_CREDENTIALS_PATH`에 Firebase 서비스 계정 키를 넣어야 푸시가 실제로
     나갑니다. 키가 없으면 알림 배치는 매일 돌지만 발송은 건너뛰고 경고 로그만 남깁니다
     (`app/services/push_client.py`).
