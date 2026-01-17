"""Onboarding Service - 대화형 온보딩 프로필 수집 로직"""

import uuid
from typing import Optional

from shared.db.postgres import PostgresClient

# =============================================================================
# 온보딩 옵션 정의
# =============================================================================

# 지역 옵션
REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"
]

# 생애주기 옵션
LIFE_CYCLES = [
    "임신/출산", "영유아 양육", "아동/청소년", "청년", "중장년", "노년"
]

# 관심분야 옵션
INTERESTS = [
    "주거/임대", "취업/창업", "교육/장학", "건강/의료", "금융/대출",
    "문화/여가", "생활지원", "장애인", "다문화/한부모"
]

# 온보딩 단계
STEPS = ["greeting", "collect_region", "collect_life_cycle", "collect_interests", "completed"]


# =============================================================================
# 헬퍼 함수
# =============================================================================

def _generate_session_id() -> str:
    """온보딩 세션 ID 생성"""
    return f"onb_{uuid.uuid4().hex[:16]}"


def _parse_region(message: str) -> Optional[str]:
    """지역 파싱"""
    message = message.strip()
    for region in REGIONS:
        if region in message or message in region:
            return region
    return None


def _parse_life_cycle(message: str) -> Optional[str]:
    """생애주기 파싱"""
    message = message.strip()
    for lc in LIFE_CYCLES:
        if lc in message or message in lc:
            return lc
    # 간단한 매핑
    mapping = {
        "임신": "임신/출산", "출산": "임신/출산",
        "영유아": "영유아 양육", "육아": "영유아 양육", "보육": "영유아 양육",
        "아동": "아동/청소년", "청소년": "아동/청소년",
        "청년": "청년", "대학생": "청년", "취준생": "청년",
        "중장년": "중장년", "중년": "중장년",
        "노년": "노년", "어르신": "노년", "노인": "노년", "고령": "노년"
    }
    for key, value in mapping.items():
        if key in message:
            return value
    return None


def _parse_interests(message: str) -> list[str]:
    """관심분야 파싱 (복수 선택)"""
    result = []
    for interest in INTERESTS:
        if interest in message:
            result.append(interest)
    # 간단한 매핑
    mapping = {
        "주거": "주거/임대", "임대": "주거/임대", "전세": "주거/임대", "월세": "주거/임대",
        "취업": "취업/창업", "창업": "취업/창업", "일자리": "취업/창업",
        "교육": "교육/장학", "장학": "교육/장학",
        "건강": "건강/의료", "의료": "건강/의료", "병원": "건강/의료",
        "금융": "금융/대출", "대출": "금융/대출",
        "문화": "문화/여가", "여가": "문화/여가",
        "생활": "생활지원",
        "장애": "장애인",
        "다문화": "다문화/한부모", "한부모": "다문화/한부모"
    }
    for key, value in mapping.items():
        if key in message and value not in result:
            result.append(value)
    return result


# =============================================================================
# 온보딩 서비스 클래스
# =============================================================================

class OnboardingService:
    """대화형 온보딩 서비스"""

    def __init__(self):
        self.postgres = PostgresClient()

    def get_or_create_session(self, user_id: int, session_id: Optional[str] = None) -> dict:
        """세션 조회 또는 생성"""
        if session_id:
            # 기존 세션 조회
            result = self.postgres.execute_query(
                """
                SELECT id, user_id, step, region, life_cycle, interests
                FROM onboarding_sessions
                WHERE id = %s AND user_id = %s
                """,
                (session_id, user_id)
            )
            if result:
                return result[0]

        # 새 세션 생성
        new_session_id = _generate_session_id()
        self.postgres.execute_write(
            """
            INSERT INTO onboarding_sessions (id, user_id, step)
            VALUES (%s, %s, 'greeting')
            """,
            (new_session_id, user_id)
        )
        return {
            "id": new_session_id,
            "user_id": user_id,
            "step": "greeting",
            "region": None,
            "life_cycle": None,
            "interests": None
        }

    def process_message(self, user_id: int, user_name: str, message: str, session_id: Optional[str] = None) -> dict:
        """온보딩 메시지 처리"""
        session = self.get_or_create_session(user_id, session_id)
        current_step = session["step"]

        response_text = ""
        next_step = current_step
        quick_replies = []
        profile = {
            "region": session.get("region"),
            "life_cycle": session.get("life_cycle"),
            "interests": session.get("interests")
        }
        is_completed = False

        # 첫 요청 (greeting)
        if current_step == "greeting":
            response_text = f"{user_name}님, 가입을 축하드려요! 🎉\n\n맞춤 정책을 추천해드리기 위해 몇 가지 질문을 드릴게요.\n\n어느 지역에 거주하고 계신가요?"
            next_step = "collect_region"
            quick_replies = REGIONS

        # 지역 수집
        elif current_step == "collect_region":
            region = _parse_region(message)
            if region:
                profile["region"] = region
                response_text = f"{region}에 사시는군요! 👍\n\n현재 상황에 해당하는 것이 있으신가요?"
                next_step = "collect_life_cycle"
                quick_replies = LIFE_CYCLES
            else:
                response_text = "지역을 다시 선택해주세요.\n\n" + ", ".join(REGIONS)
                quick_replies = REGIONS

        # 생애주기 수집
        elif current_step == "collect_life_cycle":
            life_cycle = _parse_life_cycle(message)
            if life_cycle:
                profile["life_cycle"] = life_cycle
                response_text = f"{life_cycle} 관련 정책을 찾아드릴게요! 📋\n\n관심 있는 분야를 선택해주세요. (복수 선택 가능)"
                next_step = "collect_interests"
                quick_replies = INTERESTS
            else:
                response_text = "해당하는 상황을 선택해주세요."
                quick_replies = LIFE_CYCLES

        # 관심분야 수집
        elif current_step == "collect_interests":
            interests = _parse_interests(message)
            if interests:
                profile["interests"] = ", ".join(interests)
                response_text = f"완료됐어요! 🎊\n\n입력해주신 정보를 바탕으로 맞춤 혜택을 찾아드릴게요.\n\n• 지역: {profile['region']}\n• 생애주기: {profile['life_cycle']}\n• 관심분야: {profile['interests']}"
                next_step = "completed"
                is_completed = True
            else:
                response_text = "관심 있는 분야를 선택해주세요. (예: 주거, 취업)"
                quick_replies = INTERESTS

        # 세션 업데이트
        self.postgres.execute_write(
            """
            UPDATE onboarding_sessions
            SET step = %s, region = %s, life_cycle = %s, interests = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (next_step, profile.get("region"), profile.get("life_cycle"), profile.get("interests"), session["id"])
        )

        return {
            "response": response_text,
            "session_id": session["id"],
            "step": next_step,
            "profile": profile,
            "is_completed": is_completed,
            "quick_replies": quick_replies
        }

    def complete_onboarding(self, user_id: int, session_id: str, profile: dict) -> dict:
        """온보딩 완료 처리"""
        # 1. 세션 확인
        session = self.postgres.execute_query(
            "SELECT * FROM onboarding_sessions WHERE id = %s AND user_id = %s",
            (session_id, user_id)
        )
        if not session:
            return {"success": False, "error": "잘못된 세션 ID입니다"}

        # 2. user_preferences에 저장 (upsert)
        # 기존 테이블 컬럼명: life_stage, interest_themes (jsonb)
        import json
        interests_list = profile.get("interests", "").split(", ") if profile.get("interests") else []
        self.postgres.execute_write(
            """
            INSERT INTO user_preferences (user_id, region, life_stage, interest_themes)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                region = EXCLUDED.region,
                life_stage = EXCLUDED.life_stage,
                interest_themes = EXCLUDED.interest_themes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, profile.get("region"), profile.get("life_cycle"), json.dumps(interests_list))
        )

        # 3. 사용자의 onboarding_completed를 true로 업데이트
        self.postgres.execute_write(
            "UPDATE users SET onboarding_completed = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (user_id,)
        )

        # 4. 세션 삭제
        self.postgres.execute_write(
            "DELETE FROM onboarding_sessions WHERE id = %s",
            (session_id,)
        )

        # 5. 업데이트된 사용자 정보 조회
        user = self.postgres.execute_query(
            "SELECT id, email, name, onboarding_completed, created_at FROM users WHERE id = %s",
            (user_id,)
        )

        return {
            "success": True,
            "user": {
                "id": user[0]["id"],
                "email": user[0]["email"],
                "name": user[0]["name"],
                "onboarding_completed": user[0]["onboarding_completed"],
                "profile": profile
            }
        }

    def delete_session(self, user_id: int, session_id: str) -> bool:
        """온보딩 세션 삭제 (건너뛰기)"""
        result = self.postgres.execute_write(
            "DELETE FROM onboarding_sessions WHERE id = %s AND user_id = %s",
            (session_id, user_id)
        )
        return result > 0 if result else True
