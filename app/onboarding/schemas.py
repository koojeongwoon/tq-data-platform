"""Onboarding schemas - 온보딩 관련 Pydantic 모델"""

from typing import Optional

from pydantic import BaseModel, Field


class OnboardingProfile(BaseModel):
    """온보딩 프로필 정보"""
    region: Optional[str] = None
    life_cycle: Optional[str] = None
    interests: Optional[str] = None


class ConversationRequest(BaseModel):
    """온보딩 대화 요청"""
    message: str = Field(..., description="사용자 메시지 (첫 요청 시 빈 문자열 가능)")
    session_id: Optional[str] = Field(None, description="세션 ID (없으면 새 세션 생성)")


class ConversationResponse(BaseModel):
    """온보딩 대화 응답"""
    response: str = Field(..., description="AI 응답 메시지")
    session_id: str = Field(..., description="세션 ID")
    step: str = Field(..., description="현재 단계")
    profile: OnboardingProfile = Field(default_factory=OnboardingProfile, description="수집된 프로필")
    is_completed: bool = Field(False, description="온보딩 완료 여부")
    quick_replies: list[str] = Field(default_factory=list, description="빠른 응답 버튼 목록")


class CompleteRequest(BaseModel):
    """온보딩 완료 요청"""
    session_id: str = Field(..., description="온보딩 세션 ID")
    profile: OnboardingProfile = Field(..., description="수집된 프로필 정보")


class CompleteResponse(BaseModel):
    """온보딩 완료 응답"""
    message: str = Field(..., description="완료 메시지")
    user: dict = Field(..., description="업데이트된 사용자 정보")


# 온보딩 세션 DDL
CREATE_ONBOARDING_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS onboarding_sessions (
    id VARCHAR(50) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    step VARCHAR(50) DEFAULT 'greeting',
    region VARCHAR(50),
    life_cycle VARCHAR(50),
    interests TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_onboarding_sessions_user_id ON onboarding_sessions(user_id);
"""

# user_preferences 테이블 DDL
CREATE_USER_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    region VARCHAR(50),
    life_cycle VARCHAR(50),
    interests TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);
"""
