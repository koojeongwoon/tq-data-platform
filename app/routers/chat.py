"""Chat router for RAG-based welfare policy chatbot"""

import json
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory session store (프로덕션에서는 Redis 등 사용)
_sessions: Dict[str, dict] = {}


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

    # 카테고리 매핑
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

    # 축약형으로 변환
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

    # Region mapping
    region = user_profile.get("region", "")
    if region:
        # 축약형을 정식 명칭으로 변환
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


# =====================
# 대화형 엔드포인트 (LangGraph)
# =====================

@router.post("/conversation", response_model=ConversationResponse)
async def conversation(request: Request, body: ConversationRequest):
    """
    대화형 복지 정책 챗봇 엔드포인트 (LangGraph)

    **기능**:
    - 필요한 정보(지역, 생애주기 등)를 대화를 통해 수집
    - 정보 수집 완료 시 자동으로 맞춤 정책 검색
    - 세션 기반 멀티턴 대화 지원

    **흐름 예시**:
    1. 사용자: "지원받을 수 있는 정책 알려줘"
    2. AI: "어느 지역에 거주하고 계신가요?"
    3. 사용자: "서울이요"
    4. AI: "현재 상황에 해당하는 것이 있으신가요? (임신/출산, 청년 등)"
    5. 사용자: "임신 중이에요"
    6. AI: [검색 결과 + 카드]
    """
    import uuid
    from app.services.conversation_flow import ConversationFlow

    # Get or create session
    session_id = body.session_id or str(uuid.uuid4())
    session_state = _sessions.get(session_id)

    try:
        # Process conversation
        flow = ConversationFlow()
        result = flow.process(body.message, session_state)

        # Save session state
        _sessions[session_id] = result["session_state"]

        # If ready to search, execute search
        sources = None
        if result["ready_to_search"]:
            qdrant_service = getattr(request.app.state, "qdrant_service", None)
            rag_service = RAGService(qdrant_service=qdrant_service)

            # Build filters from profile
            filters = _build_filters_from_profile(result["user_profile"])

            # Search policies
            policies = rag_service.retrieve_context(
                query=result["search_query"],
                filters=filters,
                top_k=5
            )

            sources = [_format_policy_source(p).model_dump() for p in policies]

            # Generate answer with context
            context = rag_service.build_context_prompt(policies)
            answer = rag_service.generate_response(
                query=result["search_query"],
                context=context
            )

            # Append answer to response
            result["response"] = f"{result['response']}\n\n{answer}"

        return ConversationResponse(
            response=result["response"],
            session_id=session_id,
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
async def conversation_stream(request: Request, body: ConversationRequest):
    """
    대화형 복지 정책 챗봇 스트리밍 엔드포인트 (LangGraph + SSE)

    **SSE 이벤트 형식**:
    - `event: message` - AI 응답 메시지
    - `event: profile` - 수집된 사용자 정보
    - `event: sources` - 검색된 정책 카드 (검색 실행 시)
    - `event: answer` - RAG 답변 스트리밍 (검색 실행 시)
    - `event: done` - 완료
    """
    import uuid
    from app.services.conversation_flow import ConversationFlow

    session_id = body.session_id or str(uuid.uuid4())
    session_state = _sessions.get(session_id)

    async def generate():
        try:
            # Process conversation
            flow = ConversationFlow()
            result = flow.process(body.message, session_state)

            # Save session state
            _sessions[session_id] = result["session_state"]

            # Send session info
            yield f"event: session\ndata: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"

            # Send intent
            yield f"event: intent\ndata: {json.dumps({'intent': result.get('intent', '')}, ensure_ascii=False)}\n\n"

            # Send AI response message
            yield f"event: message\ndata: {json.dumps({'text': result['response']}, ensure_ascii=False)}\n\n"

            # Send profile
            yield f"event: profile\ndata: {json.dumps(result['user_profile'], ensure_ascii=False)}\n\n"

            # If ready to search, execute and stream
            if result["ready_to_search"]:
                qdrant_service = getattr(request.app.state, "qdrant_service", None)
                rag_service = RAGService(qdrant_service=qdrant_service)

                filters = _build_filters_from_profile(result["user_profile"])

                policies = rag_service.retrieve_context(
                    query=result["search_query"],
                    filters=filters,
                    top_k=5
                )

                # Send sources
                sources_data = [_format_policy_source(p).model_dump() for p in policies]
                yield f"event: sources\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"

                # Stream answer
                context = rag_service.build_context_prompt(policies)
                for chunk in rag_service.generate_response_stream(
                    query=result["search_query"],
                    context=context
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


@router.delete("/conversation/{session_id}")
async def delete_session(session_id: str):
    """세션 삭제"""
    if session_id in _sessions:
        del _sessions[session_id]
        return {"message": "세션이 삭제되었습니다."}
    raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")


# =====================
# 기존 직접 검색 엔드포인트
# =====================

@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequest):
    """
    RAG 기반 복지 정책 챗봇 스트리밍 엔드포인트 (SSE)

    **기능**:
    - 사용자 질문을 분석하여 관련 복지 정책을 하이브리드 검색 (Dense + BM25)
    - 검색된 정책 정보를 바탕으로 자연어 답변을 스트리밍으로 생성
    - 먼저 sources 이벤트로 참조 정책을 전송, 이후 answer 이벤트로 답변 스트리밍

    **SSE 이벤트 형식**:
    - `event: sources` - 참조 정책 목록 (JSON) - 프론트엔드 카드 표시용
    - `event: answer` - 답변 텍스트 청크
    - `event: done` - 스트리밍 완료
    - `event: error` - 오류 발생

    **예시 질문**:
    - "임신부가 받을 수 있는 혜택이 뭐가 있어?"
    - "청년 창업 지원금 신청 방법 알려줘"
    """
    # Get pre-loaded qdrant_service from app state
    qdrant_service = getattr(request.app.state, "qdrant_service", None)

    async def generate():
        try:
            rag_service = RAGService(qdrant_service=qdrant_service)

            # 1. Retrieve context using hybrid search
            policies = rag_service.retrieve_context(
                query=body.query,
                filters=body.filters,
                top_k=body.top_k
            )

            # 2. Send sources first (formatted for frontend cards)
            sources_data = [
                _format_policy_source(p).model_dump()
                for p in policies
            ]
            yield f"event: sources\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"

            # 3. Build context and stream answer
            context = rag_service.build_context_prompt(policies)

            for chunk in rag_service.generate_response_stream(
                query=body.query,
                context=context,
                model=body.model
            ):
                yield f"event: answer\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

            # 4. Done
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
async def chat(request: Request, body: ChatRequest):
    """
    RAG 기반 복지 정책 챗봇 엔드포인트 (비스트리밍)

    **기능**:
    - 사용자 질문을 분석하여 관련 복지 정책을 하이브리드 검색 (Dense + BM25)
    - 검색된 정책 정보를 바탕으로 자연어 답변 생성
    - 답변에 사용된 정책 출처 제공 (프론트엔드 카드 표시용)

    **스트리밍이 필요하면**: POST /chat/stream 사용
    **대화형이 필요하면**: POST /chat/conversation 사용

    **예시 질문**:
    - "임신부가 받을 수 있는 혜택이 뭐가 있어?"
    - "청년 창업 지원금 신청 방법 알려줘"
    - "어르신 건강검진 무료로 받을 수 있어?"
    - "서울에서 받을 수 있는 육아 지원 정책"

    **필터 옵션**:
    - chunk_type: "basic_info", "eligibility", "benefit", "application"
    - province: 시/도 이름 (예: "서울특별시", "경기도")
    """
    # Get pre-loaded qdrant_service from app state
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
            sources=[
                _format_policy_source(s)
                for s in result["sources"]
            ],
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
    """
    챗봇 서비스 상태 확인

    Qdrant, PostgreSQL, OpenAI 연결 상태를 반환
    """
    from shared.config.settings import settings
    from shared.db.postgres import PostgresClient
    from shared.services.qdrant_service import QdrantService

    # Get pre-loaded service or create new one
    qdrant_service = getattr(request.app.state, "qdrant_service", None)
    if not qdrant_service:
        qdrant_service = QdrantService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    postgres = PostgresClient()

    # Check Qdrant
    try:
        qdrant_info = qdrant_service.get_collection_info()
        qdrant_status = "ready"
        qdrant_count = qdrant_info.get("points_count", 0)
    except Exception:
        qdrant_status = "unavailable"
        qdrant_count = 0

    # Check if models are pre-loaded
    models_loaded = (
        qdrant_service._dense_model is not None and
        qdrant_service._sparse_model is not None
    ) if qdrant_service else False

    return {
        "qdrant": qdrant_status,
        "postgres": "ready" if postgres.health_check() else "unavailable",
        "openai": "configured" if settings.OPENAI_API_KEY else "not_configured",
        "embedding_models": "pre-loaded" if models_loaded else "lazy-load",
        "active_sessions": len(_sessions),
        "policy_count": {
            "qdrant_chunks": qdrant_count,
            "postgres": postgres.count_policies() if postgres.health_check() else 0
        }
    }
