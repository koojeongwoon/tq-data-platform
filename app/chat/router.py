"""Chat router for RAG-based welfare policy chatbot"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.chat.conversation import ConversationFlow
from app.chat.orchestration import (
    add_message,
    create_conversation,
    delete_conversation,
    generate_conversation_title,
    get_conversation,
    get_or_create_conversation,
    get_or_create_preferences,
    get_recent_context,
    get_user_bookmarks,
    get_user_context_for_llm,
    list_conversations,
    record_policy_view,
    toggle_policy_bookmark,
    update_conversation,
    update_user_preferences,
)
from app.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationRequest,
    ConversationResponse,
    CREATE_CHAT_SESSIONS_TABLE,
    CREATE_CONVERSATIONS_TABLE,
    CREATE_MESSAGES_TABLE,
    CREATE_POLICY_VIEWS_TABLE,
    CREATE_USER_PREFERENCES_TABLE,
    PolicySource,
)
from app.chat.service import RAGService
from shared.config.settings import settings
from shared.db.postgres import PostgresClient
from shared.services.qdrant_service import QdrantService

router = APIRouter(prefix="/chat", tags=["Chat"])


def _init_tables():
    """채팅 관련 테이블 초기화"""
    postgres = PostgresClient()
    # 새로운 오케스트레이션 테이블
    postgres.execute_ddl(CREATE_CONVERSATIONS_TABLE)
    postgres.execute_ddl(CREATE_MESSAGES_TABLE)
    postgres.execute_ddl(CREATE_USER_PREFERENCES_TABLE)
    postgres.execute_ddl(CREATE_POLICY_VIEWS_TABLE)
    # Legacy (호환성 유지)
    postgres.execute_ddl(CREATE_CHAT_SESSIONS_TABLE)


# 앱 시작 시 테이블 생성
_init_tables()


# =============================================================================
# Helper Functions
# =============================================================================

def _format_policy_source(policy: dict) -> PolicySource:
    """Convert policy dict to PolicySource model for frontend card"""
    return PolicySource(
        id=policy.get("policy_id", ""),
        title=policy.get("title", ""),
        score=policy.get("score", 0),
        description=policy.get("summary", "") or policy.get("chunk_content", "")[:100] if policy.get("chunk_content") else "",
        benefit_summary=policy.get("support_provision", "") or "",
        category=_map_category(policy.get("interest_themes", [])),
        region=_format_region(policy.get("ctpv_nm", ""), policy.get("source_type", "")),
        apply_url=policy.get("website", "") or "",
        ministry=policy.get("ministry", ""),
        phone=policy.get("phone", "")
    )


def _map_category(interest_themes: list) -> str:
    """Map interest_themes to frontend category"""
    if not interest_themes:
        return "welfare"

    category_map = {
        "주거": "housing",
        "주거·자립": "housing",
        "고용": "job",
        "취업": "job",
        "창업": "job",
        "금융": "finance",
        "서민금융": "finance",
        "생활지원": "welfare",
        "보건·의료": "health",
        "건강": "health",
        "임신·출산": "family",
        "보육": "family",
        "교육": "education",
        "문화": "culture",
        "안전": "safety",
    }

    for theme in interest_themes:
        if isinstance(theme, str):
            for key, value in category_map.items():
                if key in theme:
                    return value

    return "welfare"


def _format_region(ctpv_nm: str, source_type: str) -> str:
    """Format region for display"""
    if not ctpv_nm:
        if source_type == "central":
            return "전국"
        return ""

    region_short = {
        "서울특별시": "서울",
        "부산광역시": "부산",
        "대구광역시": "대구",
        "인천광역시": "인천",
        "광주광역시": "광주",
        "대전광역시": "대전",
        "울산광역시": "울산",
        "세종특별자치시": "세종",
        "경기도": "경기",
        "강원도": "강원",
        "강원특별자치도": "강원",
        "충청북도": "충북",
        "충청남도": "충남",
        "전라북도": "전북",
        "전북특별자치도": "전북",
        "전라남도": "전남",
        "경상북도": "경북",
        "경상남도": "경남",
        "제주특별자치도": "제주",
    }

    return region_short.get(ctpv_nm, ctpv_nm)


def _build_filters_from_profile(user_profile: dict) -> dict:
    """Build search filters from user profile"""
    filters = {}

    region = user_profile.get("region", "")
    if region:
        region_full = {
            "서울": "서울특별시",
            "부산": "부산광역시",
            "대구": "대구광역시",
            "인천": "인천광역시",
            "광주": "광주광역시",
            "대전": "대전광역시",
            "울산": "울산광역시",
            "세종": "세종특별자치시",
            "경기": "경기도",
            "강원": "강원특별자치도",
            "충북": "충청북도",
            "충남": "충청남도",
            "전북": "전북특별자치도",
            "전남": "전라남도",
            "경북": "경상북도",
            "경남": "경상남도",
            "제주": "제주특별자치도",
        }
        filters["province"] = region_full.get(region, region)

    return filters


# =============================================================================
# Conversation Endpoints (LangGraph)
# =============================================================================

@router.post("/conversation", response_model=ConversationResponse)
async def conversation(
    request: Request,
    body: ConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    대화형 복지 정책 챗봇 엔드포인트 (LangGraph + Orchestration)

    **기능**:
    - 필요한 정보(지역, 생애주기 등)를 대화를 통해 수집
    - 정보 수집 완료 시 자동으로 맞춤 정책 검색
    - 대화 이력 영구 저장 및 사용자 관심사 학습
    """
    user_id = current_user["id"]

    # 1. 대화방 가져오기 또는 생성
    conversation_id, conv_data = get_or_create_conversation(body.session_id, user_id)
    is_new_conversation = conv_data is None

    # 2. 사용자 컨텍스트 가져오기 (장기 기억)
    user_context = get_user_context_for_llm(user_id)

    # 3. 기존 대화 이력 가져오기
    session_state = None
    if conv_data:
        recent_messages = get_recent_context(conversation_id, limit=10)
        session_state = {
            "messages": recent_messages,
            "user_profile": conv_data.get("collected_info", {}),
            "intent": conv_data.get("current_intent", ""),
            "agent_data": conv_data.get("agent_data", {}),
            "ready_to_search": conv_data.get("ready_to_search", False),
        }
        # 장기 기억에서 프로필 보완
        if user_context.get("region") and not session_state["user_profile"].get("region"):
            session_state["user_profile"]["region"] = user_context["region"]
        if user_context.get("life_stage") and not session_state["user_profile"].get("life_stage"):
            session_state["user_profile"]["life_stage"] = user_context["life_stage"]

    try:
        # 4. 사용자 메시지 저장
        add_message(conversation_id, "user", body.message)

        # 5. LangGraph 처리
        flow = ConversationFlow()
        result = flow.process(
            body.message, 
            session_state,
            pre_load_policy_id=body.pre_load_policy_id
        )

        # 6. 대화방 상태 업데이트
        update_conversation(
            conversation_id, user_id,
            current_intent=result.get("intent"),
            collected_info=result["user_profile"],
            agent_data=result.get("agent_data", {}),
            ready_to_search=result["ready_to_search"]
        )

        # 7. 새 대화방이면 제목 자동 생성
        if is_new_conversation:
            title = generate_conversation_title(body.message)
            update_conversation(conversation_id, user_id, title=title)

        # 8. 사용자 선호도 업데이트 (장기 기억)
        if result["user_profile"]:
            profile = result["user_profile"]
            update_user_preferences(
                user_id,
                region=profile.get("region"),
                life_stage=profile.get("life_stage"),
                add_topic=result.get("intent")
            )

        # 9. 검색 실행 (필요시)
        sources = None
        if result["ready_to_search"]:
            qdrant_service = getattr(request.app.state, "qdrant_service", None)
            rag_service = RAGService(qdrant_service=qdrant_service)

            filters = _build_filters_from_profile(result["user_profile"])
            chat_result = rag_service.chat(
                query=result["search_query"],
                filters=filters,
                top_k=5
            )

            sources = [_format_policy_source(p).model_dump() for p in chat_result["sources"]]
            policies = chat_result["sources"]

            # 정책 조회 기록
            for policy in policies:
                record_policy_view(
                    user_id,
                    policy.get("policy_id", ""),
                    conversation_id,
                    result["search_query"],
                    policy.get("score")
                )

            result["response"] = f"{result['response']}\n\n{chat_result['answer']}"

        # 10. AI 응답 저장
        add_message(
            conversation_id, "assistant", result["response"],
            intent=result.get("intent"),
            sources=sources
        )

        return ConversationResponse(
            response=result["response"],
            session_id=conversation_id,
            intent=result.get("intent", ""),
            ready_to_search=result["ready_to_search"],
            user_profile=result["user_profile"],
            sources=sources
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"대화 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/conversation/stream")
async def conversation_stream(
    request: Request,
    body: ConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    """대화형 복지 정책 챗봇 스트리밍 엔드포인트 (LangGraph + SSE)"""
    user_id = current_user["id"]
    session_id, conversation = get_or_create_conversation(body.session_id, user_id)
    session_state = conversation.get("collected_info", {}) if conversation else {}

    async def generate():
        try:
            flow = ConversationFlow()
            result = flow.process(body.message, session_state)

            # DB에 대화 상태 저장
            update_conversation(session_id, user_id, collected_info=result.get("session_state", {}))

            yield f"event: session\ndata: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"
            yield f"event: intent\ndata: {json.dumps({'intent': result.get('intent', '')}, ensure_ascii=False)}\n\n"
            yield f"event: message\ndata: {json.dumps({'text': result['response']}, ensure_ascii=False)}\n\n"
            yield f"event: profile\ndata: {json.dumps(result['user_profile'], ensure_ascii=False)}\n\n"

            if result["ready_to_search"]:
                qdrant_service = getattr(request.app.state, "qdrant_service", None)
                rag_service = RAGService(qdrant_service=qdrant_service)

                filters = _build_filters_from_profile(result["user_profile"])
                
                # Fetch policies once for UI/Tracking even if cache hits
                # In a more optimized version, we could get this from cache as well
                policies = rag_service.retrieve_context(
                    query=result["search_query"],
                    filters=filters,
                    top_k=5
                )
                sources_data = [_format_policy_source(p).model_dump() for p in policies]
                yield f"event: sources\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"

                for chunk in rag_service.chat_stream(
                    query=result["search_query"],
                    filters=filters,
                    top_k=5
                ):
                    yield f"event: answer\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

            yield f"event: done\ndata: {json.dumps({'ready_to_search': result['ready_to_search']}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.delete("/conversation/{conversation_id}")
async def delete_conv(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """대화방 삭제"""
    user_id = current_user["id"]
    deleted = delete_conversation(conversation_id, user_id)

    if deleted:
        return {"message": "대화방이 삭제되었습니다."}
    raise HTTPException(status_code=404, detail="대화방을 찾을 수 없습니다.")


@router.get("/conversations")
async def list_convs(
    current_user: dict = Depends(get_current_user),
    include_archived: bool = False,
    limit: int = 20,
    offset: int = 0
):
    """사용자의 대화방 목록 조회"""
    user_id = current_user["id"]
    conversations = list_conversations(user_id, include_archived, limit, offset)

    return {
        "count": len(conversations),
        "conversations": conversations
    }


@router.get("/conversations/{conversation_id}")
async def get_conv(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """대화방 상세 조회 (메시지 포함)"""
    user_id = current_user["id"]
    conv = get_conversation(conversation_id, user_id)

    if not conv:
        raise HTTPException(status_code=404, detail="대화방을 찾을 수 없습니다.")

    messages = get_recent_context(conversation_id, limit=50)

    return {
        **conv,
        "messages": messages
    }


@router.patch("/conversations/{conversation_id}")
async def update_conv(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    title: str = None,
    is_archived: bool = None,
    is_pinned: bool = None
):
    """대화방 업데이트 (제목, 보관, 고정)"""
    user_id = current_user["id"]

    updated = update_conversation(
        conversation_id, user_id,
        title=title,
        is_archived=is_archived,
        is_pinned=is_pinned
    )

    if updated:
        return {"message": "대화방이 업데이트되었습니다."}
    raise HTTPException(status_code=404, detail="대화방을 찾을 수 없습니다.")


# =============================================================================
# User Preferences Endpoints
# =============================================================================

@router.get("/preferences")
async def get_prefs(current_user: dict = Depends(get_current_user)):
    """사용자 선호도/관심사 조회"""
    user_id = current_user["id"]
    prefs = get_or_create_preferences(user_id)

    return prefs


@router.patch("/preferences")
async def update_prefs(
    current_user: dict = Depends(get_current_user),
    region: str = None,
    region_detail: str = None,
    life_stage: str = None,
    household_type: str = None
):
    """사용자 선호도 업데이트"""
    user_id = current_user["id"]

    update_user_preferences(
        user_id,
        region=region,
        region_detail=region_detail,
        life_stage=life_stage,
        household_type=household_type
    )

    return {"message": "선호도가 업데이트되었습니다."}


@router.get("/bookmarks")
async def get_bookmarks(current_user: dict = Depends(get_current_user)):
    """북마크한 정책 목록"""
    user_id = current_user["id"]
    bookmarks = get_user_bookmarks(user_id)

    return {
        "count": len(bookmarks),
        "bookmarks": bookmarks
    }


@router.post("/bookmarks/{policy_id}")
async def toggle_bookmark(
    policy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """정책 북마크 토글"""
    user_id = current_user["id"]
    is_bookmarked = toggle_policy_bookmark(user_id, policy_id)

    return {
        "policy_id": policy_id,
        "bookmarked": is_bookmarked
    }


# =============================================================================
# Direct Chat Endpoints
# =============================================================================

@router.post("/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """RAG 기반 복지 정책 챗봇 스트리밍 엔드포인트 (SSE)"""
    qdrant_service = getattr(request.app.state, "qdrant_service", None)

    async def generate():
        try:
            rag_service = RAGService(qdrant_service=qdrant_service)

            policies = rag_service.retrieve_context(
                query=body.query,
                filters=body.filters,
                top_k=body.top_k
            )

            sources_data = [_format_policy_source(p).model_dump() for p in policies]
            yield f"event: sources\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"

            context = rag_service.build_context_prompt(policies)
            for chunk in rag_service.generate_response_stream(
                query=body.query,
                context=context,
                model=body.model
            ):
                yield f"event: answer\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

            yield f"event: done\ndata: {json.dumps({'query': body.query, 'context_used': len(policies) > 0}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse, include_in_schema=False)
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """RAG 기반 복지 정책 챗봇 엔드포인트 (비스트리밍)"""
    qdrant_service = getattr(request.app.state, "qdrant_service", None)

    try:
        rag_service = RAGService(qdrant_service=qdrant_service)

        result = rag_service.chat(
            query=body.query,
            filters=body.filters,
            top_k=body.top_k,
            model=body.model
        )

        return ChatResponse(
            answer=result["answer"],
            sources=[_format_policy_source(s) for s in result["sources"]],
            query=result["query"],
            context_used=result["context_used"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"챗봇 응답 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/health")
async def chat_health(request: Request):
    """챗봇 서비스 상태 확인"""
    qdrant_service = getattr(request.app.state, "qdrant_service", None)
    if not qdrant_service:
        qdrant_service = QdrantService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    postgres = PostgresClient()

    try:
        qdrant_info = qdrant_service.get_collection_info()
        qdrant_status = "ready"
        qdrant_count = qdrant_info.get("points_count", 0)
    except Exception:
        qdrant_status = "unavailable"
        qdrant_count = 0

    models_loaded = (
        qdrant_service._dense_model is not None and
        qdrant_service._sparse_model is not None
    ) if qdrant_service else False

    # DB에서 대화 통계 조회
    conv_count = postgres.execute_one("SELECT COUNT(*) as count FROM conversations")
    msg_count = postgres.execute_one("SELECT COUNT(*) as count FROM messages")
    user_prefs_count = postgres.execute_one("SELECT COUNT(*) as count FROM user_preferences")

    return {
        "qdrant": qdrant_status,
        "postgres": "ready" if postgres.health_check() else "unavailable",
        "openai": "configured" if settings.OPENAI_API_KEY else "not_configured",
        "embedding_models": "pre-loaded" if models_loaded else "lazy-load",
        "orchestration": {
            "conversations": conv_count["count"] if conv_count else 0,
            "messages": msg_count["count"] if msg_count else 0,
            "users_with_preferences": user_prefs_count["count"] if user_prefs_count else 0,
        },
        "policy_count": {
            "qdrant_chunks": qdrant_count,
            "postgres": postgres.count_policies() if postgres.health_check() else 0
        }
    }




# =============================================================================
# Profile Collection Endpoints (인증 필요 - 가입 후 프로필 수집)
# =============================================================================

@router.get("/profile/status")
async def profile_status(current_user: dict = Depends(get_current_user)):
    """
    프로필 완성 상태 확인

    프로필이 완성되지 않은 경우 프론트엔드에서 프로필 수집 채팅을 시작할 수 있습니다.
    """
    user_id = current_user["id"]
    status = get_user_profile_status(user_id)

    return {
        "has_profile": status["has_profile"],
        "missing_fields": status["missing_fields"],
        "profile": status.get("current_profile", {})
    }


