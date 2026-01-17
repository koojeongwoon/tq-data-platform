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
from shared.prompts import (
    INTENT_CLASSIFICATION_SYSTEM,
    SLOT_EXTRACTION_SYSTEM,
    GENERAL_QUESTION_SYSTEM,
    build_intent_classification_prompt,
    build_slot_extraction_prompt,
    build_general_question_prompt,
)


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
    intent: str                    # welfare_search, policy_detail, general_question, chitchat, unknown
    missing_fields: list[str]
    ready_to_search: bool
    search_query: str
    policy_id: str                 # For policy_detail intent
    fallback_count: int            # Track consecutive fallbacks


# =============================================================================
# Constants
# =============================================================================

# Intent types
INTENT_WELFARE_SEARCH = "welfare_search"
INTENT_POLICY_DETAIL = "policy_detail"
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


# =============================================================================
# Conversation Flow Class
# =============================================================================

class ConversationFlow:
    """LangGraph-based conversation orchestration manager"""

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")

        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            temperature=0
        )
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
        workflow.add_node("handle_chitchat", self._handle_chitchat)
        workflow.add_node("handle_general_question", self._handle_general_question)
        workflow.add_node("handle_fallback", self._handle_fallback)

        # Set entry point
        workflow.set_entry_point("classify_intent")

        # Route based on intent
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "welfare_search": "extract_info",
                "policy_detail": "prepare_search",
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
        workflow.add_edge("prepare_search", END)

        # Other flows end directly
        workflow.add_edge("handle_chitchat", END)
        workflow.add_edge("handle_general_question", END)
        workflow.add_edge("handle_fallback", END)

        return workflow.compile()

    # =========================================================================
    # Intent Classification (LLM-based)
    # =========================================================================

    def _classify_intent(self, state: ConversationState) -> ConversationState:
        """Classify user intent"""
        messages = state["messages"]
        current_profile = state.get("user_profile", {})
        previous_intent = state.get("intent", "")

        latest_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                latest_msg = msg.content
                break

        # If we're in the middle of collecting info for welfare_search, continue that flow
        # This handles follow-up answers like "서울", "서울에 살고 있어", "임신 중이에요"
        if previous_intent == INTENT_WELFARE_SEARCH:
            missing = [f for f in REQUIRED_FIELDS if not current_profile.get(f)]
            if missing:
                # Still collecting info, keep welfare_search intent
                state["intent"] = INTENT_WELFARE_SEARCH
                return state

        # Quick check for chitchat (no LLM needed)
        if self._is_chitchat(latest_msg):
            state["intent"] = INTENT_CHITCHAT
            state["fallback_count"] = 0
            return state

        # Quick check for policy ID
        if re.search(r'WLF\d+', latest_msg):
            state["intent"] = INTENT_POLICY_DETAIL
            state["fallback_count"] = 0
            return state

        # Use LLM for intent classification
        intent = self._llm_classify_intent(latest_msg)
        state["intent"] = intent

        if intent != INTENT_UNKNOWN:
            state["fallback_count"] = 0

        return state

    def _is_chitchat(self, message: str) -> bool:
        """Quick rule-based chitchat detection"""
        msg_lower = message.lower().strip()
        chitchat_patterns = [
            "안녕", "하이", "헬로", "hi", "hello", "반가",
            "감사", "고마워", "땡큐", "thank",
            "잘가", "바이", "bye", "다음에", "안녕히"
        ]
        return any(p in msg_lower for p in chitchat_patterns)

    def _llm_classify_intent(self, message: str) -> str:
        """LLM-based intent classification"""
        prompt = build_intent_classification_prompt(message)

        try:
            response = self.llm.invoke([
                SystemMessage(content=INTENT_CLASSIFICATION_SYSTEM),
                HumanMessage(content=prompt)
            ])
            intent = response.content.strip().lower()

            valid_intents = [INTENT_WELFARE_SEARCH, INTENT_POLICY_DETAIL,
                          INTENT_GENERAL_QUESTION, INTENT_CHITCHAT, INTENT_UNKNOWN]
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
        elif intent == INTENT_GENERAL_QUESTION:
            return "general_question"
        elif intent == INTENT_CHITCHAT:
            return "chitchat"
        else:
            return "fallback"

    # =========================================================================
    # Slot Filling (LLM-based)
    # =========================================================================

    def _extract_info(self, state: ConversationState) -> ConversationState:
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

        state["user_profile"] = updated_profile
        return state

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

        except (json.JSONDecodeError, Exception):
            return current_profile

    # =========================================================================
    # Requirements Check & Question Asking
    # =========================================================================

    def _check_requirements(self, state: ConversationState) -> ConversationState:
        """Check if required information is collected"""
        profile = state.get("user_profile", {})

        missing = []
        for field in REQUIRED_FIELDS:
            if not profile.get(field):
                missing.append(field)

        state["missing_fields"] = missing
        state["ready_to_search"] = len(missing) == 0

        return state

    def _route_after_check(self, state: ConversationState) -> Literal["ask", "search"]:
        """Route based on whether requirements are met"""
        if state["ready_to_search"]:
            return "search"
        return "ask"

    def _ask_question(self, state: ConversationState) -> ConversationState:
        """Generate question for missing information"""
        missing = state["missing_fields"]

        if missing:
            field = missing[0]
            question = FIELD_QUESTIONS.get(field, f"{FIELD_KOREAN.get(field, field)}을(를) 알려주세요.")
            state["messages"].append(AIMessage(content=question))

        return state

    # =========================================================================
    # Search Preparation
    # =========================================================================

    def _prepare_search(self, state: ConversationState) -> ConversationState:
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

        # Add original query if it's substantive
        if user_queries:
            first_query = user_queries[0]
            if len(first_query) > 5:  # Skip short answers like "서울"
                search_parts.append(first_query)

        if profile.get("region"):
            search_parts.append(f"지역: {profile['region']}")
        if profile.get("life_cycle"):
            search_parts.append(f"생애주기: {profile['life_cycle']}")
        if profile.get("interest"):
            search_parts.append(f"분야: {profile['interest']}")

        state["search_query"] = " ".join(search_parts)

        # Add confirmation message
        collected_info = ", ".join([
            f"{FIELD_KOREAN.get(k, k)}: {v}"
            for k, v in profile.items() if v
        ])
        state["messages"].append(
            AIMessage(content=f"알겠습니다. [{collected_info}] 조건으로 맞춤 정책을 검색해드릴게요.")
        )

        return state

    # =========================================================================
    # Chitchat Handler
    # =========================================================================

    def _handle_chitchat(self, state: ConversationState) -> ConversationState:
        """Handle chitchat/greetings"""
        messages = state["messages"]
        latest_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                latest_msg = msg.content.lower()
                break

        if any(g in latest_msg for g in ["안녕", "하이", "헬로", "hi", "hello"]):
            response = CHITCHAT_RESPONSES["greeting"]
        elif any(t in latest_msg for t in ["감사", "고마워", "땡큐", "thank"]):
            response = CHITCHAT_RESPONSES["thanks"]
        elif any(b in latest_msg for b in ["잘가", "바이", "bye"]):
            response = CHITCHAT_RESPONSES["bye"]
        else:
            response = CHITCHAT_RESPONSES["default"]

        state["messages"].append(AIMessage(content=response))
        state["ready_to_search"] = False

        return state

    # =========================================================================
    # General Question Handler
    # =========================================================================

    def _handle_general_question(self, state: ConversationState) -> ConversationState:
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

        state["messages"].append(AIMessage(content=answer))
        state["ready_to_search"] = False

        return state

    # =========================================================================
    # Fallback Handler
    # =========================================================================

    def _handle_fallback(self, state: ConversationState) -> ConversationState:
        """Handle unrecognized intents"""
        fallback_count = state.get("fallback_count", 0) + 1
        state["fallback_count"] = fallback_count

        idx = min(fallback_count - 1, len(FALLBACK_MESSAGES) - 1)
        response = FALLBACK_MESSAGES[idx]

        state["messages"].append(AIMessage(content=response))
        state["ready_to_search"] = False

        return state

    # =========================================================================
    # Main Process Method
    # =========================================================================

    def process(
        self,
        user_message: str,
        session_state: Optional[dict] = None
    ) -> dict:
        """
        Process user message and return response

        Args:
            user_message: User's input message
            session_state: Previous session state (for multi-turn)

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
                    HumanMessage(content=m["content"]) if m["role"] == "user"
                    else AIMessage(content=m["content"])
                    for m in session_state.get("messages", [])
                ],
                "user_profile": session_state.get("user_profile", {}),
                "intent": session_state.get("intent", ""),
                "missing_fields": [],
                "ready_to_search": False,
                "search_query": "",
                "policy_id": "",
                "fallback_count": session_state.get("fallback_count", 0)
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
                "fallback_count": 0
            }

        # Add new user message
        state["messages"].append(HumanMessage(content=user_message))

        # Run graph
        result = self.graph.invoke(state)

        # Get AI response
        ai_response = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                ai_response = msg.content
                break

        # Build session state for persistence
        new_session_state = {
            "messages": [
                {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                for m in result["messages"]
            ],
            "user_profile": result["user_profile"],
            "intent": result["intent"],
            "fallback_count": result.get("fallback_count", 0)
        }

        return {
            "response": ai_response,
            "intent": result["intent"],
            "ready_to_search": result["ready_to_search"],
            "search_query": result.get("search_query", ""),
            "user_profile": result["user_profile"],
            "session_state": new_session_state
        }
