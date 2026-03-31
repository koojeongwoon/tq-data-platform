"""Dashboard service - 대시보드 데이터 집계 및 맞춤 정보 조회"""

import json
from datetime import datetime, timezone
from typing import Dict, Any

from shared.db.postgres import PostgresClient
from shared.services.qdrant_service import QdrantService
from app.chat.service import RAGService
from app.dashboard.schemas import DashboardSummary, RecommendedPolicy


class DashboardService:
    """Aggregates data for the dashboard view"""

    def __init__(self, qdrant_service: QdrantService = None, rag_service: RAGService = None):
        self.postgres = PostgresClient()
        self.qdrant = qdrant_service
        self.rag = rag_service

    def get_dashboard_summary(self, user_id: int) -> Dict[str, Any]:
        """사용자별 대시보드 요약 데이터 조회"""
        from shared.utils import calculate_dday_string
        
        # 1. 프로필 정보 및 완성도 계산
        prefs = self.postgres.execute_one(
            "SELECT region, life_stage as life_cycle, interest_themes as interests FROM user_preferences WHERE user_id = %s",
            (user_id,)
        )
        
        score = 0
        total_matches = 0
        if prefs:
            if prefs.get("region"): score += 30
            if prefs.get("life_cycle"): score += 30
            if prefs.get("interests") and len(prefs["interests"]) > 0: score += 40
            
            # 2. 실시간 매칭 수 (Qdrant)
            if self.qdrant:
                total_matches = self.qdrant.count_matches(
                    province=prefs.get("region"),
                    life_cycle=prefs.get("life_cycle")
                )
            
        # 3. 최근 활동량 (조회 이력)
        views = self.postgres.execute_one(
            "SELECT COUNT(*) as count FROM policy_views WHERE user_id = %s",
            (user_id,)
        )
        
        # 4. 신규 정책 (최근 7일 이내 생성된 정책 중 사용자 관심사에 맞는 것)
        # 여기서는 단순 카운트만 수행
        new_matches_query = """
            SELECT COUNT(*) as count 
            FROM welfare_policies 
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """
        if prefs and prefs.get("region"):
            new_matches_query += f" AND (ctpv_nm = '{prefs['region']}' OR source_type = 'central')"
            
        new_matches = self.postgres.execute_one(new_matches_query)
        
        # 5. 가장 가까운 마감일
        deadline_query = """
            SELECT MIN(end_date) as next_deadline 
            FROM welfare_policies 
            WHERE end_date >= CURRENT_DATE
        """
        if prefs and prefs.get("region"):
            deadline_query += f" AND (ctpv_nm = '{prefs['region']}' OR source_type = 'central')"
            
        next_deadline_row = self.postgres.execute_one(deadline_query)
        next_deadline = next_deadline_row["next_deadline"] if next_deadline_row else None
        
        return {
            "total_matches": total_matches,
            "new_matches": new_matches["count"] if new_matches else 0,
            "profile_completion_score": score,
            "next_deadline": calculate_dday_string(next_deadline) if next_deadline else "상시",
            "recent_activities_count": views["count"] if views else 0
        }

    def get_personalized_recommendations(self, user_id: int) -> Dict[str, Any]:
        """사용자 프로필 기반 맞춤 정책 리스트 조회 (UI 카드용)"""
        from shared.utils import map_category, format_region, calculate_dday_string
        
        # 1. 사용자 프로필 가져오기
        prefs = self.postgres.execute_one(
            "SELECT region, life_stage as life_cycle, interest_themes as interests FROM user_preferences WHERE user_id = %s",
            (user_id,)
        )
        
        if not prefs or (not self.qdrant and not self.rag):
            return {"recommendations": [], "total_count": 0}
            
        # 검색 쿼리 구성
        interests_str = " ".join(prefs.get("interests", []))
        query = f"{prefs.get('life_cycle', '')} {interests_str} 복지 정책"
        
        # RAGService가 있으면 Reranking 사용, 없으면 Qdrant 직접 사용
        if self.rag:
            results = self.rag.retrieve_context(
                query=query,
                filters={
                    "province": prefs.get("region"),
                    "life_cycle": prefs.get("life_cycle")
                },
                top_k=5
            )
        else:
            # Fallback to direct Qdrant search if RAGService not provided
            results = self.qdrant.hybrid_search(
                query=query, 
                limit=5,
                province=prefs.get("region"),
                life_cycle=prefs.get("life_cycle")
            )
        
        recommendations = []
        for r in results:
            # 임계치 적용 (0.5) - 너무 낮은 점수는 제외
            score = float(r.get("score", 0.0))
            if score < 0.5:
                continue
                
            # PostgreSQL에서 추가 마감일 정보 등 보완
            policy_id = r.get("policy_id")
            full_policy = self.postgres.get_policy_by_id(policy_id) if policy_id else None
            
            recommendations.append(RecommendedPolicy(
                id=policy_id or "unknown",
                title=r.get("title", "제목 없음"),
                category=map_category(r.get("metadata", {}).get("interest_themes", r.get("interest_themes", []))),
                region=format_region(r.get("metadata", {}).get("province")),
                match_score=score,
                deadline=calculate_dday_string(full_policy.get("end_date")) if full_policy else "상시"
            ))
            
        return {
            "recommendations": recommendations,
            "total_count": len(recommendations)
        }
