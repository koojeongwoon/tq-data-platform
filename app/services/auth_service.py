"""Authentication service - password hashing and JWT tokens"""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt

from shared.config.settings import settings

# =============================================================================
# Password Hashing
# =============================================================================


def hash_password(password: str) -> str:
    """비밀번호 해시"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


# =============================================================================
# JWT Token
# =============================================================================

# JWT 설정
JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Access Token: 30분
REFRESH_TOKEN_EXPIRE_DAYS = 7    # Refresh Token: 7일


def create_access_token(user_id: int, email: str) -> str:
    """JWT 액세스 토큰 생성 (30분)"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow()
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int, email: str) -> str:
    """JWT 리프레시 토큰 생성 (7일)"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow()
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """JWT 토큰 디코딩 및 검증"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # 토큰 만료
    except jwt.InvalidTokenError:
        return None  # 유효하지 않은 토큰


def decode_refresh_token(token: str) -> Optional[dict]:
    """리프레시 토큰 디코딩 및 검증"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None  # 리프레시 토큰이 아님
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_access_token_expire_seconds() -> int:
    """Access Token 만료 시간 (초)"""
    return ACCESS_TOKEN_EXPIRE_MINUTES * 60


def get_refresh_token_expire_seconds() -> int:
    """Refresh Token 만료 시간 (초)"""
    return REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
