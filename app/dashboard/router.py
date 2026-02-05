"""Dashboard router - 사용자별 대역 기반 요약 및 추천 API"""

from fastapi import APIRouter, Depends, Request

from app.auth import get_current_user
from app.dashboard.schemas import DashboardSummary, PersonalizedWelfareResponse
from app.dashboard.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(current_user: dict = Depends(get_current_user)):
    """
    사용자 대시보드 요약 정보 조회
    
    - 프로필 완성도, 매칭 정책 수, 최근 활동 등 집계 데이터 반환
    """
    service = DashboardService()
    summary = service.get_dashboard_summary(current_user["id"])
    return summary


@router.get("/personalized", response_model=PersonalizedWelfareResponse)
async def get_personalized(request: Request, current_user: dict = Depends(get_current_user)):
    """
    맞춤형 정책 추천 리스트 조회 (UI 카드용)
    
    - 사용자의 관심사 및 프로필 기반 시맨틱 검색 결과 반환
    """
    qdrant_service = getattr(request.app.state, "qdrant_service", None)
    service = DashboardService(qdrant_service=qdrant_service)
    
    recommendations = service.get_personalized_recommendations(current_user["id"])
    return recommendations
