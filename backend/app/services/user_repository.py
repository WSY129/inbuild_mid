"""
회원가입팀 레포(inbuild_mid)의 blood_link.db를 직접 읽어 사용자 프로필을 가져온다.
이 백엔드는 users 테이블에 대해 읽기 전용으로만 접근한다 (쓰기는 회원가입팀 코드가 담당).

users 테이블 스키마 (inbuild_mid/database.py 기준):
    id INTEGER PRIMARY KEY AUTOINCREMENT
    user_id TEXT UNIQUE           -- 로그인 아이디
    password TEXT                  -- bcrypt 해시 (이 백엔드는 사용하지 않음)
    nickname TEXT
    blood_type_abo TEXT            -- A / B / O / AB
    rh_type TEXT                   -- Rh+ / Rh- / 모름
    birth_date TEXT
    last_donation_date TEXT
    last_donation_method TEXT
    notification_agreed INTEGER
"""
import sqlite3
from typing import Optional

from app.config import settings
from app.schemas.user import SignupUser

#사용자정보가 없으면 None 반환, 있으면 SignupUser 객체 반환
def get_user_by_id(user_id: str) -> Optional[SignupUser]:
    # 이 백엔드는 blood_link.db에 읽기 전용으로만 접근해야 한다 (쓰기는 회원가입팀 코드가 담당).
    # mode=ro로 열면 이 프로세스에서 실수로 쓰기 쿼리를 보내도 DB 단계에서 거부되고,
    # 파일이 없을 때 sqlite3가 빈 DB를 새로 만들어버리는 것도 막을 수 있다.
    conn = sqlite3.connect(f"file:{settings.shared_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    #SQLite 조회결과는 기본적으로 튜플로 반환되는데, row_factory를 sqlite3.Row로 설정하면 컬럼명을 키로 갖는 딕셔너리처럼 접근 가능
    try:
        cursor = conn.cursor()
        #SQL 인젝션 방지를 위해 ? 플레이스홀더를 사용하고, execute의 두 번째 인자로 튜플을 전달
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    #해당 user_id를 가진 사용자가 없으면 NONE 반환(404)

    return SignupUser(
        internal_id=row["id"],
        id=row["user_id"],
        nickname=row["nickname"],
        bloodType=row["blood_type_abo"],
        rhType=row["rh_type"],
        birthdate=row["birth_date"],
        donationDate=row["last_donation_date"],
        donationMethod=row["last_donation_method"],
    )
