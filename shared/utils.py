"""Shared utility functions for the TQ Data Platform"""

from datetime import datetime, timezone
from typing import List, Optional, Union


def map_category(interest_themes: Union[str, List[str]]) -> str:
    """Map interest_themes to frontend category icon keys"""
    if not interest_themes:
        return "welfare"

    if isinstance(interest_themes, str):
        try:
            import json
            interest_themes = json.loads(interest_themes)
        except Exception:
            interest_themes = [interest_themes]

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


def format_region(ctpv_nm: Optional[str], source_type: str = "regional") -> str:
    """Format region for display (short names)"""
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


def calculate_dday_string(end_date: Optional[Union[datetime, str]]) -> Optional[str]:
    """Calculate D-day string (e.g., 'D-5', '오늘 마감', '상시')"""
    if not end_date:
        return "상시"

    if isinstance(end_date, str):
        try:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except Exception:
            return None

    now = datetime.now(timezone.utc)
    # Ensure end_date is timezone-aware
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    delta = (end_date.date() - now.date()).days

    if delta < 0:
        return "종료"
    if delta == 0:
        return "오늘 마감"
    return f"D-{delta}"
