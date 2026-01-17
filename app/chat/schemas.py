"""Chat schemas - 챗봇 관련 Pydantic 모델"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request model"""

    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="사용자 질문",
        examples=["임신부 지원 정책 알려줘", "청년 창업 지원금 어떻게 받아?"]
    )
    session_id: Optional[str] = Field(
        None,
        description="세션 ID (대화형 모드에서 사용)"
    )
    filters: Optional[dict] = Field(
        None,
        description="검색 필터 (chunk_type, province/ctpv_nm 등)",
        examples=[{"chunk_type": "benefit"}, {"province": "서울특별시"}]
    )
    top_k: int = Field(
        5,
        ge=1,
        le=10,
        description="검색할 정책 수"
    )
    model: str = Field(
        "gpt-4o-mini",
        description="사용할 LLM 모델",
        examples=["gpt-4o-mini", "gpt-4o"]
    )


class ConversationRequest(BaseModel):
    """Conversation request model for multi-turn chat"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="사용자 메시지"
    )
    session_id: Optional[str] = Field(
        None,
        description="세션 ID (없으면 새 세션 생성)"
    )


class OnboardingRequest(BaseModel):
    """대화형 온보딩/회원가입 요청"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="사용자 메시지"
    )
    session_id: Optional[str] = Field(
        None,
        description="게스트 세션 ID (없으면 새 세션 생성)"
    )


class OnboardingResponse(BaseModel):
    """대화형 온보딩/회원가입 응답"""

    response: str = Field(..., description="AI 응답")
    session_id: str = Field(..., description="게스트 세션 ID")
    step: str = Field(..., description="현재 온보딩 단계")
    is_complete: bool = Field(False, description="회원가입 완료 여부")
    collected_info: dict = Field(default_factory=dict, description="수집된 정보 (닉네임, 이메일)")

    # 회원가입 완료 시에만 포함
    access_token: Optional[str] = Field(None, description="JWT Access Token (완료 시)")
    refresh_token: Optional[str] = Field(None, description="JWT Refresh Token (완료 시)")
    user: Optional[dict] = Field(None, description="사용자 정보 (완료 시)")


class ProfileCollectionRequest(BaseModel):
    """프로필 수집 요청 (가입 후 채팅)"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="사용자 메시지"
    )
    current_step: str = Field(
        "ask_age_group",
        description="현재 프로필 수집 단계"
    )


class ProfileCollectionResponse(BaseModel):
    """프로필 수집 응답"""

    response: str = Field(..., description="AI 응답")
    step: str = Field(..., description="현재 단계 (ask_age_group, ask_gender, ask_region, ask_interests, complete)")
    is_complete: bool = Field(False, description="프로필 수집 완료 여부")
    profile: dict = Field(default_factory=dict, description="수집된 프로필 정보")


class ConversationResponse(BaseModel):
    """Conversation response model"""

    response: str = Field(..., description="AI 응답")
    session_id: str = Field(..., description="세션 ID")
    intent: str = Field("", description="감지된 의도 (welfare_search, chitchat, general_question, etc.)")
    ready_to_search: bool = Field(..., description="검색 준비 완료 여부")
    user_profile: dict = Field(default_factory=dict, description="수집된 사용자 정보")
    sources: Optional[List[dict]] = Field(None, description="검색 결과 (검색 실행 시)")


class PolicySource(BaseModel):
    """Source policy reference for frontend card display"""

    # 기본 식별자
    id: str = Field(..., description="정책 ID")
    title: str = Field(..., description="정책명")
    score: float = Field(..., description="관련도 점수")

    # 카드 표시용 필드
    description: str = Field("", description="정책 설명 (1-2줄)")
    benefit_summary: str = Field("", description="혜택 요약 (예: 월 50만원)")
    category: str = Field("", description="카테고리 (housing, job, finance, welfare 등)")
    region: str = Field("", description="지역 (서울, 경기, 전국 등)")
    apply_url: str = Field("", description="신청 URL")

    # 추가 정보
    ministry: str = Field("", description="담당부처")
    phone: str = Field("", description="문의전화")


class ChatResponse(BaseModel):
    """Chat response model"""

    answer: str = Field(..., description="AI 답변")
    sources: List[PolicySource] = Field(..., description="참조한 정책 목록")
    query: str = Field(..., description="원본 질문")
    context_used: bool = Field(..., description="정책 컨텍스트 사용 여부")


# =============================================================================
# Database DDL - Conversation Orchestration
# =============================================================================

# 1. 채팅방 (Conversations) - 사용자별 여러 대화방 관리
CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Conversation metadata
    title VARCHAR(200),                          -- 대화방 제목 (자동 생성 또는 사용자 지정)
    summary TEXT,                                -- 대화 요약 (LLM으로 주기적 업데이트)

    -- Current state (for multi-turn)
    current_intent VARCHAR(50),                  -- 현재 감지된 의도
    collected_info JSONB DEFAULT '{}',           -- 현재 대화에서 수집된 정보
    ready_to_search BOOLEAN DEFAULT FALSE,

    -- Status
    is_archived BOOLEAN DEFAULT FALSE,           -- 보관함 이동
    is_pinned BOOLEAN DEFAULT FALSE,             -- 상단 고정

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_conversation_id ON conversations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_last_message ON conversations(user_id, last_message_at DESC);
"""

# 2. 메시지 이력 (Messages) - 모든 대화 내용 영구 저장
CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(50) UNIQUE NOT NULL,
    conversation_id VARCHAR(50) NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,

    -- Message content
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,

    -- Additional data
    intent VARCHAR(50),                          -- 이 메시지의 의도
    extracted_info JSONB DEFAULT '{}',           -- 이 메시지에서 추출된 정보
    sources JSONB DEFAULT '[]',                  -- 참조한 정책 목록 (assistant만)
    model VARCHAR(50),                           -- 사용된 LLM 모델

    -- Feedback
    feedback VARCHAR(20) CHECK (feedback IN ('helpful', 'not_helpful', NULL)),
    feedback_comment TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(conversation_id, created_at);
"""

# 3. 사용자 프로필/관심사 (User Preferences) - 장기 기억
CREATE_USER_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 기본 정보 (사용자가 명시적으로 알려준 것)
    region VARCHAR(50),                          -- 거주 지역 (서울, 경기 등)
    region_detail VARCHAR(100),                  -- 상세 지역 (시군구)
    life_stage VARCHAR(50),                      -- 생애주기 (청년, 중장년, 노년 등)
    household_type VARCHAR(50),                  -- 가구 형태 (1인가구, 다자녀 등)

    -- 관심사 (대화에서 추론된 것)
    interest_themes JSONB DEFAULT '[]',          -- 관심 테마 ['주거', '취업', '금융' 등]
    searched_keywords JSONB DEFAULT '[]',        -- 검색했던 키워드들
    viewed_policies JSONB DEFAULT '[]',          -- 조회한 정책 ID들

    -- 행동 패턴
    preferred_time VARCHAR(20),                  -- 주로 사용하는 시간대
    interaction_count INTEGER DEFAULT 0,         -- 총 대화 횟수
    last_topics JSONB DEFAULT '[]',              -- 최근 대화 주제들

    -- 개인화 설정
    notification_enabled BOOLEAN DEFAULT TRUE,
    language VARCHAR(10) DEFAULT 'ko',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);
"""

# 4. 정책 조회 이력 (Policy Views) - 어떤 정책에 관심 있는지 추적
CREATE_POLICY_VIEWS_TABLE = """
CREATE TABLE IF NOT EXISTS policy_views (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    policy_id VARCHAR(50) NOT NULL,
    conversation_id VARCHAR(50) REFERENCES conversations(conversation_id) ON DELETE SET NULL,

    -- View context
    search_query TEXT,                           -- 어떤 검색어로 이 정책을 찾았는지
    relevance_score FLOAT,                       -- 검색 시 관련도 점수

    -- User actions
    clicked BOOLEAN DEFAULT FALSE,               -- 상세 조회 클릭 여부
    bookmarked BOOLEAN DEFAULT FALSE,            -- 북마크 여부
    shared BOOLEAN DEFAULT FALSE,                -- 공유 여부

    -- Timestamps
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_policy_views_user_id ON policy_views(user_id);
CREATE INDEX IF NOT EXISTS idx_policy_views_policy_id ON policy_views(policy_id);
CREATE INDEX IF NOT EXISTS idx_policy_views_user_policy ON policy_views(user_id, policy_id);
"""

# 5. 비인증 게스트 세션 (대화형 회원가입용)
CREATE_GUEST_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS guest_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE NOT NULL,

    -- 수집된 회원가입 정보
    collected_nickname VARCHAR(50),                  -- 닉네임
    collected_email VARCHAR(255),
    collected_password_hash VARCHAR(255),

    -- 개인 정보 (맞춤 정책 추천용)
    collected_age_group VARCHAR(20),                 -- 연령대 (10대, 20대, 30대, 40대, 50대, 60대 이상)
    collected_gender VARCHAR(10),                    -- 성별 (남성, 여성, 기타, 미공개)
    collected_region VARCHAR(50),                    -- 지역 (시/도)
    collected_region_detail VARCHAR(100),            -- 상세 지역 (시/군/구)

    -- 관심 정책 카테고리 (복수 선택)
    collected_interests JSONB DEFAULT '[]',          -- ["임신/출산", "육아", "청년", "노년" 등]

    -- 온보딩 상태
    onboarding_step VARCHAR(50) DEFAULT 'greeting',
    messages JSONB DEFAULT '[]',

    -- 연결된 사용자 (회원가입 완료 시)
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Metadata
    device_fingerprint VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guest_sessions_session_id ON guest_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_guest_sessions_email ON guest_sessions(collected_email);
CREATE INDEX IF NOT EXISTS idx_guest_sessions_expires_at ON guest_sessions(expires_at);
"""

# Legacy - 기존 세션 테이블 (마이그레이션 후 삭제 예정)
CREATE_CHAT_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_profile JSONB DEFAULT '{}',
    messages JSONB DEFAULT '[]',
    intent VARCHAR(50),
    ready_to_search BOOLEAN DEFAULT FALSE,
    fallback_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_expires_at ON chat_sessions(expires_at);
"""
