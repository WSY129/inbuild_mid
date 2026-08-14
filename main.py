from datetime import date
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from passlib.context import CryptContext
from database import init_db
from auth import create_access_token, get_current_user_id
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# 프론트가 err.message를 읽으니, 에러 응답을 {"message": ...} 형식으로 통일
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


class SignupRequest(BaseModel):
    id: str
    password: str
    nickname: str
    bloodType: str                  # "A" / "B" / "O" / "AB"
    rhType: str                      # "Rh+" / "Rh-" / "모름"
    birthdate: str                    # "YYYY-MM-DD"
    donationDate: Optional[str] = None
    donationMethod: Optional[str] = None


class LoginRequest(BaseModel):
    id: str
    password: str


class VerifyPasswordRequest(BaseModel):
    password: str


class UpdateProfileRequest(BaseModel):
    id: str
    nickname: str
    password: Optional[str] = None
    passwordConfirm: Optional[str] = None
    bloodType: str
    rhType: str
    birthdate: str
    donationMethod: str


@app.get("/api/members/check-id")
def check_id(id: str):
    conn = sqlite3.connect("blood_link.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return {"available": not exists}


@app.post("/api/members/signup")
def signup(req: SignupRequest):
    if req.donationDate and not req.donationMethod:
        raise HTTPException(status_code=400, detail="최근 헌혈일을 입력했다면 헌혈 방식도 입력해야 합니다")

    conn = sqlite3.connect("blood_link.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (req.id,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="이미 사용중인 아이디입니다")

    hashed_pw = pwd_context.hash(req.password)

    cursor.execute("""
        INSERT INTO users
        (user_id, password, nickname, blood_type_abo, rh_type, birth_date,
         last_donation_date, last_donation_method, notification_agreed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        req.id, hashed_pw, req.nickname, req.bloodType, req.rhType,
        req.birthdate, req.donationDate, req.donationMethod,
        1  # 알림 동의 화면이 아직 없어서 기본값 True로 저장
    ))
    conn.commit()
    conn.close()

    return {"success": True}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = sqlite3.connect("blood_link.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (req.id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=400, detail="존재하지 않는 아이디입니다")

    stored_hashed_pw = user[2]
    if not pwd_context.verify(req.password, stored_hashed_pw):
        raise HTTPException(status_code=400, detail="비밀번호가 일치하지 않습니다")

    access_token = create_access_token(user_id=req.id)
    return {"success": True, "accessToken": access_token}


def calculate_age(birthdate_str: str) -> int:
    birth = date.fromisoformat(birthdate_str)
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

@app.post("/api/auth/verify-password")
def verify_password(req: VerifyPasswordRequest, current_user_id: str = Depends(get_current_user_id)):
    conn = sqlite3.connect("blood_link.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (current_user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not pwd_context.verify(req.password, user[2]):
        raise HTTPException(status_code=400, detail="비밀번호가 올바르지 않습니다")

    return {"success": True}


@app.get("/api/users/me")
def get_my_info(current_user_id: str = Depends(get_current_user_id)):
    conn = sqlite3.connect("blood_link.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, nickname, blood_type_abo, rh_type, birth_date, last_donation_method
        FROM users WHERE user_id = ?
    """, (current_user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    return {
        "id": row[0],
        "nickname": row[1],
        "bloodType": row[2],
        "rhType": row[3],
        "birthdate": row[4],
        "donationMethod": row[5],
    }


@app.patch("/api/users/me")
def update_my_info(req: UpdateProfileRequest, current_user_id: str = Depends(get_current_user_id)):
    # 1) 나이 제한 검사
    age = calculate_age(req.birthdate)
    if age < 16:
        raise HTTPException(status_code=400, detail="만 16세 미만일 경우 헌혈에 참여할 수 없습니다")
    if age > 69:
        raise HTTPException(status_code=400, detail="만 69세 초과일 경우 헌혈에 참여할 수 없습니다")

    # 2) 새 비밀번호를 입력했다면, 확인란과 일치하는지 검사
    if req.password and req.password != req.passwordConfirm:
        raise HTTPException(status_code=400, detail="비밀번호가 일치하지 않습니다")

    conn = sqlite3.connect("blood_link.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (current_user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    # 3) 아이디를 바꾸려는 경우, 다른 사람이 이미 쓰고 있는지 확인
    if req.id != current_user_id:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (req.id,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="이미 사용중인 아이디입니다")

    # 4) 실제로 바뀐 게 하나라도 있는지 검사
    new_password_changed = bool(req.password) and not pwd_context.verify(req.password, user[2])
    nothing_changed = (
        req.id == user[1]
        and req.nickname == user[3]
        and req.bloodType == user[4]
        and req.rhType == user[5]
        and req.birthdate == user[6]
        and req.donationMethod == user[8]
        and not new_password_changed
    )
    if nothing_changed:
        conn.close()
        raise HTTPException(status_code=400, detail="변경 사항이 없습니다")

    # 5) 실제 저장
    new_hashed_pw = pwd_context.hash(req.password) if new_password_changed else user[2]
    cursor.execute("""
        UPDATE users
        SET user_id = ?, password = ?, nickname = ?, blood_type_abo = ?, rh_type = ?, birth_date = ?, last_donation_method = ?
        WHERE user_id = ?
    """, (req.id, new_hashed_pw, req.nickname, req.bloodType, req.rhType, req.birthdate, req.donationMethod, current_user_id))
    conn.commit()
    conn.close()

    response = {"success": True}
    if req.id != current_user_id:
        response["accessToken"] = create_access_token(user_id=req.id)
    return response