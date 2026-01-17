"""Auth service - password hashing and JWT tokens"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt

from shared.config.settings import settings
from shared.db.postgres import PostgresClient


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


# =============================================================================
# Refresh Token DB Management (RTR)
# =============================================================================

def hash_token(token: str) -> str:
    """토큰을 SHA256으로 해시 (DB 저장용)"""
    return hashlib.sha256(token.encode()).hexdigest()


def store_refresh_token(user_id: int, token: str) -> bool:
    """리프레시 토큰을 DB에 저장"""
    postgres = PostgresClient()
    token_hash = hash_token(token)
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    return postgres.execute_write(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
        """,
        (user_id, token_hash, expires_at)
    )


def validate_refresh_token(token: str) -> Optional[dict]:
    """
    리프레시 토큰 검증 (JWT + DB)

    Returns:
        검증 성공 시 JWT payload, 실패 시 None
    """
    # 1. JWT 디코딩
    payload = decode_refresh_token(token)
    if not payload:
        return None

    # 2. DB에서 토큰 확인 (해시로 검색)
    postgres = PostgresClient()
    token_hash = hash_token(token)

    result = postgres.execute_query(
        """
        SELECT id, user_id, is_revoked, expires_at
        FROM refresh_tokens
        WHERE token_hash = %s
        """,
        (token_hash,)
    )

    if not result:
        return None  # DB에 없음

    token_record = result[0]

    # 3. 이미 사용된(revoked) 토큰인지 확인
    if token_record["is_revoked"]:
        # 토큰 재사용 공격 감지 - 해당 유저의 모든 토큰 무효화
        revoke_all_user_tokens(token_record["user_id"])
        return None

    # 4. 만료 확인
    if token_record["expires_at"] < datetime.utcnow():
        return None

    return payload


def revoke_refresh_token(token: str) -> bool:
    """리프레시 토큰을 무효화 (RTR에서 사용)"""
    postgres = PostgresClient()
    token_hash = hash_token(token)

    return postgres.execute_write(
        """
        UPDATE refresh_tokens
        SET is_revoked = TRUE, revoked_at = CURRENT_TIMESTAMP
        WHERE token_hash = %s
        """,
        (token_hash,)
    )


def revoke_all_user_tokens(user_id: int) -> bool:
    """특정 사용자의 모든 리프레시 토큰 무효화 (로그아웃, 보안 위협 시)"""
    postgres = PostgresClient()

    return postgres.execute_write(
        """
        UPDATE refresh_tokens
        SET is_revoked = TRUE, revoked_at = CURRENT_TIMESTAMP
        WHERE user_id = %s AND is_revoked = FALSE
        """,
        (user_id,)
    )


def cleanup_expired_tokens() -> int:
    """만료된 토큰 정리 (배치 작업용)"""
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        DELETE FROM refresh_tokens
        WHERE expires_at < CURRENT_TIMESTAMP
        RETURNING id
        """
    )

    return len(result) if result else 0
