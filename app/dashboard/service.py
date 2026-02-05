"""Dashboard service - 대시보드 데이터 집계 및 맞춤 정보 조회"""

import json
from datetime import datetime, timezone
from typing import Dict, Any

from shared.db.postgres import PostgresClient
from shared.services.qdrant_service import QdrantService
from app.dashboard.schemas import DashboardSummary, RecommendedPolicy


class DashboardService:
    """Aggregates data for the dashboard view"""

    def __init__(self, qdrant_service: QdrantService = None):
        self.postgres = PostgresClient()
        self.qdrant = qdrant_service

    def get_dashboard_summary(self, user_id: int) -> Dict[str, Any]:
        """사용자별 대시보드 요약 데이터 조회"""
        
        # 1. 프로필 완성도 계산
        prefs = self.postgres.execute_query(
            "SELECT region, life_cycle, interests FROM user_preferences WHERE user_id = %s",
            (user_id,)
        )
        score = 0
        if prefs:
            p = prefs[0]
            if p.get("region"): score += 30
            if p.get("life_cycle"): score += 30
            if p.get("interests") and len(p["interests"]) > 0: score += 40
            
        # 2. 활동량 및 최근 조회 조회
        views = self.postgres.execute_query(
            "SELECT COUNT(*) as count FROM policy_views WHERE user_id = %s",
            (user_id,)
        )
        
        # 3. 매칭 현황 (간단히 조회 이력 기반 또는 저장된 매칭 수)
        # 실제로는 Qdrant에서 실시간으로 불러오는 것이 좋으나, 우선은 Mocking 처리하거나
        # views 기반으로 응답
        
        return {
            "total_matches": 12, # Mock
            "new_matches": 2,    # Mock
            "profile_completion_score": score,
            "next_deadline": "2026-03-15", # Mock
            "recent_activities_count": views[0]["count"] if views else 0
        }

    def get_personalized_recommendations(self, user_id: int) -> Dict[str, Any]:
        """사용자 프로필 기반 맞춤 정책 리스트 조회 (UI 카드용)"""
        # 1. 사용자 프로필 가져오기
        prefs = self.postgres.execute_query(
            "SELECT region, life_cycle, interests FROM user_preferences WHERE user_id = %s",
            (user_id,)
        )
        
        if not prefs or not self.qdrant:
            return {"recommendations": [], "total_count": 0}
            
        p = prefs[0]
        # Qdrant 검색 (임시 쿼리)
        # 실제 구현에서는 챗봇 엔진의 검색 로직을 재사용해야 함
        query = f"{p.get('region', '')} {p.get('life_cycle', '')} 복지 혜택"
        
        # Qdrant 하이브리드 검색 실행 (상세 필터 생략)
        results = self.qdrant.search(query=query, limit=5)
        
        recommendations = []
        for r in results:
            recommendations.append(RecommendedPolicy(
                id=r.get("policy_id", "unknown"),
                title=r.get("title", "제목 없음"),
                category="welfare", # 임시
                region=r.get("ctpv_nm", "전국"),
                match_score=float(r.get("score", 0.0)),
                deadline=None
            ))
            
        return {
            "recommendations": recommendations,
            "total_count": len(recommendations)
        }
