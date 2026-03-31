"""Welfare Policy Router"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from app.auth import get_current_user, get_current_user_optional
from shared.db.postgres import PostgresClient

router = APIRouter(prefix="/welfare", tags=["Welfare"])


@router.get("/policies")
async def get_welfare_policies(
    limit: int = 100,
    offset: int = 0,
    region: str = None,
    category: str = None
):
    """
    PostgreSQL에서 복지 정책 목록 조회 (필터링 포함)

    Args:
        limit: 조회할 정책 개수 (기본: 100)
        offset: 시작 위치 (기본: 0)
        region: 지역 필터 (예: 서울)
        category: 카테고리 필터 (예: job, housing)
    """
    try:
        postgres = PostgresClient()

        conditions = []
        params = []

        if region:
            conditions.append("ctpv_nm LIKE %s")
            params.append(f"%{region}%")

        if category:
            # category_map의 역방향 검색은 복잡하므로, 관심분야 문자열 포함 여부로 필터링
            # 또는 interest_themes에서 category에 해당하는 키워드가 있는지 확인
            category_keywords = {
                "housing": ["주거", "임대", "주택"],
                "job": ["고용", "취업", "창업", "일자리"],
                "finance": ["금융", "대출", "서민금융"],
                "health": ["보건", "의료", "건강"],
                "family": ["임신", "출산", "보육", "육아", "가족"],
                "education": ["교육", "장학", "학교"],
                "culture": ["문화", "여가", "체육"],
                "safety": ["안전", "방범", "보안"],
                "welfare": ["생활지원", "복지"]
            }
            
            keywords = category_keywords.get(category, [])
            if keywords:
                keyword_conds = " OR ".join(["interest_themes::text LIKE %s" for _ in keywords])
                conditions.append(f"({keyword_conds})")
                for kw in keywords:
                    params.append(f"%{kw}%")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        SELECT policy_id, title, summary, ministry, source_type,
               ctpv_nm, sgg_nm, support_provision, phone, website,
               life_cycles, interest_themes
        FROM welfare_policies
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """
        
        params.extend([limit, offset])
        result = postgres.execute_query(query, tuple(params))

        if result:
            return {
                "total": len(result), # 필터링된 결과 수 (실제로는 COUNT(*) 쿼리 필요하지만 우선 이렇게 처리)
                "limit": limit,
                "offset": offset,
                "policies": result
            }

        return {"total": 0, "policies": []}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch policies: {str(e)}")


@router.get("/policies/{policy_id}")
async def get_welfare_policy(
    policy_id: str
):
    """
    특정 복지 정책 상세 조회

    Args:
        policy_id: 정책 ID
    """
    try:
        postgres = PostgresClient()
        result = postgres.get_policy_by_id(policy_id)

        if result:
            return result

        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch policy: {str(e)}")


@router.get("/stats")
async def get_welfare_stats():
    """복지 정책 통계 정보"""
    try:
        postgres = PostgresClient()

        total_count = postgres.count_policies()
        central_count = postgres.count_policies({"source_type": "central"})
        regional_count = postgres.count_policies({"source_type": "regional"})

        return {
            "total_policies": total_count,
            "central_policies": central_count,
            "regional_policies": regional_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.get("/recommendations")
async def get_welfare_recommendations(
    region: str = None,
    life_cycle: str = None,
    limit: int = 5,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    맞춤 추천 정책 조회 (대시보드용)
    - regional: 내 지역 정책 (region + life_cycle)
    - national: 전국 공통 정책 (life_cycle 위주)
    """
    try:
        postgres = PostgresClient()
        
        # 로그인 사용자인 경우 프로필 기반 기본값 설정
        if current_user:
            prefs = postgres.execute_one(
                "SELECT region, life_stage as life_cycle FROM user_preferences WHERE user_id = %s",
                (current_user["id"],)
            )
            if prefs:
                if not region:
                    region = prefs.get("region")
                if not life_cycle:
                    life_cycle = prefs.get("life_cycle")
                print(f"--- [DASHBOARD] Auto-applying profile for user {current_user['id']}: region={region}, life_cycle={life_cycle} ---")

        response = {
            "regional": [],
            "national": []
        }

        # 1. National Policies (source_type='central')
        national_conds = ["source_type = 'central'"]
        national_params = []
        
        if life_cycle:
            # Use OR condition: metadata (life_cycles) OR keywords in title/summary
            national_conds.append("(life_cycles::text LIKE %s OR title LIKE %s OR summary LIKE %s)")
            national_params.extend([f"%{life_cycle}%", f"%{life_cycle}%", f"%{life_cycle}%"])
            
        where_national = " WHERE " + " AND ".join(national_conds)
        
        national_query = f"""
        SELECT policy_id, title, summary, ministry, source_type, ctpv_nm, sgg_nm
        FROM welfare_policies
        {where_national}
        ORDER BY created_at DESC
        LIMIT %s
        """
        national_params.append(limit)
        response["national"] = postgres.execute_query(national_query, tuple(national_params)) or []

        # 2. Regional Policies (source_type='regional')
        if region:
            regional_conds = ["source_type = 'regional'", "ctpv_nm LIKE %s"]
            regional_params = [f"%{region}%"]
            
            if life_cycle:
                # Same fallback logic for regional
                regional_conds.append("(life_cycles::text LIKE %s OR title LIKE %s OR summary LIKE %s)")
                regional_params.extend([f"%{life_cycle}%", f"%{life_cycle}%", f"%{life_cycle}%"])
                
            where_regional = " WHERE " + " AND ".join(regional_conds)
            
            regional_query = f"""
            SELECT policy_id, title, summary, ministry, source_type, ctpv_nm, sgg_nm
            FROM welfare_policies
            {where_regional}
            ORDER BY created_at DESC
            LIMIT %s
            """
            regional_params.append(limit)
            response["regional"] = postgres.execute_query(regional_query, tuple(regional_params)) or []
        
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recommendations: {str(e)}")
