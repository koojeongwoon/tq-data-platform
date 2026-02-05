"""Conversation Orchestration Service

대화 오케스트레이션: 채팅방, 메시지 이력, 사용자 관심사 관리
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional

from shared.db.postgres import PostgresClient


# =============================================================================
# Conversations (채팅방)
# =============================================================================

def create_conversation(user_id: int, title: str = None) -> dict:
    """새 대화방 생성"""
    postgres = PostgresClient()
    conversation_id = str(uuid.uuid4())

    postgres.execute_write(
        """
        INSERT INTO conversations (conversation_id, user_id, title)
        VALUES (%s, %s, %s)
        """,
        (conversation_id, user_id, title)
    )

    return {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "title": title,
        "created_at": datetime.utcnow().isoformat()
    }


def get_conversation(conversation_id: str, user_id: int) -> Optional[dict]:
    """대화방 조회 (소유권 검증)"""
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        SELECT conversation_id, user_id, title, summary, current_intent,
               collected_info, agent_data, ready_to_search, is_archived, is_pinned,
               created_at, updated_at, last_message_at
        FROM conversations
        WHERE conversation_id = %s AND user_id = %s
        """,
        (conversation_id, user_id)
    )

    if not result:
        return None

    row = result[0]
    return {
        "conversation_id": row["conversation_id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "summary": row["summary"],
        "current_intent": row["current_intent"],
        "collected_info": row["collected_info"] or {},
        "agent_data": row["agent_data"] or {},
        "ready_to_search": row["ready_to_search"],
        "is_archived": row["is_archived"],
        "is_pinned": row["is_pinned"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
    }


def list_conversations(
    user_id: int,
    include_archived: bool = False,
    limit: int = 20,
    offset: int = 0
) -> List[dict]:
    """사용자의 대화방 목록 조회"""
    postgres = PostgresClient()

    if include_archived:
        where_clause = "user_id = %s"
        params = (user_id, limit, offset)
    else:
        where_clause = "user_id = %s AND is_archived = FALSE"
        params = (user_id, limit, offset)

    result = postgres.execute_query(
        f"""
        SELECT conversation_id, title, summary, current_intent,
               is_archived, is_pinned, created_at, last_message_at,
               (SELECT COUNT(*) FROM messages WHERE messages.conversation_id = conversations.conversation_id) as message_count
        FROM conversations
        WHERE {where_clause}
        ORDER BY is_pinned DESC, last_message_at DESC
        LIMIT %s OFFSET %s
        """,
        params
    )

    return [
        {
            "conversation_id": row["conversation_id"],
            "title": row["title"],
            "summary": row["summary"],
            "current_intent": row["current_intent"],
            "is_archived": row["is_archived"],
            "is_pinned": row["is_pinned"],
            "message_count": row["message_count"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
        }
        for row in (result or [])
    ]


def update_conversation(
    conversation_id: str,
    user_id: int,
    title: str = None,
    summary: str = None,
    current_intent: str = None,
    collected_info: dict = None,
    agent_data: dict = None,
    ready_to_search: bool = None,
    is_archived: bool = None,
    is_pinned: bool = None
) -> bool:
    """대화방 업데이트"""
    postgres = PostgresClient()

    updates = []
    params = []

    if title is not None:
        updates.append("title = %s")
        params.append(title)
    if summary is not None:
        updates.append("summary = %s")
        params.append(summary)
    if current_intent is not None:
        updates.append("current_intent = %s")
        params.append(current_intent)
    if collected_info is not None:
        updates.append("collected_info = %s")
        params.append(json.dumps(collected_info))
    if agent_data is not None:
        updates.append("agent_data = %s")
        params.append(json.dumps(agent_data))
    if ready_to_search is not None:
        updates.append("ready_to_search = %s")
        params.append(ready_to_search)
    if is_archived is not None:
        updates.append("is_archived = %s")
        params.append(is_archived)
    if is_pinned is not None:
        updates.append("is_pinned = %s")
        params.append(is_pinned)

    if not updates:
        return True

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([conversation_id, user_id])

    return postgres.execute_write(
        f"""
        UPDATE conversations
        SET {', '.join(updates)}
        WHERE conversation_id = %s AND user_id = %s
        """,
        tuple(params)
    )


def delete_conversation(conversation_id: str, user_id: int) -> bool:
    """대화방 삭제"""
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        DELETE FROM conversations
        WHERE conversation_id = %s AND user_id = %s
        RETURNING id
        """,
        (conversation_id, user_id)
    )

    return bool(result)


def get_or_create_conversation(conversation_id: Optional[str], user_id: int) -> tuple[str, Optional[dict]]:
    """대화방 가져오기 또는 생성"""
    if conversation_id:
        conv = get_conversation(conversation_id, user_id)
        if conv:
            return conversation_id, conv

    # 새 대화방 생성
    new_conv = create_conversation(user_id)
    return new_conv["conversation_id"], None


# =============================================================================
# Messages (메시지 이력)
# =============================================================================

def add_message(
    conversation_id: str,
    role: str,
    content: str,
    intent: str = None,
    extracted_info: dict = None,
    sources: list = None,
    model: str = None
) -> dict:
    """메시지 추가"""
    postgres = PostgresClient()
    message_id = str(uuid.uuid4())

    postgres.execute_write(
        """
        INSERT INTO messages (message_id, conversation_id, role, content, intent, extracted_info, sources, model)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            message_id,
            conversation_id,
            role,
            content,
            intent,
            json.dumps(extracted_info or {}),
            json.dumps(sources or []),
            model
        )
    )

    # 대화방의 last_message_at 업데이트
    postgres.execute_write(
        """
        UPDATE conversations
        SET last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE conversation_id = %s
        """,
        (conversation_id,)
    )

    return {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": datetime.utcnow().isoformat()
    }


def get_messages(
    conversation_id: str,
    limit: int = 50,
    before_id: str = None
) -> List[dict]:
    """대화방의 메시지 목록 조회"""
    postgres = PostgresClient()

    if before_id:
        result = postgres.execute_query(
            """
            SELECT message_id, role, content, intent, extracted_info, sources, model, feedback, created_at
            FROM messages
            WHERE conversation_id = %s AND id < (SELECT id FROM messages WHERE message_id = %s)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (conversation_id, before_id, limit)
        )
    else:
        result = postgres.execute_query(
            """
            SELECT message_id, role, content, intent, extracted_info, sources, model, feedback, created_at
            FROM messages
            WHERE conversation_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (conversation_id, limit)
        )

    messages = [
        {
            "message_id": row["message_id"],
            "role": row["role"],
            "content": row["content"],
            "intent": row["intent"],
            "extracted_info": row["extracted_info"] or {},
            "sources": row["sources"] or [],
            "model": row["model"],
            "feedback": row["feedback"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in (result or [])
    ]

    # 시간순으로 정렬 (오래된 것부터)
    return list(reversed(messages))


def get_recent_context(conversation_id: str, limit: int = 10) -> List[dict]:
    """LLM 컨텍스트용 최근 메시지 조회"""
    messages = get_messages(conversation_id, limit=limit)
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def add_message_feedback(message_id: str, feedback: str, comment: str = None) -> bool:
    """메시지 피드백 추가"""
    postgres = PostgresClient()

    return postgres.execute_write(
        """
        UPDATE messages
        SET feedback = %s, feedback_comment = %s
        WHERE message_id = %s
        """,
        (feedback, comment, message_id)
    )


# =============================================================================
# User Preferences (사용자 관심사/장기 기억)
# =============================================================================

def get_user_preferences(user_id: int) -> Optional[dict]:
    """사용자 선호도 조회"""
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        SELECT user_id, region, region_detail, life_stage, household_type,
               interest_themes, searched_keywords, viewed_policies,
               preferred_time, interaction_count, last_topics,
               notification_enabled, language, created_at, updated_at
        FROM user_preferences
        WHERE user_id = %s
        """,
        (user_id,)
    )

    if not result:
        return None

    row = result[0]
    return {
        "user_id": row["user_id"],
        "region": row["region"],
        "region_detail": row["region_detail"],
        "life_stage": row["life_stage"],
        "household_type": row["household_type"],
        "interest_themes": row["interest_themes"] or [],
        "searched_keywords": row["searched_keywords"] or [],
        "viewed_policies": row["viewed_policies"] or [],
        "preferred_time": row["preferred_time"],
        "interaction_count": row["interaction_count"],
        "last_topics": row["last_topics"] or [],
        "notification_enabled": row["notification_enabled"],
        "language": row["language"],
    }


def get_or_create_preferences(user_id: int) -> dict:
    """사용자 선호도 가져오기 또는 생성"""
    prefs = get_user_preferences(user_id)
    if prefs:
        return prefs

    postgres = PostgresClient()
    postgres.execute_write(
        """
        INSERT INTO user_preferences (user_id)
        VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,)
    )

    return get_user_preferences(user_id) or {
        "user_id": user_id,
        "region": None,
        "region_detail": None,
        "life_stage": None,
        "household_type": None,
        "interest_themes": [],
        "searched_keywords": [],
        "viewed_policies": [],
        "interaction_count": 0,
        "last_topics": [],
    }


def update_user_preferences(
    user_id: int,
    region: str = None,
    region_detail: str = None,
    life_stage: str = None,
    household_type: str = None,
    add_interest_theme: str = None,
    add_searched_keyword: str = None,
    add_viewed_policy: str = None,
    add_topic: str = None
) -> bool:
    """사용자 선호도 업데이트"""
    postgres = PostgresClient()

    # 먼저 레코드 존재 확인/생성
    get_or_create_preferences(user_id)

    updates = ["updated_at = CURRENT_TIMESTAMP", "interaction_count = interaction_count + 1"]
    params = []

    if region is not None:
        updates.append("region = %s")
        params.append(region)
    if region_detail is not None:
        updates.append("region_detail = %s")
        params.append(region_detail)
    if life_stage is not None:
        updates.append("life_stage = %s")
        params.append(life_stage)
    if household_type is not None:
        updates.append("household_type = %s")
        params.append(household_type)

    # JSONB 배열에 추가 (중복 제거, 최근 20개만 유지)
    if add_interest_theme:
        updates.append("""
            interest_themes = (
                SELECT jsonb_agg(DISTINCT elem)
                FROM (
                    SELECT elem FROM jsonb_array_elements(
                        COALESCE(interest_themes, '[]'::jsonb) || %s::jsonb
                    ) elem
                    LIMIT 20
                ) sub
            )
        """)
        params.append(json.dumps([add_interest_theme]))

    if add_searched_keyword:
        updates.append("""
            searched_keywords = (
                SELECT jsonb_agg(elem)
                FROM (
                    SELECT elem FROM jsonb_array_elements(
                        %s::jsonb || COALESCE(searched_keywords, '[]'::jsonb)
                    ) elem
                    LIMIT 50
                ) sub
            )
        """)
        params.append(json.dumps([add_searched_keyword]))

    if add_viewed_policy:
        updates.append("""
            viewed_policies = (
                SELECT jsonb_agg(elem)
                FROM (
                    SELECT elem FROM jsonb_array_elements(
                        %s::jsonb || COALESCE(viewed_policies, '[]'::jsonb)
                    ) elem
                    LIMIT 100
                ) sub
            )
        """)
        params.append(json.dumps([add_viewed_policy]))

    if add_topic:
        updates.append("""
            last_topics = (
                SELECT jsonb_agg(elem)
                FROM (
                    SELECT elem FROM jsonb_array_elements(
                        %s::jsonb || COALESCE(last_topics, '[]'::jsonb)
                    ) elem
                    LIMIT 10
                ) sub
            )
        """)
        params.append(json.dumps([add_topic]))

    params.append(user_id)

    return postgres.execute_write(
        f"""
        UPDATE user_preferences
        SET {', '.join(updates)}
        WHERE user_id = %s
        """,
        tuple(params)
    )


# =============================================================================
# Policy Views (정책 조회 이력)
# =============================================================================

def record_policy_view(
    user_id: int,
    policy_id: str,
    conversation_id: str = None,
    search_query: str = None,
    relevance_score: float = None
) -> bool:
    """정책 조회 기록"""
    postgres = PostgresClient()

    return postgres.execute_write(
        """
        INSERT INTO policy_views (user_id, policy_id, conversation_id, search_query, relevance_score)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, policy_id, conversation_id, search_query, relevance_score)
    )


def record_policy_click(user_id: int, policy_id: str) -> bool:
    """정책 클릭 기록 (가장 최근 조회 레코드 업데이트)"""
    postgres = PostgresClient()

    return postgres.execute_write(
        """
        UPDATE policy_views
        SET clicked = TRUE
        WHERE id = (
            SELECT id FROM policy_views
            WHERE user_id = %s AND policy_id = %s
            ORDER BY viewed_at DESC
            LIMIT 1
        )
        """,
        (user_id, policy_id)
    )


def toggle_policy_bookmark(user_id: int, policy_id: str) -> bool:
    """정책 북마크 토글"""
    postgres = PostgresClient()

    # 기존 조회 기록이 있으면 업데이트, 없으면 새로 생성
    result = postgres.execute_query(
        """
        SELECT id, bookmarked FROM policy_views
        WHERE user_id = %s AND policy_id = %s
        ORDER BY viewed_at DESC
        LIMIT 1
        """,
        (user_id, policy_id)
    )

    if result:
        new_value = not result[0]["bookmarked"]
        postgres.execute_write(
            "UPDATE policy_views SET bookmarked = %s WHERE id = %s",
            (new_value, result[0]["id"])
        )
        return new_value
    else:
        postgres.execute_write(
            """
            INSERT INTO policy_views (user_id, policy_id, bookmarked)
            VALUES (%s, %s, TRUE)
            """,
            (user_id, policy_id)
        )
        return True


def get_user_bookmarks(user_id: int, limit: int = 50) -> List[dict]:
    """사용자의 북마크된 정책 목록"""
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        SELECT DISTINCT ON (policy_id) policy_id, search_query, viewed_at
        FROM policy_views
        WHERE user_id = %s AND bookmarked = TRUE
        ORDER BY policy_id, viewed_at DESC
        LIMIT %s
        """,
        (user_id, limit)
    )

    return [
        {
            "policy_id": row["policy_id"],
            "search_query": row["search_query"],
            "viewed_at": row["viewed_at"].isoformat() if row["viewed_at"] else None,
        }
        for row in (result or [])
    ]


def get_frequently_viewed_policies(user_id: int, limit: int = 10) -> List[dict]:
    """사용자가 자주 조회한 정책"""
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        SELECT policy_id, COUNT(*) as view_count, MAX(viewed_at) as last_viewed
        FROM policy_views
        WHERE user_id = %s
        GROUP BY policy_id
        ORDER BY view_count DESC, last_viewed DESC
        LIMIT %s
        """,
        (user_id, limit)
    )

    return [
        {
            "policy_id": row["policy_id"],
            "view_count": row["view_count"],
            "last_viewed": row["last_viewed"].isoformat() if row["last_viewed"] else None,
        }
        for row in (result or [])
    ]


# =============================================================================
# Utility Functions
# =============================================================================

def generate_conversation_title(first_message: str) -> str:
    """첫 메시지 기반 대화방 제목 자동 생성"""
    # 간단하게 첫 30자 사용 (나중에 LLM으로 개선 가능)
    title = first_message[:30].strip()
    if len(first_message) > 30:
        title += "..."
    return title


def get_user_context_for_llm(user_id: int) -> dict:
    """LLM에 전달할 사용자 컨텍스트"""
    prefs = get_or_create_preferences(user_id)

    context = {}

    if prefs.get("region"):
        context["region"] = prefs["region"]
        if prefs.get("region_detail"):
            context["region"] += f" {prefs['region_detail']}"

    if prefs.get("life_stage"):
        context["life_stage"] = prefs["life_stage"]

    if prefs.get("household_type"):
        context["household_type"] = prefs["household_type"]

    if prefs.get("interest_themes"):
        context["interests"] = prefs["interest_themes"][:5]

    if prefs.get("last_topics"):
        context["recent_topics"] = prefs["last_topics"][:3]

    return context
