from datetime import date
from dotenv import load_dotenv
load_dotenv()
from enum import Enum
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import Optional
from passlib.context import CryptContext
from database import init_db, get_db
from auth import create_access_token, get_current_user_pk
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


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(x) for x in e["loc"][1:]), "reason": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"message": "입력값을 확인해주세요", "detail": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    return JSONResponse(status_code=500, content={"message": "서버 오류가 발생했습니다"})


class BloodTypeABO(str, Enum):
    A = "A"
    B = "B"
    O = "O"
    AB = "AB"


class RhType(str, Enum):
    positive = "Rh+"
    negative = "Rh-"
    unknown = "모름"


class DonationMethod(str, Enum):
    whole = "전혈"
    plasma = "혈장성분헌혈"
    platelet = "혈소판성분헌혈"
    platelet_plasma = "혈소판혈장성분헌혈"
    unknown = "모름"


class SignupRequest(BaseModel):
    id: str = Field(..., min_length=4, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=64)
    nickname: str = Field(..., min_length=1, max_length=12)
    bloodType: BloodTypeABO
    rhType: RhType
    birthdate: date
    donationDate: Optional[date] = None
    donationMethod: Optional[DonationMethod] = None


class LoginRequest(BaseModel):
    id: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class VerifyPasswordRequest(BaseModel):
    password: str = Field(..., min_length=1)


class UpdateProfileRequest(BaseModel):
    id: Optional[str] = Field(None, min_length=4, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    nickname: Optional[str] = Field(None, min_length=1, max_length=12)
    password: Optional[str] = Field(None, min_length=8, max_length=64)
    passwordConfirm: Optional[str] = None
    bloodType: Optional[BloodTypeABO] = None
    rhType: Optional[RhType] = None
    birthdate: Optional[date] = None
    donationDate: Optional[date] = None
    donationMethod: Optional[DonationMethod] = None


@app.get("/api/members/check-id")
def check_id(id: str, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (id,))
    exists = cursor.fetchone() is not None
    return {"available": not exists}


@app.post("/api/members/signup", status_code=201)
def signup(req: SignupRequest, db: sqlite3.Connection = Depends(get_db)):
    if req.donationDate and not req.donationMethod:
        raise HTTPException(status_code=422, detail="최근 헌혈일을 입력했다면 헌혈 방식도 입력해야 합니다")

    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (req.id,))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="이미 사용중인 아이디입니다")

    hashed_pw = pwd_context.hash(req.password)

    cursor.execute("""
        INSERT INTO users
        (user_id, password, nickname, blood_type_abo, rh_type, birth_date,
         last_donation_date, last_donation_method, notification_agreed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        req.id, hashed_pw, req.nickname, req.bloodType.value, req.rhType.value,
        req.birthdate.isoformat(),
        req.donationDate.isoformat() if req.donationDate else None,
        req.donationMethod.value if req.donationMethod else None,
        1
    ))

    return {"success": True}


@app.post("/api/auth/login")
def login(req: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (req.id,))
    user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="존재하지 않는 아이디입니다")

    stored_hashed_pw = user[2]
    if not pwd_context.verify(req.password, stored_hashed_pw):
        raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다")

    access_token = create_access_token(user_pk=user[0])
    return {"success": True, "accessToken": access_token}


def calculate_age(birth: date) -> int:
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


@app.post("/api/auth/verify-password")
def verify_password(
    req: VerifyPasswordRequest,
    current_user_pk: int = Depends(get_current_user_pk),
    db: sqlite3.Connection = Depends(get_db),
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (current_user_pk,))
    user = cursor.fetchone()

    if not user or not pwd_context.verify(req.password, user[2]):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")

    return {"success": True}


@app.get("/api/users/me")
def get_my_info(
    current_user_pk: int = Depends(get_current_user_pk),
    db: sqlite3.Connection = Depends(get_db),
):
    cursor = db.cursor()
    cursor.execute("""
        SELECT user_id, nickname, blood_type_abo, rh_type, birth_date, last_donation_date, last_donation_method
        FROM users WHERE id = ?
    """, (current_user_pk,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    return {
        "id": row[0],
        "nickname": row[1],
        "bloodType": row[2],
        "rhType": row[3],
        "birthdate": row[4],
        "donationDate": row[5],
        "donationMethod": row[6],
    }


@app.patch("/api/users/me")
def update_my_info(
    req: UpdateProfileRequest,
    current_user_pk: int = Depends(get_current_user_pk),
    db: sqlite3.Connection = Depends(get_db),
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (current_user_pk,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    updates = req.model_dump(exclude_unset=True, exclude={"passwordConfirm"})

    if "birthdate" in updates:
        age = calculate_age(updates["birthdate"])
        if age < 16:
            raise HTTPException(status_code=422, detail="만 16세 미만일 경우 헌혈에 참여할 수 없습니다")
        if age > 69:
            raise HTTPException(status_code=422, detail="만 69세 초과일 경우 헌혈에 참여할 수 없습니다")
        updates["birthdate"] = updates["birthdate"].isoformat()

    if "donationDate" in updates and updates["donationDate"] is not None:
        updates["donationDate"] = updates["donationDate"].isoformat()

    if "password" in updates:
        if req.password != req.passwordConfirm:
            raise HTTPException(status_code=422, detail="비밀번호가 일치하지 않습니다")
        if pwd_context.verify(req.password, user[2]):
            del updates["password"]
        else:
            updates["password"] = pwd_context.hash(updates["password"])

    if "id" in updates and updates["id"] != user[1]:
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (updates["id"],))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="이미 사용중인 아이디입니다")
    elif "id" in updates:
        del updates["id"]

    for enum_field in ("bloodType", "rhType", "donationMethod"):
        if enum_field in updates and updates[enum_field] is not None:
            updates[enum_field] = updates[enum_field].value

    if not updates:
        raise HTTPException(status_code=422, detail="변경 사항이 없습니다")

    column_map = {
        "id": "user_id", "password": "password", "nickname": "nickname",
        "bloodType": "blood_type_abo", "rhType": "rh_type",
        "birthdate": "birth_date", "donationDate": "last_donation_date",
        "donationMethod": "last_donation_method",
    }
    set_clause = ", ".join(f"{column_map[k]} = ?" for k in updates)
    values = list(updates.values()) + [current_user_pk]

    cursor.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)

    return {"success": True}