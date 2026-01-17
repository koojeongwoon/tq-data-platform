"""Auth schemas - 인증 관련 Pydantic 모델"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """회원가입 요청"""
    email: EmailStr = Field(..., description="이메일")
    password: str = Field(..., min_length=8, description="비밀번호 (최소 8자)")
    name: str = Field(..., min_length=2, max_length=50, description="이름")


class UserLogin(BaseModel):
    """로그인 요청"""
    email: EmailStr = Field(..., description="이메일")
    password: str = Field(..., description="비밀번호")


class UserProfile(BaseModel):
    """사용자 프로필 (온보딩에서 수집)"""
    region: Optional[str] = None
    life_cycle: Optional[str] = None
    interests: Optional[str] = None


class UserResponse(BaseModel):
    """사용자 정보 응답"""
    id: int
    email: str
    name: str
    created_at: datetime
    is_active: bool = True
    onboarding_completed: bool = False
    profile: Optional[UserProfile] = None


class TokenResponse(BaseModel):
    """로그인 응답 (JWT 토큰)"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access Token 만료 시간 (초)")
    user: UserResponse


class RefreshRequest(BaseModel):
    """토큰 갱신 요청"""
    refresh_token: str = Field(..., description="리프레시 토큰")


class RefreshResponse(BaseModel):
    """토큰 갱신 응답 (RTR - Refresh Token Rotation)"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access Token 만료 시간 (초)")


class TokenPayload(BaseModel):
    """JWT 토큰 페이로드"""
    sub: int  # user_id
    email: str
    exp: datetime


# Database DDL
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""

# ALTER TABLE for existing database
ALTER_USERS_ADD_ONBOARDING = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;
"""

CREATE_REFRESH_TOKENS_TABLE = """
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
"""
