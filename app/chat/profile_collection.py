"""Profile Collection Service - 가입 후 대화형 프로필 수집"""

import json
import re
from typing import Optional

from shared.db.postgres import PostgresClient

# 연령대 옵션
AGE_GROUPS = ["10대", "20대", "30대", "40대", "50대", "60대 이상"]

# 성별 옵션
GENDERS = ["남성", "여성", "기타", "미공개"]

# 지역 옵션
REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"
]

# 관심 정책 카테고리
INTEREST_CATEGORIES = [
    "임신/출산", "육아/보육", "청년", "중장년", "노년/어르신",
    "취업/창업", "주거/주택", "교육/장학", "건강/의료", "금융/대출",
    "문화/여가", "생활지원", "장애인", "다문화/한부모"
]

# 프로필 수집 단계
PROFILE_STEPS = [
    "start",          # 시작
    "ask_age_group",  # 연령대
    "ask_gender",     # 성별
    "ask_region",     # 지역
    "ask_interests",  # 관심 분야
    "complete"        # 완료
]

# 단계별 프롬프트
PROFILE_PROMPTS = {
    "start": "맞춤 정책 추천을 위해 몇 가지 질문을 드릴게요! 😊\n\n먼저, 연령대를 알려주세요.\n\n" + "\n".join([f"{i+1}. {age}" for i, age in enumerate(AGE_GROUPS)]) + "\n\n번호나 연령대를 입력해주세요.",
    "ask_age_group": "연령대를 선택해주세요.\n\n" + "\n".join([f"{i+1}. {age}" for i, age in enumerate(AGE_GROUPS)]),
    "ask_gender": "성별을 알려주세요.\n\n" + "\n".join([f"{i+1}. {g}" for i, g in enumerate(GENDERS)]) + "\n\n(건너뛰기 가능)",
    "ask_region": "거주 지역을 알려주세요.\n\n" + ", ".join(REGIONS) + "\n\n지역명을 입력해주세요. (예: 서울, 경기)",
    "ask_interests": "관심 있는 정책 분야를 선택해주세요! (복수 선택 가능)\n\n" + "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(INTEREST_CATEGORIES)]) + "\n\n번호를 쉼표로 구분해서 입력해주세요. (예: 1,3,5)\n건너뛰시려면 '건너뛰기'를 입력하세요.",
    "complete": "프로필 설정이 완료되었습니다! 🎉\n\n{nickname}님의 프로필:\n• 연령대: {age_group}\n• 성별: {gender}\n• 지역: {region}\n• 관심분야: {interests}\n\n이제 맞춤 복지 정책을 추천받으실 수 있어요!\n무엇이 궁금하신가요?"
}


def _parse_age_group(message: str) -> Optional[str]:
    """연령대 파싱"""
    message = message.strip()
    if message.isdigit():
        idx = int(message) - 1
        if 0 <= idx < len(AGE_GROUPS):
            return AGE_GROUPS[idx]
    for age in AGE_GROUPS:
        if age in message or message in age:
            return age
    return None


def _parse_gender(message: str) -> Optional[str]:
    """성별 파싱"""
    message = message.strip()
    if message.isdigit():
        idx = int(message) - 1
        if 0 <= idx < len(GENDERS):
            return GENDERS[idx]
    for gender in GENDERS:
        if gender in message or message in gender:
            return gender
    return None


def _parse_region(message: str) -> Optional[str]:
    """지역 파싱"""
    message = message.strip()
    for region in REGIONS:
        if region in message or message in region:
            return region
    return None


def _parse_interests(message: str) -> list:
    """관심 분야 파싱 (복수 선택)"""
    message = message.strip()
    interests = []

    if re.match(r'^[\d,\s]+$', message):
        numbers = re.findall(r'\d+', message)
        for num in numbers:
            idx = int(num) - 1
            if 0 <= idx < len(INTEREST_CATEGORIES):
                interests.append(INTEREST_CATEGORIES[idx])
    else:
        for cat in INTEREST_CATEGORIES:
            if cat in message:
                interests.append(cat)

    return interests


def get_user_profile_status(user_id: int) -> dict:
    """사용자 프로필 상태 조회"""
    postgres = PostgresClient()

    result = postgres.execute_query(
        """
        SELECT region, age_group, gender, interest_themes
        FROM user_preferences
        WHERE user_id = %s
        """,
        (user_id,)
    )

    if not result:
        return {
            "has_profile": False,
            "missing_fields": ["age_group", "gender", "region", "interests"]
        }

    prefs = result[0]
    missing = []

    if not prefs.get("age_group"):
        missing.append("age_group")
    if not prefs.get("gender"):
        missing.append("gender")
    if not prefs.get("region"):
        missing.append("region")
    if not prefs.get("interest_themes") or prefs["interest_themes"] == []:
        missing.append("interests")

    return {
        "has_profile": len(missing) == 0,
        "missing_fields": missing,
        "current_profile": {
            "age_group": prefs.get("age_group"),
            "gender": prefs.get("gender"),
            "region": prefs.get("region"),
            "interests": prefs.get("interest_themes") or []
        }
    }


def get_next_profile_step(user_id: int) -> str:
    """다음 프로필 수집 단계 결정"""
    status = get_user_profile_status(user_id)

    if status["has_profile"]:
        return "complete"

    missing = status["missing_fields"]

    if "age_group" in missing:
        return "ask_age_group"
    elif "gender" in missing:
        return "ask_gender"
    elif "region" in missing:
        return "ask_region"
    elif "interests" in missing:
        return "ask_interests"

    return "complete"


def start_profile_collection(user_id: int) -> dict:
    """프로필 수집 시작"""
    next_step = get_next_profile_step(user_id)

    if next_step == "complete":
        status = get_user_profile_status(user_id)
        profile = status["current_profile"]

        # 사용자 닉네임 가져오기
        postgres = PostgresClient()
        user = postgres.execute_query(
            "SELECT name FROM users WHERE id = %s",
            (user_id,)
        )
        nickname = user[0]["name"] if user else "회원"

        return {
            "response": f"이미 프로필이 완성되어 있어요! 😊\n\n{nickname}님의 프로필:\n• 연령대: {profile['age_group']}\n• 성별: {profile['gender']}\n• 지역: {profile['region']}\n• 관심분야: {', '.join(profile['interests']) if profile['interests'] else '없음'}",
            "step": "complete",
            "is_complete": True,
            "profile": profile
        }

    return {
        "response": PROFILE_PROMPTS["start"],
        "step": "ask_age_group",
        "is_complete": False,
        "profile": {}
    }


def process_profile_message(user_id: int, message: str, current_step: str) -> dict:
    """
    프로필 수집 메시지 처리

    Returns:
        dict with: response, step, is_complete, profile
    """
    postgres = PostgresClient()
    message = message.strip()

    # 건너뛰기 처리
    skip_words = ["건너뛰기", "스킵", "skip", "패스", "나중에"]
    is_skip = message.lower() in skip_words

    response = ""
    next_step = current_step
    is_complete = False

    # 현재 프로필 조회
    status = get_user_profile_status(user_id)
    profile = status["current_profile"]

    if current_step == "ask_age_group":
        age_group = _parse_age_group(message) if not is_skip else None

        if age_group:
            profile["age_group"] = age_group
            postgres.execute_write(
                "UPDATE user_preferences SET age_group = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                (age_group, user_id)
            )
            next_step = "ask_gender"
            response = PROFILE_PROMPTS["ask_gender"]
        elif is_skip:
            next_step = "ask_gender"
            response = PROFILE_PROMPTS["ask_gender"]
        else:
            response = "연령대를 다시 선택해주세요.\n\n" + "\n".join([f"{i+1}. {age}" for i, age in enumerate(AGE_GROUPS)])

    elif current_step == "ask_gender":
        gender = _parse_gender(message) if not is_skip else None

        if gender:
            profile["gender"] = gender
            postgres.execute_write(
                "UPDATE user_preferences SET gender = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                (gender, user_id)
            )
            next_step = "ask_region"
            response = PROFILE_PROMPTS["ask_region"]
        elif is_skip:
            next_step = "ask_region"
            response = PROFILE_PROMPTS["ask_region"]
        else:
            response = "성별을 다시 선택해주세요.\n\n" + "\n".join([f"{i+1}. {g}" for i, g in enumerate(GENDERS)])

    elif current_step == "ask_region":
        region = _parse_region(message) if not is_skip else None

        if region:
            profile["region"] = region
            postgres.execute_write(
                "UPDATE user_preferences SET region = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                (region, user_id)
            )
            next_step = "ask_interests"
            response = PROFILE_PROMPTS["ask_interests"]
        elif is_skip:
            next_step = "ask_interests"
            response = PROFILE_PROMPTS["ask_interests"]
        else:
            response = f"지역을 다시 입력해주세요.\n\n{', '.join(REGIONS)}"

    elif current_step == "ask_interests":
        interests = _parse_interests(message) if not is_skip else []

        profile["interests"] = interests
        postgres.execute_write(
            "UPDATE user_preferences SET interest_themes = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
            (json.dumps(interests), user_id)
        )

        # 완료
        is_complete = True
        next_step = "complete"

        # 사용자 닉네임 가져오기
        user = postgres.execute_query(
            "SELECT name FROM users WHERE id = %s",
            (user_id,)
        )
        nickname = user[0]["name"] if user else "회원"

        # 최종 프로필 조회
        final_status = get_user_profile_status(user_id)
        profile = final_status["current_profile"]

        response = PROFILE_PROMPTS["complete"].format(
            nickname=nickname,
            age_group=profile.get("age_group") or "미지정",
            gender=profile.get("gender") or "미지정",
            region=profile.get("region") or "미지정",
            interests=", ".join(profile.get("interests", [])) if profile.get("interests") else "없음"
        )

    return {
        "response": response,
        "step": next_step,
        "is_complete": is_complete,
        "profile": profile
    }


def update_single_profile_field(user_id: int, field: str, value: str) -> dict:
    """단일 프로필 필드 업데이트"""
    postgres = PostgresClient()

    valid_fields = {
        "age_group": ("age_group", _parse_age_group),
        "gender": ("gender", _parse_gender),
        "region": ("region", _parse_region),
    }

    if field not in valid_fields:
        return {"success": False, "error": f"잘못된 필드입니다: {field}"}

    db_field, parser = valid_fields[field]
    parsed_value = parser(value)

    if not parsed_value:
        return {"success": False, "error": f"잘못된 값입니다: {value}"}

    postgres.execute_write(
        f"UPDATE user_preferences SET {db_field} = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
        (parsed_value, user_id)
    )

    return {"success": True, "field": field, "value": parsed_value}


def update_interests(user_id: int, interests: list) -> dict:
    """관심 분야 업데이트"""
    postgres = PostgresClient()

    # 유효한 카테고리만 필터링
    valid_interests = [i for i in interests if i in INTEREST_CATEGORIES]

    postgres.execute_write(
        "UPDATE user_preferences SET interest_themes = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
        (json.dumps(valid_interests), user_id)
    )

    return {"success": True, "interests": valid_interests}
