"""Onboarding Registration Service - Guest to User conversion"""

import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    store_refresh_token,
)
from shared.db.postgres import PostgresClient

# 게스트 세션 만료 시간 (24시간)
GUEST_SESSION_EXPIRE_HOURS = 24

# 회원가입 단계
ONBOARDING_STEPS = [
    "greeting",
    "ask_nickname",
    "ask_email",
    "ask_password",
    "confirm",
    "complete"
]

# 단계별 프롬프트
STEP_PROMPTS = {
    "greeting": "안녕하세요! 복지 정책 도우미입니다. 🎉\n간단한 회원가입 후 맞춤 정책을 추천받으실 수 있어요.\n\n먼저 사용하실 닉네임을 알려주세요!",
    "ask_nickname": "닉네임을 입력해주세요.",
    "ask_email": "좋아요, {nickname}님! 로그인에 사용할 이메일 주소를 알려주세요.",
    "ask_password": "비밀번호를 설정해주세요. (8자 이상, 영문+숫자 포함)",
    "confirm": "{nickname}님, 입력하신 정보를 확인해주세요:\n\n• 닉네임: {nickname}\n• 이메일: {email}\n\n'확인'을 입력하시면 가입이 완료됩니다.\n수정이 필요하시면 '수정'을 입력해주세요.",
    "complete": "🎉 가입이 완료되었습니다!\n{nickname}님, 환영합니다!\n\n맞춤 정책 추천을 위해 몇 가지 질문을 드릴게요. 지금 바로 시작할까요? (예/나중에)"
}

class GuestRegistrationService:
    """Handles guest landing and registration flow"""

    def __init__(self):
        self.postgres = PostgresClient()

    def create_guest_session(
        self,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_fingerprint: Optional[str] = None
    ) -> str:
        """새 게스트 세션 생성"""
        session_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=GUEST_SESSION_EXPIRE_HOURS)

        initial_message = {
            "role": "assistant",
            "content": STEP_PROMPTS["greeting"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.postgres.execute_write(
            """
            INSERT INTO guest_sessions (
                session_id, onboarding_step, messages,
                ip_address, user_agent, device_fingerprint, expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session_id,
                "ask_nickname",
                json.dumps([initial_message]),
                ip_address,
                user_agent,
                device_fingerprint,
                expires_at
            )
        )
        return session_id

    def process_message(self, session_id: str, message: str) -> dict:
        """Processes registration chat messages"""
        session_result = self.postgres.execute_query(
            """
            SELECT session_id, collected_nickname, collected_email, collected_password_hash,
                   onboarding_step, messages
            FROM guest_sessions
            WHERE session_id = %s AND expires_at > CURRENT_TIMESTAMP AND completed_at IS NULL
            """,
            (session_id,)
        )

        if not session_result:
            return {
                "response": "세션이 만료되었거나 찾을 수 없습니다. 다시 시작해주세요.",
                "step": "expired",
                "is_complete": False,
                "collected_info": {}
            }

        session = session_result[0]
        current_step = session["onboarding_step"]
        messages = session["messages"] or []

        # 사용자 메시지 추가
        messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # 수집된 정보
        collected_info = {
            "nickname": session["collected_nickname"],
            "email": session["collected_email"],
        }

        response = ""
        next_step = current_step
        is_complete = False
        tokens = {}

        # 단계별 처리
        if current_step == "ask_nickname":
            nickname = message.strip()
            if len(nickname) < 2:
                response = "닉네임은 2자 이상 입력해주세요."
            elif len(nickname) > 20:
                response = "닉네임은 20자 이하로 입력해주세요."
            else:
                collected_info["nickname"] = nickname
                next_step = "ask_email"
                response = STEP_PROMPTS["ask_email"].format(nickname=nickname)
                self.postgres.execute_write(
                    "UPDATE guest_sessions SET collected_nickname = %s, onboarding_step = %s WHERE session_id = %s",
                    (nickname, next_step, session_id)
                )

        elif current_step == "ask_email":
            email = message.strip().lower()
            if not self._validate_email(email):
                response = "올바른 이메일 형식이 아닙니다. 다시 입력해주세요. (예: example@email.com)"
            elif self._check_email_exists(email):
                response = "이미 가입된 이메일입니다. 다른 이메일을 입력해주세요."
            else:
                collected_info["email"] = email
                next_step = "ask_password"
                response = STEP_PROMPTS["ask_password"]
                self.postgres.execute_write(
                    "UPDATE guest_sessions SET collected_email = %s, onboarding_step = %s WHERE session_id = %s",
                    (email, next_step, session_id)
                )

        elif current_step == "ask_password":
            password = message.strip()
            is_valid, error_msg = self._validate_password(password)
            if not is_valid:
                response = error_msg
            else:
                password_hash = hash_password(password)
                next_step = "confirm"
                response = STEP_PROMPTS["confirm"].format(
                    nickname=collected_info["nickname"],
                    email=collected_info["email"]
                )
                self.postgres.execute_write(
                    "UPDATE guest_sessions SET collected_password_hash = %s, onboarding_step = %s WHERE session_id = %s",
                    (password_hash, next_step, session_id)
                )

        elif current_step == "confirm":
            if message.strip() in ["확인", "완료", "가입", "예", "네", "yes", "ok", "confirm"]:
                result = self._complete_registration(session_id, session)
                if result["success"]:
                    is_complete = True
                    next_step = "complete"
                    response = STEP_PROMPTS["complete"].format(nickname=collected_info["nickname"])
                    tokens = {
                        "access_token": result["access_token"],
                        "refresh_token": result["refresh_token"],
                        "user": result["user"]
                    }
                else:
                    response = result["error"]
            elif message.strip() in ["수정", "변경", "취소", "다시"]:
                next_step = "ask_nickname"
                response = "처음부터 다시 시작할게요. 닉네임을 입력해주세요."
                self.postgres.execute_write(
                    """UPDATE guest_sessions
                       SET collected_nickname = NULL, collected_email = NULL,
                           collected_password_hash = NULL, onboarding_step = %s
                       WHERE session_id = %s""",
                    (next_step, session_id)
                )
                collected_info = {}
            else:
                response = "'확인' 또는 '수정'을 입력해주세요."

        # 응답 메시지 추가
        messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # 메시지 업데이트
        self.postgres.execute_write(
            "UPDATE guest_sessions SET messages = %s, updated_at = CURRENT_TIMESTAMP WHERE session_id = %s",
            (json.dumps(messages), session_id)
        )

        result = {
            "response": response,
            "session_id": session_id,
            "step": next_step,
            "is_complete": is_complete,
            "collected_info": {k: v for k, v in collected_info.items() if v}
        }

        if tokens:
            result.update(tokens)

        return result

    def get_or_create_guest_session(
        self,
        session_id: Optional[str],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[str, dict]:
        """게스트 세션 조회 또는 생성"""
        if session_id:
            # session = get_guest_session(session_id) logic
            result = self.postgres.execute_query(
                "SELECT session_id, onboarding_step, collected_nickname, collected_email FROM guest_sessions WHERE session_id = %s AND expires_at > CURRENT_TIMESTAMP",
                (session_id,)
            )
            if result and result[0]:
                row = result[0]
                return session_id, {
                    "response": "",
                    "session_id": session_id,
                    "step": row["onboarding_step"],
                    "is_complete": False,
                    "collected_info": {
                        "nickname": row["collected_nickname"],
                        "email": row["collected_email"],
                    }
                }

        # 새 세션 생성
        new_session_id = self.create_guest_session(ip_address, user_agent)
        return new_session_id, {
            "response": STEP_PROMPTS["greeting"],
            "session_id": new_session_id,
            "step": "ask_nickname",
            "is_complete": False,
            "collected_info": {}
        }

    def _validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _validate_password(self, password: str) -> tuple[bool, str]:
        if len(password) < 8: return False, "비밀번호는 8자 이상이어야 합니다."
        if not re.search(r'[A-Za-z]', password): return False, "비밀번호에 영문자를 포함해주세요."
        if not re.search(r'\d', password): return False, "비밀번호에 숫자를 포함해주세요."
        return True, ""

    def _check_email_exists(self, email: str) -> bool:
        result = self.postgres.execute_query("SELECT id FROM users WHERE email = %s", (email,))
        return bool(result)

    def _complete_registration(self, session_id: str, session: dict) -> dict:
        try:
            user_result = self.postgres.execute_query(
                """
                INSERT INTO users (email, password_hash, name)
                VALUES (%s, %s, %s)
                RETURNING id, email, name, is_active, created_at
                """,
                (session["collected_email"], session["collected_password_hash"], session["collected_nickname"])
            )
            if not user_result: return {"success": False, "error": "사용자 생성 실패"}
            user = user_result[0]

            access_token = create_access_token(user["id"], user["email"])
            refresh_token = create_refresh_token(user["id"], user["email"])
            store_refresh_token(user["id"], refresh_token)

            self.postgres.execute_write(
                "UPDATE guest_sessions SET user_id = %s, completed_at = CURRENT_TIMESTAMP WHERE session_id = %s",
                (user["id"], session_id)
            )
            return {
                "success": True, "access_token": access_token, "refresh_token": refresh_token,
                "user": {
                    "id": user["id"], "email": user["email"], "name": user["name"],
                    "is_active": user["is_active"], "created_at": user["created_at"].isoformat()
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
