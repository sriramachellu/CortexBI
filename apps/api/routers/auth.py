import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from apps.api.config import settings
from apps.api.deps import CurrentUserId, DbSession
from packages.db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

_DUMMY_HASH = bcrypt.hashpw(b"dummy_timing_pad", bcrypt.gensalt()).decode()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest, db: DbSession):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(409, detail="Email already registered")

    if len(body.password) < 8:
        raise HTTPException(400, detail="Password must be at least 8 characters")

    user = User(
        user_id=uuid.uuid4(),
        email=body.email,
        password_hash=_hash_password(body.password),
    )
    db.add(user)
    await db.commit()

    token = create_token(str(user.user_id), user.email)
    return AuthResponse(token=token, user_id=str(user.user_id), email=user.email)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: DbSession):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    stored_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = _verify_password(body.password, stored_hash)

    if not user or not password_ok:
        raise HTTPException(401, detail="Invalid email or password")

    token = create_token(str(user.user_id), user.email)
    return AuthResponse(token=token, user_id=str(user.user_id), email=user.email)


@router.get("/me")
async def get_current_user(user_id: CurrentUserId, db: DbSession):
    result = await db.execute(select(User).where(User.user_id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail="User not found")
    return {"user_id": str(user.user_id), "email": user.email}
