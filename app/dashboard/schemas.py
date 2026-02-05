"""Dashboard schemas - 대시보드 관련 Pydantic 모델"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """대시보드 요약 정보"""
    total_matches: int = Field(..., description="매칭된 전체 정책 수")
    new_matches: int = Field(..., description="최근 추가된 매칭 정책 수")
    profile_completion_score: int = Field(..., description="프로필 완성도 점수 (0-100)")
    next_deadline: Optional[str] = Field(None, description="가장 가까운 신청 마감일")
    recent_activities_count: int = Field(0, description="최근 활동 수")


class RecommendedPolicy(BaseModel):
    """대시보드 추천 정책 소형 카드 정보"""
    id: str = Field(..., description="정책 ID")
    title: str = Field(..., description="정책명")
    category: str = Field(..., description="카테고리")
    region: str = Field(..., description="지역")
    deadline: Optional[str] = Field(None, description="마감일")
    match_score: float = Field(..., description="매칭 점수")


class PersonalizedWelfareResponse(BaseModel):
    """맞춤 복지 리스트 응답"""
    recommendations: List[RecommendedPolicy] = Field(..., description="추천 정책 목록")
    total_count: int = Field(..., description="전체 검색 결과 수")
