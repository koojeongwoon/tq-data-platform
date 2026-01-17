"""Chat session management - DB-backed session storage"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from shared.db.postgres import PostgresClient

# Session expires after 24 hours of inactivity
SESSION_EXPIRE_HOURS = 24


def create_session(user_id: int) -> str:
    """Create a new chat session for user"""
    postgres = PostgresClient()
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)

    postgres.execute_write(
        """
        INSERT INTO chat_sessions (session_id, user_id, expires_at)
        VALUES (%s, %s, %s)
        """,
        (session_id, user_id, expires_at)
    )

    return session_id


def get_session(session_id: str, user_id: int) -> Optional[dict]:
    """
    Get session state from DB

    Args:
        session_id: Session ID
        user_id: User ID (for ownership verification)

    Returns:
        Session state dict or None if not found/expired/unauthorized
    """
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        SELECT session_id, user_id, user_profile, messages, intent,
               ready_to_search, fallback_count, expires_at
        FROM chat_sessions
        WHERE session_id = %s AND user_id = %s AND expires_at > CURRENT_TIMESTAMP
        """,
        (session_id, user_id)
    )

    if not result:
        return None

    row = result[0]

    return {
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "user_profile": row["user_profile"] or {},
        "messages": row["messages"] or [],
        "intent": row["intent"] or "",
        "ready_to_search": row["ready_to_search"] or False,
        "fallback_count": row["fallback_count"] or 0
    }


def update_session(session_id: str, user_id: int, state: dict) -> bool:
    """
    Update session state in DB

    Args:
        session_id: Session ID
        user_id: User ID (for ownership verification)
        state: New session state

    Returns:
        True if updated, False otherwise
    """
    postgres = PostgresClient()
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)

    return postgres.execute_write(
        """
        UPDATE chat_sessions
        SET user_profile = %s,
            messages = %s,
            intent = %s,
            ready_to_search = %s,
            fallback_count = %s,
            updated_at = CURRENT_TIMESTAMP,
            expires_at = %s
        WHERE session_id = %s AND user_id = %s
        """,
        (
            json.dumps(state.get("user_profile", {})),
            json.dumps(state.get("messages", [])),
            state.get("intent", ""),
            state.get("ready_to_search", False),
            state.get("fallback_count", 0),
            expires_at,
            session_id,
            user_id
        )
    )


def delete_session(session_id: str, user_id: int) -> bool:
    """
    Delete a session

    Args:
        session_id: Session ID
        user_id: User ID (for ownership verification)

    Returns:
        True if deleted, False otherwise
    """
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        DELETE FROM chat_sessions
        WHERE session_id = %s AND user_id = %s
        RETURNING id
        """,
        (session_id, user_id)
    )

    return bool(result)


def delete_user_sessions(user_id: int) -> int:
    """
    Delete all sessions for a user (e.g., on logout)

    Args:
        user_id: User ID

    Returns:
        Number of deleted sessions
    """
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        DELETE FROM chat_sessions
        WHERE user_id = %s
        RETURNING id
        """,
        (user_id,)
    )

    return len(result) if result else 0


def get_user_sessions(user_id: int) -> list:
    """
    Get all active sessions for a user

    Args:
        user_id: User ID

    Returns:
        List of session summaries
    """
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        SELECT session_id, intent, created_at, updated_at
        FROM chat_sessions
        WHERE user_id = %s AND expires_at > CURRENT_TIMESTAMP
        ORDER BY updated_at DESC
        """,
        (user_id,)
    )

    return result or []


def cleanup_expired_sessions() -> int:
    """
    Clean up expired sessions (batch job)

    Returns:
        Number of deleted sessions
    """
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        DELETE FROM chat_sessions
        WHERE expires_at < CURRENT_TIMESTAMP
        RETURNING id
        """
    )

    return len(result) if result else 0


def get_or_create_session(session_id: Optional[str], user_id: int) -> tuple[str, Optional[dict]]:
    """
    Get existing session or create new one

    Args:
        session_id: Optional session ID
        user_id: User ID

    Returns:
        Tuple of (session_id, session_state or None for new sessions)
    """
    if session_id:
        state = get_session(session_id, user_id)
        if state:
            return session_id, state

    # Create new session
    new_session_id = create_session(user_id)
    return new_session_id, None
