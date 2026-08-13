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