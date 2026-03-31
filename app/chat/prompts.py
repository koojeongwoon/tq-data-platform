"""Chat-domain specific prompts (Orchestration & Intents)"""

# =============================================================================
# Intent Classification Prompts
# =============================================================================

INTENT_CLASSIFICATION_SYSTEM = "의도 분류 AI입니다. 키워드만 응답하세요."


def build_intent_classification_prompt(message: str, previous_intent: str = "", last_reply: str = "") -> str:
    """Build prompt for intent classification with context"""
    context_str = ""
    if previous_intent:
        context_str += f"\n이전 의도: {previous_intent}"
    if last_reply:
        context_str += f"\n최근 AI 답변: \"{last_reply}\""

    return f"""사용자 메시지의 의도를 분류하세요. {context_str}
    
사용자 메시지: "{message}"

가능한 의도:
1. welfare_search: 복지 정책/지원금/혜택을 찾거나 검색하려는 의도
   - 예: "육아 지원금 알려줘", "청년 혜택 뭐있어?"
   - 지역, 생애주기(임신, 육아, 청년, 노인 등), 관심분야 언급 시 해당
2. policy_detail: 특정 정책의 상세 내용(신청 방법, 대상 등)을 묻는 의도
   - 예: "이 정책 자세히 알려줘", "신청 방법이 뭐야?"
3. checklist: 서류 준비나 신청 자격 체크리스트가 필요한 의도 (이전 답변이 질문인 경우 답변도 포함)
   - 예: "어떤 서류 준비해야 돼?", "필요한 서류 알려줘", "체크리스트 만들어줘"
4. reasoning: 복합 조건 필터링이나 지원금 계산이 필요한 의도
   - 예: "나는 얼마 받을 수 있어?", "내 조건이면 혜택이 어떻게 돼?", "가구원이 3명인데 계산해줘"
5. plain_language: 어려운 용어 설명이나 요약이 필요한 의도
   - 예: "중위소득이 뭐야?", "어렵게 설명된 거 좀 쉽게 풀어서 말해줘", "한 줄 요약해줘"
6. scenario: 가상 상황(퇴사, 이사, 결혼 등)에 따른 변화 시뮬레이션
   - 예: "내가 직장을 그만두면 어떻게 돼?", "다른 지역으로 이사 가면 혜택이 바뀌나?"
7. general_question: 복지 관련 일반 질문
   - 예: "복지란 무엇인가요?", "어디서 신청하나요?"
8. chitchat: 인사, 잡담, 감사, 또는 이전 질문에 대한 단순 긍정/부정(예, 아니오)
   - 중요: 이전 의도가 전문 에이전트(checklist, reasoning 등)이고 사용자가 그 질문에 답하는 것이라면 해당 전문 에이전트 의도를 유지하세요.
9. unknown: 위 어느 것에도 해당하지 않음

의도 키워드만 응답 (welfare_search, policy_detail, checklist, reasoning, plain_language, scenario, general_question, chitchat, unknown):"""


# =============================================================================
# Slot Extraction Prompts
# =============================================================================

SLOT_EXTRACTION_SYSTEM = "정보 추출 AI입니다. JSON만 응답하세요."


def build_slot_extraction_prompt(
    conversation: str,
    current_region: str = "미수집",
    current_life_cycle: str = "미수집",
    current_age_group: str = "미수집",
    current_interest: str = "미수집"
) -> str:
    """Build prompt for slot extraction from conversation"""
    return f"""대화에서 사용자 정보를 추출하세요.

대화 내용:
{conversation}

현재 수집된 정보:
- region (지역): {current_region}
- life_cycle (생애주기): {current_life_cycle}
- age_group (연령대): {current_age_group}
- interest (관심분야): {current_interest}

추출 규칙:
1. region: 한국의 시/도 (서울, 경기, 부산, 대구, 인천, 광주, 대전, 울산, 세종, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주)
2. life_cycle: 생애주기 단계
   - "임신/출산": 임신 중, 출산 예정, 임산부, 산모, 태아 관련
   - "영유아": 육아, 아기, 신생아, 영아, 유아, 0-6세 자녀
   - "아동": 초등학생, 어린이
   - "청소년": 중고등학생
   - "청년": 20-30대, 대학생, 취준생, 사회초년생
   - "중장년": 40-50대
   - "노년": 60대 이상, 어르신, 노인, 고령자
3. age_group: 연령대 (10대, 20대, 30대, 40대, 50대, 60대 이상)
4. interest: 관심분야 (주거, 취업, 창업, 금융, 건강, 교육, 문화, 돌봄)

중요:
- 이미 수집된 정보('미수집'이 아닌 것)는 그대로 유지하세요
- 새로 파악된 정보만 추가하세요
- 정보가 없으면 빈 문자열로 두세요

JSON만 응답:
{{"region": "", "life_cycle": "", "age_group": "", "interest": ""}}"""


# =============================================================================
# General Question Prompts
# =============================================================================

GENERAL_QUESTION_SYSTEM = "복지 정책 상담사로서 친절하게 답변하세요."


def build_general_question_prompt(question: str) -> str:
    """Build prompt for general welfare questions"""
    return f"""당신은 한국 복지 정책 전문 상담사입니다.
사용자의 일반적인 복지 관련 질문에 간단히 답변해주세요.
구체적인 정책 검색이 필요하면 그렇게 안내해주세요.

사용자 질문: {question}

간결하게 2-3문장으로 답변하세요:"""
# =============================================================================
# Greeting Prompts
# =============================================================================

GREETING_SYSTEM = "친절한 복지 상담사 '베니'로서 사용자에게 개인화된 첫 인사를 건네세요."


def build_greeting_prompt(user_profile: dict) -> str:
    """Build prompt for personalized first greeting"""
    region = user_profile.get("region", "전국")
    life_stage = user_profile.get("life_stage") or user_profile.get("life_cycle", "관심있는")
    interests = ", ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
    
    context_str = f"지역: {region}, 상황: {life_stage}"
    if interests:
        context_str += f", 관심분야: {interests}"

    return f"""사용자 정보: {context_str}

위 정보를 바탕으로 사용자에게 친절하고 개인화된 첫 인사를 하세요.
- 사용자의 지역이나 상황(청년, 임신 등)을 언급하며 공감대를 형성하세요.
- 무엇을 도와드릴지 자연스럽게 물어보세요.
- 2문장 이내로 짧고 따뜻하게 작성하세요."""
