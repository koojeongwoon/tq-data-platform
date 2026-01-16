"""Authentication router - 회원가입, 로그인, 사용자 정보"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.user import (
    CREATE_USERS_TABLE,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_access_token_expire_seconds,
    hash_password,
    verify_password,
)
from shared.db.postgres import PostgresClient

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


def _init_users_table():
    """users 테이블 초기화"""
    postgres = PostgresClient()
    postgres.execute_ddl(CREATE_USERS_TABLE)


# 앱 시작 시 테이블 생성
_init_users_table()


# =============================================================================
# Dependencies
# =============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """현재 로그인한 사용자 반환"""
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # DB에서 사용자 확인
    postgres = PostgresClient()
    user_id = payload.get("user_id") or int(payload["sub"])
    user = postgres.execute_query(
        "SELECT id, email, name, is_active, created_at FROM users WHERE id = %s",
        (user_id,)
    )

    if not user or not user[0].get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다"
        )

    return user[0]


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate):
    """
    회원가입

    - 이메일 중복 체크
    - 비밀번호 해시 저장
    - 자동 로그인 (JWT 토큰 반환)
    """
    postgres = PostgresClient()

    # 이메일 중복 체크
    existing = postgres.execute_query(
        "SELECT id FROM users WHERE email = %s",
        (body.email,)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다"
        )

    # 비밀번호 해시
    password_hash = hash_password(body.password)

    # 사용자 생성
    result = postgres.execute_query(
        """
        INSERT INTO users (email, password_hash, name)
        VALUES (%s, %s, %s)
        RETURNING id, email, name, is_active, created_at
        """,
        (body.email, password_hash, body.name)
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 생성에 실패했습니다"
        )

    user = result[0]

    # JWT 토큰 생성
    access_token = create_access_token(user["id"], user["email"])
    refresh_token = create_refresh_token(user["id"], user["email"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=get_access_token_expire_seconds(),
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            created_at=user["created_at"],
            is_active=user["is_active"]
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
    """
    로그인

    - 이메일/비밀번호 검증
    - JWT 토큰 반환
    """
    postgres = PostgresClient()

    # 사용자 조회
    result = postgres.execute_query(
        "SELECT id, email, password_hash, name, is_active, created_at FROM users WHERE email = %s",
        (body.email,)
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다"
        )

    user = result[0]

    # 비밀번호 검증
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다"
        )

    # 비활성화된 계정 체크
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비활성화된 계정입니다"
        )

    # JWT 토큰 생성
    access_token = create_access_token(user["id"], user["email"])
    refresh_token = create_refresh_token(user["id"], user["email"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=get_access_token_expire_seconds(),
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            created_at=user["created_at"],
            is_active=user["is_active"]
        )
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(body: RefreshRequest):
    """
    토큰 갱신 (RTR - Refresh Token Rotation)

    - 유효한 Refresh Token으로 새 Access Token + Refresh Token 발급
    - 기존 Refresh Token은 무효화되고 새 토큰 쌍이 발급됨
    """
    payload = decode_refresh_token(body.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 리프레시 토큰입니다"
        )

    user_id = payload.get("user_id") or int(payload["sub"])
    email = payload.get("email")

    # 사용자 존재 및 활성화 확인
    postgres = PostgresClient()
    user = postgres.execute_query(
        "SELECT id, is_active FROM users WHERE id = %s",
        (user_id,)
    )

    if not user or not user[0].get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다"
        )

    # RTR: 새 Access Token + Refresh Token 발급
    new_access_token = create_access_token(user_id, email)
    new_refresh_token = create_refresh_token(user_id, email)

    return RefreshResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=get_access_token_expire_seconds()
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보

    Authorization: Bearer <token> 헤더 필요
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        created_at=current_user["created_at"],
        is_active=current_user["is_active"]
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    로그아웃

    JWT는 서버에서 무효화할 수 없으므로, 클라이언트에서 토큰 삭제 필요.
    이 엔드포인트는 로그아웃 확인용.
    """
    return {"message": "로그아웃 되었습니다", "user_id": current_user["id"]}
