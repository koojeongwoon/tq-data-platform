"""
LangGraph-based conversation orchestration for welfare policy chatbot

Features:
- Intent Recognition (복지검색, 정책상세, 일반질문, 잡담)
- LLM-based Slot Filling
- Fallback handling
- Multi-turn dialog management
"""

import json
import re
from typing import Annotated, Literal, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from shared.config.settings import settings
from app.welfare.prompts import (
    CHECKLIST_AGENT_SYSTEM,
    REASONING_AGENT_SYSTEM,
    PLAIN_LANGUAGE_AGENT_SYSTEM,
    SCENARIO_AGENT_SYSTEM,
)
from .prompts import (
    INTENT_CLASSIFICATION_SYSTEM,
    SLOT_EXTRACTION_SYSTEM,
    GENERAL_QUESTION_SYSTEM,
    build_intent_classification_prompt,
    build_slot_extraction_prompt,
    build_general_question_prompt,
)
from .service import RAGService


# =============================================================================
# Type Definitions
# =============================================================================

class UserProfile(TypedDict, total=False):
    """User profile information for policy search"""
    region: str          # 시/도 (서울특별시, 경기도 등)
    age_group: str       # 연령대 (20대, 30대 등)
    life_cycle: str      # 생애주기 (임신/출산, 영유아, 청년, 노년 등)
    interest: str        # 관심분야 (주거, 취업, 금융, 건강 등)


class ConversationState(TypedDict):
    """Conversation state for LangGraph"""
    messages: Annotated[list, add_messages]
    user_profile: UserProfile
    intent: str                    # welfare_search, policy_detail, checklist, reasoning, plain_language, scenario, general_question, chitchat, unknown
    missing_fields: list[str]
    ready_to_search: bool
    search_query: str
    policy_id: str                 # For policy_detail intent
    agent_data: dict               # Persistent data for specialized agents (checklist items, calc results, etc.)
    fallback_count: int            # Track consecutive fallbacks
    retrieved_docs: list[dict]     # Context retrieved from RAG


# =============================================================================
# Constants
# =============================================================================

# Intent types
INTENT_WELFARE_SEARCH = "welfare_search"
INTENT_POLICY_DETAIL = "policy_detail"
INTENT_CHECKLIST = "checklist"
INTENT_REASONING = "reasoning"
INTENT_PLAIN_LANGUAGE = "plain_language"
INTENT_SCENARIO = "scenario"
INTENT_GENERAL_QUESTION = "general_question"
INTENT_CHITCHAT = "chitchat"
INTENT_UNKNOWN = "unknown"

# Required fields for welfare search
REQUIRED_FIELDS = ["region", "life_cycle"]
OPTIONAL_FIELDS = ["age_group", "interest"]

FIELD_QUESTIONS = {
    "region": "어느 지역에 거주하고 계신가요? (예: 서울, 경기, 부산 등)",
    "life_cycle": "현재 상황에 해당하는 것이 있으신가요? (예: 임신/출산, 영유아 양육, 청년, 중장년, 노년 등)",
    "age_group": "연령대가 어떻게 되시나요? (예: 20대, 30대, 40대 등)",
    "interest": "어떤 분야의 지원이 필요하신가요? (예: 주거, 취업, 금융, 건강, 교육 등)",
}

FIELD_KOREAN = {
    "region": "지역",
    "life_cycle": "생애주기",
    "age_group": "연령대",
    "interest": "관심분야",
}

# Region normalization (short -> full name) - 지역은 명확한 매핑이 필요
REGION_NORMALIZE = {
    "서울": "서울특별시", "경기": "경기도", "부산": "부산광역시",
    "대구": "대구광역시", "인천": "인천광역시", "광주": "광주광역시",
    "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
    "강원": "강원도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전라북도", "전남": "전라남도", "경북": "경상북도",
    "경남": "경상남도", "제주": "제주특별자치도"
}

# Chitchat responses
CHITCHAT_RESPONSES = {
    "greeting": "안녕하세요! 복지 정책 검색을 도와드릴게요. 어떤 복지 정보가 필요하신가요?",
    "thanks": "도움이 되셨다니 기쁩니다! 더 궁금한 점이 있으시면 말씀해주세요.",
    "bye": "이용해 주셔서 감사합니다. 좋은 하루 되세요!",
    "default": "네, 무엇을 도와드릴까요? 복지 정책 검색이 필요하시면 말씀해주세요."
}

# Fallback messages
FALLBACK_MESSAGES = [
    "죄송합니다, 잘 이해하지 못했어요. 복지 정책 검색이 필요하시면 '복지 정책 찾아줘'라고 말씀해주세요.",
    "무슨 말씀이신지 잘 모르겠어요. 예를 들어 '서울에서 받을 수 있는 육아 지원금 알려줘'처럼 질문해주시면 도움드릴 수 있어요.",
    "계속 이해하기 어려운 것 같아요. 혹시 복지 정책 검색 외에 다른 도움이 필요하시면 상담원 연결을 요청해주세요."
]

MAX_FALLBACK_COUNT = 3

# Agent Labels for UI
AGENT_LABELS = {
    INTENT_WELFARE_SEARCH: "🔍 [맞춤 검색]",
    INTENT_CHECKLIST: "📋 [서류 안내]",
    INTENT_REASONING: "💰 [혜택 계산]",
    INTENT_PLAIN_LANGUAGE: "🖋️ [쉬운 설명]",
    INTENT_SCENARIO: "🔮 [상황 예측]",
}


# =============================================================================
# Conversation Flow Class
# =============================================================================

class ConversationFlow:
    """LangGraph-based conversation orchestration manager"""

    def __init__(self, qdrant_service=None):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")

        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            temperature=0
        )
        self.rag_service = RAGService(qdrant_service=qdrant_service)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow with intent routing"""
        workflow = StateGraph(ConversationState)

        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("extract_info", self._extract_info)
        workflow.add_node("check_requirements", self._check_requirements)
        workflow.add_node("ask_question", self._ask_question)
        workflow.add_node("prepare_search", self._prepare_search)
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("handle_chitchat", self._handle_chitchat)
        workflow.add_node("handle_general_question", self._handle_general_question)
        workflow.add_node("handle_welfare_search", self._handle_welfare_search)
        workflow.add_node("handle_policy_detail", self._handle_policy_detail)
        workflow.add_node("handle_checklist", self._handle_checklist)
        workflow.add_node("handle_reasoning", self._handle_reasoning)
        workflow.add_node("handle_plain_language", self._handle_plain_language)
        workflow.add_node("handle_scenario", self._handle_scenario)
        workflow.add_node("handle_fallback", self._handle_fallback)

        # Set entry point
        workflow.set_entry_point("classify_intent")

        # Route based on intent
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "welfare_search": "extract_info",
                "policy_detail": "retrieve_context",
                "checklist": "retrieve_context",
                "reasoning": "retrieve_context",
                "plain_language": "retrieve_context",
                "scenario": "retrieve_context",
                "general_question": "handle_general_question",
                "chitchat": "handle_chitchat",
                "fallback": "handle_fallback"
            }
        )

        # Welfare search flow
        workflow.add_edge("extract_info", "check_requirements")
        workflow.add_conditional_edges(
            "check_requirements",
            self._route_after_check,
            {
                "ask": "ask_question",
                "search": "prepare_search"
            }
        )
        workflow.add_edge("ask_question", END)
        workflow.add_edge("prepare_search", "retrieve_context")
        
        # Route AFTER retrieval based on intent
        workflow.add_conditional_edges(
            "retrieve_context",
            self._route_after_retrieval,
            {
                "welfare_search": "handle_welfare_search",
                "policy_detail": "handle_policy_detail",
                "checklist": "handle_checklist",
                "reasoning": "handle_reasoning",
                "plain_language": "handle_plain_language",
                "scenario": "handle_scenario",
                "end": END
            }
        )

        # All final nodes go to END
        workflow.add_edge("handle_chitchat", END)
        workflow.add_edge("handle_general_question", END)
        workflow.add_edge("handle_welfare_search", END)
        workflow.add_edge("handle_policy_detail", END)
        workflow.add_edge("handle_checklist", END)
        workflow.add_edge("handle_reasoning", END)
        workflow.add_edge("handle_plain_language", END)
        workflow.add_edge("handle_scenario", END)
        workflow.add_edge("handle_fallback", END)

        return workflow.compile()

    # =========================================================================
    # Intent Classification (LLM-based)
    # =========================================================================

    def _classify_intent(self, state: ConversationState) -> dict:
        """Classify user intent with context awareness"""
        messages = state["messages"]
        current_profile = state.get("user_profile", {})
        previous_intent = state.get("intent", "")

        latest_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                latest_msg = msg.content
                break

        last_reply = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_reply = msg.content
                break

        # 0. Prioritize intent from focus_policy_id (e.g. from dashboard click)
        focus_policy_id = state.get("agent_data", {}).get("focus_policy_id")
        if focus_policy_id and previous_intent == INTENT_POLICY_DETAIL:
            # Check if user message is a follow-up or a new query
            # If short/generic, keep policy_detail to allow detailed view
            if len(latest_msg) < 10 or "상세" in latest_msg or "가르쳐" in latest_msg or "알려" in latest_msg:
                 return {"intent": INTENT_POLICY_DETAIL}

        # If we're in the middle of collecting info for welfare_search, continue that flow
        if previous_intent == INTENT_WELFARE_SEARCH:
            missing = [f for f in REQUIRED_FIELDS if not current_profile.get(f)]
            if missing:
                return {"intent": INTENT_WELFARE_SEARCH}

        # Stickiness for specialty agents: If user says "Yes/No" or very short answer
        # to a specialty agent's question, keep the same intent.
        specialty_intents = [INTENT_CHECKLIST, INTENT_REASONING, INTENT_PLAIN_LANGUAGE, INTENT_SCENARIO]
        if previous_intent in specialty_intents:
            short_answers = ["예", "아니오", "네", "아니요", "응", "아니", "yes", "no", "ok", "알았어", "확인"]
            clean_msg = latest_msg.strip().lower()
            if clean_msg in short_answers or len(clean_msg) <= 5:
                # Keep specialty intent for follow-ups
                return {"intent": previous_intent}

        # Quick check for chitchat (no LLM needed)
        if self._is_chitchat(latest_msg):
            return {"intent": INTENT_CHITCHAT, "fallback_count": 0}

        # Quick check for policy ID
        if re.search(r'WLF\d+', latest_msg):
            return {"intent": INTENT_POLICY_DETAIL, "fallback_count": 0}

        # Use LLM with context for intent classification
        intent = self._llm_classify_intent(latest_msg, previous_intent, last_reply)
        
        # Console Logging for visibility
        if intent in AGENT_LABELS:
            print(f"--- [AGENT TRIGGERED] ---")
            print(f"User: \"{latest_msg}\"")
            print(f"Agent: {AGENT_LABELS[intent]}")
            print(f"--------------------------")

        return {"intent": intent, "fallback_count": 0}

    def _is_chitchat(self, message: str) -> bool:
        """Quick rule-based chitchat detection"""
        msg_lower = message.lower().strip()
        chitchat_patterns = [
            "안녕", "하이", "헬로", "hi", "hello", "반가",
            "감사", "고마워", "땡큐", "thank",
            "잘가", "바이", "bye", "다음에", "안녕히"
        ]
        return any(p in msg_lower for p in chitchat_patterns)

    def _llm_classify_intent(self, message: str, previous_intent: str = "", last_reply: str = "") -> str:
        """LLM-based intent classification with context"""
        prompt = build_intent_classification_prompt(message, previous_intent, last_reply)

        try:
            response = self.llm.invoke([
                SystemMessage(content=INTENT_CLASSIFICATION_SYSTEM),
                HumanMessage(content=prompt)
            ])
            intent = response.content.strip().lower()

            valid_intents = [
                INTENT_WELFARE_SEARCH, INTENT_POLICY_DETAIL,
                INTENT_CHECKLIST, INTENT_REASONING,
                INTENT_PLAIN_LANGUAGE, INTENT_SCENARIO,
                INTENT_GENERAL_QUESTION, INTENT_CHITCHAT, INTENT_UNKNOWN
            ]
            if intent in valid_intents:
                return intent
        except Exception:
            pass

        return INTENT_UNKNOWN

    def _route_by_intent(self, state: ConversationState) -> str:
        """Route based on classified intent"""
        intent = state.get("intent", INTENT_UNKNOWN)

        if intent == INTENT_WELFARE_SEARCH:
            return "welfare_search"
        elif intent == INTENT_POLICY_DETAIL:
            return "policy_detail"
        elif intent == INTENT_CHECKLIST:
            return "checklist"
        elif intent == INTENT_REASONING:
            return "reasoning"
        elif intent == INTENT_PLAIN_LANGUAGE:
            return "plain_language"
        elif intent == INTENT_SCENARIO:
            return "scenario"
        elif intent == INTENT_GENERAL_QUESTION:
            return "general_question"
        elif intent == INTENT_CHITCHAT:
            return "chitchat"
        else:
            return "fallback"

    # =========================================================================
    # Slot Filling (LLM-based)
    # =========================================================================

    def _extract_info(self, state: ConversationState) -> dict:
        """Extract user information using LLM"""
        messages = state["messages"]
        current_profile = state.get("user_profile", {})

        # Get all conversation context for better extraction
        conversation_text = "\n".join([
            f"{'사용자' if isinstance(m, HumanMessage) else 'AI'}: {m.content}"
            for m in messages[-6:]  # Last 6 messages for context
        ])

        # LLM extraction
        updated_profile = self._llm_extract_slots(conversation_text, current_profile)

        return {"user_profile": updated_profile}

    def _llm_extract_slots(self, conversation: str, current_profile: dict) -> dict:
        """LLM-based slot extraction"""
        prompt = build_slot_extraction_prompt(
            conversation=conversation,
            current_region=current_profile.get('region', '미수집'),
            current_life_cycle=current_profile.get('life_cycle', '미수집'),
            current_age_group=current_profile.get('age_group', '미수집'),
            current_interest=current_profile.get('interest', '미수집')
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=SLOT_EXTRACTION_SYSTEM),
                HumanMessage(content=prompt)
            ])

            content = response.content
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                content = json_match.group()

            extracted = json.loads(content)
            updated_profile = {**current_profile}

            for key, value in extracted.items():
                # Only update if new value exists AND field is not already collected
                if value and value.strip() and not current_profile.get(key):
                    normalized = value.strip()
                    # Normalize region names
                    if key == "region":
                        normalized = REGION_NORMALIZE.get(normalized, normalized)
                    updated_profile[key] = normalized

            return updated_profile

        except Exception:
            return current_profile

    # =========================================================================
    # Requirements Check & Question Asking
    # =========================================================================

    def _check_requirements(self, state: ConversationState) -> dict:
        """Check if required information is collected"""
        profile = state.get("user_profile", {})

        missing = []
        for field in REQUIRED_FIELDS:
            if not profile.get(field):
                missing.append(field)

        return {
            "missing_fields": missing,
            "ready_to_search": len(missing) == 0
        }

    def _route_after_check(self, state: ConversationState) -> Literal["ask", "search"]:
        """Route based on whether requirements are met"""
        if state["ready_to_search"]:
            return "search"
        return "ask"

    def _ask_question(self, state: ConversationState) -> dict:
        """Generate question for missing information"""
        missing = state["missing_fields"]

        if missing:
            field = missing[0]
            question = FIELD_QUESTIONS.get(field, f"{FIELD_KOREAN.get(field, field)}을(를) 알려주세요.")
            return {"messages": [AIMessage(content=question)]}

        return {}

    # =========================================================================
    # Search Preparation
    # =========================================================================

    def _prepare_search(self, state: ConversationState) -> dict:
        """Prepare search query from collected information"""
        profile = state.get("user_profile", {})
        messages = state["messages"]

        # Get the original user query (first user message about welfare)
        user_queries = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                user_queries.append(msg.content)

        # Build search context
        search_parts = []

        if user_queries:
            first_query = user_queries[0]
            if len(first_query) > 5:
                search_parts.append(first_query)

        if profile.get("region"):
            search_parts.append(f"지역: {profile['region']}")
        if profile.get("life_cycle"):
            search_parts.append(f"생애주기: {profile['life_cycle']}")
        if profile.get("interest"):
            search_parts.append(f"분야: {profile['interest']}")

        search_query = " ".join(search_parts)

        # 수집된 정보 요약 메시지 추가
        collected_info = ", ".join([
            f"{FIELD_KOREAN.get(k, k)}: {v}"
            for k, v in profile.items() if v
        ])
        msg_content = f"알겠습니다. [{collected_info}] 조건으로 맞춤 정책을 검색해드릴게요."

        return {
            "search_query": search_query,
            "messages": [AIMessage(content=collected_info)]
        }

    # =========================================================================
    # Context Retrieval Node
    # =========================================================================

    def _retrieve_context(self, state: ConversationState) -> dict:
        """Retrieve policy context using RAGService"""
        query = state.get("search_query")
        
        # If no explicit search query (e.g. from specialized agent), use the last message
        if not query:
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    query = msg.content
                    break
        
        # 1. Prioritize pre-loaded policy ID (from dashboard click)
        focus_policy_id = state.get("agent_data", {}).get("focus_policy_id")
        
        # 1.1 Extract ID from query if not explicitly provided in agent_data
        if not focus_policy_id and query:
            # Match patterns like WLF00001234
            id_match = re.search(r"WLF\d{8}", query)
            if id_match:
                focus_policy_id = id_match.group(0)
                print(f"--- [RETRIEVE] Automatically extracted policy ID: {focus_policy_id} ---")

        # If we have a specific policy ID to focus on, use it directly
        if focus_policy_id:
            print(f"--- [RETRIEVE] Fetching specific policy ID: {focus_policy_id} ---")
            docs = self.rag_service.retrieve_context_by_id(focus_policy_id)
            if docs:
                print(f"--- [RETRIEVE] Found policy by ID: {focus_policy_id} ---")
                return {"retrieved_docs": docs}
            else:
                print(f"--- [RETRIEVE] Policy ID {focus_policy_id} not found ---")

        # 2. General Query-based Retrieval
        print(f"--- [RETRIEVING CONTEXT] Query: '{query}' ---")
        
        if not query:
            print("--- [RETRIEVE] No query found, skipping ---")
            return {"retrieved_docs": []}

        profile = state.get("user_profile", {})
        filters = {
            "province": profile.get("region"),
            "life_cycle": profile.get("life_cycle")
        }

        # Use RAGService to get enriched policy docs
        try:
            docs = self.rag_service.retrieve_context(
                query=query,
                filters=filters,
                top_k=5
            )
            print(f"--- [RETRIEVE] Found {len(docs)} docs ---")
        except Exception as e:
            print(f"--- [RETRIEVE ERROR] {str(e)} ---")
            docs = []

        return {"retrieved_docs": docs}

    def _route_after_retrieval(self, state: ConversationState) -> str:
        """Route to actual agent node or END after retrieval"""
        intent = state.get("intent", INTENT_UNKNOWN)
        
        if intent == INTENT_WELFARE_SEARCH:
            return "welfare_search"
        elif intent == INTENT_CHECKLIST:
            return "checklist"
        elif intent == INTENT_REASONING:
            return "reasoning"
        elif intent == INTENT_PLAIN_LANGUAGE:
            return "plain_language"
        elif intent == INTENT_SCENARIO:
            return "scenario"
        elif intent == INTENT_POLICY_DETAIL:
            return "policy_detail"
        
        return "end"

    def _handle_welfare_search(self, state: ConversationState) -> dict:
        """Node for welfare search response generation"""
        docs = state.get("retrieved_docs", [])
        context = self.rag_service.build_context_prompt(docs)
        
        last_msg = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_msg = msg.content
                break
        
        try:
            answer = self.rag_service.generate_response(last_msg, context)
        except Exception:
            answer = "죄송합니다, 정책 정보를 처리하는 중 문제가 발생했습니다."
            
        return {"messages": [AIMessage(content=answer)]}

    def _handle_policy_detail(self, state: ConversationState) -> dict:
        """Node for policy detail response generation"""
        docs = state.get("retrieved_docs", [])
        
        if docs:
            # use the first doc for detail
            context = self.rag_service.build_context_prompt(docs[:1])
            answer = f"신청하신 정책의 상세 내용입니다.\n\n{context}"
        else:
            answer = "해당 정책 정보를 찾을 수 없습니다."
            
        return {"messages": [AIMessage(content=answer)]}

    # =========================================================================
    # Specialized Agent Handlers (Context-Aware)
    # =========================================================================

    def _handle_checklist(self, state: ConversationState) -> dict:
        """Handle checklist agent with retrieved context"""
        print("--- [AGENT] Checklist Node ---")
        messages = state["messages"]
        docs = state.get("retrieved_docs", [])
        context = self.rag_service.build_context_prompt(docs)

        try:
            response = self.llm.invoke([
                SystemMessage(content=CHECKLIST_AGENT_SYSTEM),
                HumanMessage(content=f"정책 문맥:\n{context}\n\n위 정보를 바탕으로 대화를 이어가세요."),
                *messages[-5:]
            ])
            answer = response.content
            print(f"--- [AGENT] Checklist Response: {answer[:50]}... ---")
        except Exception as e:
            print(f"--- [AGENT ERROR] {str(e)} ---")
            answer = "죄송합니다, 서류 안내를 처리하는 중 문제가 발생했습니다."

        return {"messages": [AIMessage(content=answer)]}

    def _handle_reasoning(self, state: ConversationState) -> dict:
        """Handle reasoning agent with retrieved context"""
        messages = state["messages"]
        docs = state.get("retrieved_docs", [])
        context = self.rag_service.build_context_prompt(docs)

        try:
            response = self.llm.invoke([
                SystemMessage(content=REASONING_AGENT_SYSTEM),
                HumanMessage(content=f"정책 문맥:\n{context}\n\n위 정보를 바탕으로 대화를 이어가세요."),
                *messages[-5:]
            ])
            answer = response.content
        except Exception:
            answer = "죄송합니다, 지원금 계산 중 문제가 발생했습니다."

        return {"messages": [AIMessage(content=answer)]}

    def _handle_plain_language(self, state: ConversationState) -> dict:
        """Handle plain language agent with retrieved context"""
        messages = state["messages"]
        docs = state.get("retrieved_docs", [])
        context = self.rag_service.build_context_prompt(docs)

        try:
            response = self.llm.invoke([
                SystemMessage(content=PLAIN_LANGUAGE_AGENT_SYSTEM),
                HumanMessage(content=f"정책 문맥:\n{context}\n\n위 정보를 바탕으로 대화를 이어가세요."),
                *messages[-5:]
            ])
            answer = response.content
        except Exception:
            answer = "죄송합니다, 용어 설명을 처리하는 중 문제가 발생했습니다."

        return {"messages": [AIMessage(content=answer)]}

    def _handle_scenario(self, state: ConversationState) -> dict:
        """Handle scenario agent with retrieved context"""
        messages = state["messages"]
        docs = state.get("retrieved_docs", [])
        context = self.rag_service.build_context_prompt(docs)

        try:
            response = self.llm.invoke([
                SystemMessage(content=SCENARIO_AGENT_SYSTEM),
                HumanMessage(content=f"정책 문맥:\n{context}\n\n위 정보를 바탕으로 대화를 이어가세요."),
                *messages[-5:]
            ])
            answer = response.content
        except Exception:
            answer = "죄송합니다, 시나리오 분석 중 문제가 발생했습니다."

        return {"messages": [AIMessage(content=answer)]}

    # =========================================================================
    # Chitchat Handler (Restored)
    # =========================================================================

    def _handle_chitchat(self, state: ConversationState) -> dict:
        """Handle chitchat/greetings with personalization"""
        messages = state["messages"]
        profile = state.get("user_profile", {})
        latest_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                latest_msg = msg.content.lower()
                break

        if any(g in latest_msg for g in ["안녕", "하이", "헬로", "hi", "hello"]):
            if profile.get("region") and profile.get("life_cycle"):
                response = f"안녕하세요! {profile['region']}에 거주하시는 {profile['life_cycle']}님을 위한 맞춤 복지 정보를 찾아드릴게요. 무엇이 궁금하신가요?"
            elif profile.get("region"):
                response = f"안녕하세요! {profile['region']}의 복지 정책 전문가 베니입니다. 어떤 도움이 필요하신가요?"
            else:
                response = CHITCHAT_RESPONSES["greeting"]
        elif any(t in latest_msg for t in ["감사", "고마워", "땡큐", "thank"]):
            response = CHITCHAT_RESPONSES["thanks"]
        elif any(b in latest_msg for b in ["잘가", "바이", "bye"]):
            response = CHITCHAT_RESPONSES["bye"]
        else:
            response = CHITCHAT_RESPONSES["default"]

        return {"messages": [AIMessage(content=response)]}

    # =========================================================================
    # General Question Handler (Restored)
    # =========================================================================

    def _handle_general_question(self, state: ConversationState) -> dict:
        """Handle general welfare-related questions"""
        messages = state["messages"]
        latest_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                latest_msg = msg.content
                break

        prompt = build_general_question_prompt(latest_msg)

        try:
            response = self.llm.invoke([
                SystemMessage(content=GENERAL_QUESTION_SYSTEM),
                HumanMessage(content=prompt)
            ])
            answer = response.content
        except Exception:
            answer = "죄송합니다, 답변을 생성하는 데 문제가 발생했어요. 구체적인 복지 정책이 궁금하시면 '복지 정책 검색해줘'라고 말씀해주세요."

        return {"messages": [AIMessage(content=answer)]}

    # =========================================================================
    # Fallback Handler
    # =========================================================================

    def _handle_fallback(self, state: ConversationState) -> dict:
        """Handle unrecognized intents"""
        fallback_count = state.get("fallback_count", 0) + 1

        idx = min(fallback_count - 1, len(FALLBACK_MESSAGES) - 1)
        response = FALLBACK_MESSAGES[idx]

        return {
            "messages": [AIMessage(content=response)],
            "fallback_count": fallback_count,
            "ready_to_search": False
        }

    # =========================================================================
    # Main Process Method
    # =========================================================================

    def process(
        self,
        user_message: str,
        session_state: Optional[dict] = None,
        pre_load_policy_id: Optional[str] = None
    ) -> dict:
        """
        Process user message and return response

        Args:
            user_message: User's input message
            session_state: Previous session state (for multi-turn)
            pre_load_policy_id: Optional policy ID to focus on (dashboard integration)

        Returns:
            {
                "response": str,           # AI response message
                "intent": str,             # Detected intent
                "ready_to_search": bool,   # Whether to trigger search
                "search_query": str,       # Query for policy search
                "user_profile": dict,      # Collected user info
                "session_state": dict      # State to persist for next turn
            }
        """
        # Initialize or restore state
        if session_state:
            state = {
                "messages": [
                    m if not isinstance(m, dict) else (
                        HumanMessage(content=m["content"]) if m.get("role") == "user"
                        else AIMessage(content=m["content"])
                    )
                    for m in session_state.get("messages", [])
                ],
                "user_profile": session_state.get("user_profile", {}),
                "intent": session_state.get("intent", ""),
                "missing_fields": [],
                "ready_to_search": False,
                "search_query": "",
                "policy_id": "",
                "agent_data": session_state.get("agent_data", {}),
                "fallback_count": session_state.get("fallback_count", 0),
                "retrieved_docs": session_state.get("retrieved_docs", [])
            }
        else:
            state = {
                "messages": [],
                "user_profile": {},
                "intent": "",
                "missing_fields": [],
                "ready_to_search": False,
                "search_query": "",
                "policy_id": "",
                "agent_data": {},
                "fallback_count": 0,
                "retrieved_docs": []
            }

        # Add new user message
        if user_message:
            state["messages"].append(HumanMessage(content=user_message))

        # Handle contextual pre-loading
        # Handle contextual pre-loading
        if pre_load_policy_id:
            state["intent"] = INTENT_POLICY_DETAIL
            if "agent_data" not in state:
                state["agent_data"] = {}
            state["agent_data"]["focus_policy_id"] = pre_load_policy_id
            
            # Make sure we don't treat this as a generic search
            state["search_query"] = ""
            
            # If no message from user, but policy pre-loaded, trigger specialized response
            if not user_message:
                state["messages"].append(HumanMessage(content=f"정책 ID {pre_load_policy_id}에 대해 대화를 시작해줘"))

        # Run graph
        print(f"--- [RUNNING GRAPH] Intent: {state['intent']} ---")
        result = self.graph.invoke(state)
        print(f"--- [GRAPH COMPLETE] Final Intent: {result['intent']} ---")

        # Get AI response and prepend label for specialty agents
        ai_response = ""
        intent = result["intent"]
        
        print(f"--- [POST-GRAPH] Messages Count: {len(result['messages'])} ---")
        
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                ai_response = msg.content
                print(f"--- [POST-GRAPH] AI Response Found: {ai_response[:50]}... ---")
                # Prepend agent label if it's a specialty agent
                if intent in AGENT_LABELS:
                    label = AGENT_LABELS[intent]
                    if not ai_response.startswith(label):
                        ai_response = f"{label}\n{ai_response}"
                break
        
        if not ai_response:
            print("--- [POST-GRAPH WARNING] No AI message found in state! ---")

        # Build session state for persistence
        new_session_state = {
            "messages": [
                {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                for m in result["messages"]
            ],
            "user_profile": result["user_profile"],
            "intent": result["intent"],
            "agent_data": result.get("agent_data", {}),
            "fallback_count": result.get("fallback_count", 0)
        }

        return {
            "response": ai_response,
            "intent": result["intent"],
            "ready_to_search": len(result.get("retrieved_docs", [])) > 0,
            "search_query": result.get("search_query", ""),
            "user_profile": result["user_profile"],
            "retrieved_docs": result.get("retrieved_docs", []),
            "agent_data": result.get("agent_data", {}),
            "session_state": new_session_state
        }
