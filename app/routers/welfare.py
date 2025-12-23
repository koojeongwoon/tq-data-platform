"""
Welfare Policy Router
"""
from fastapi import APIRouter, HTTPException

from shared.db.d1 import D1Client

router = APIRouter(prefix="/welfare", tags=["Welfare"])


@router.get("/policies")
async def get_welfare_policies(limit: int = 100, offset: int = 0):
    """
    D1에서 복지 정책 목록 조회

    Args:
        limit: 조회할 정책 개수 (기본: 100)
        offset: 시작 위치 (기본: 0)
    """
    try:
        d1 = D1Client()

        query = f"""
        SELECT policy_id, policy_name, policy_summary, target_audience,
               support_details, application_method, created_at
        FROM welfare_policies
        ORDER BY created_at DESC
        LIMIT {limit} OFFSET {offset}
        """

        result = d1.execute_query(query)

        if result and "results" in result:
            policies = result["results"]
            return {
                "total": len(policies),
                "limit": limit,
                "offset": offset,
                "policies": policies
            }

        return {"total": 0, "policies": []}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch policies: {str(e)}")


@router.get("/policies/{policy_id}")
async def get_welfare_policy(policy_id: str):
    """
    특정 복지 정책 상세 조회

    Args:
        policy_id: 정책 ID
    """
    try:
        d1 = D1Client()

        query = f"""
        SELECT *
        FROM welfare_policies
        WHERE policy_id = '{policy_id}'
        """

        result = d1.execute_query(query)

        if result and "results" in result and len(result["results"]) > 0:
            return result["results"][0]

        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch policy: {str(e)}")


@router.get("/stats")
async def get_welfare_stats():
    """
    복지 정책 통계 정보
    """
    try:
        d1 = D1Client()

        # 전체 정책 수
        total_query = "SELECT COUNT(*) as total FROM welfare_policies"
        total_result = d1.execute_query(total_query)

        total_count = 0
        if total_result and "results" in total_result and len(total_result["results"]) > 0:
            total_count = total_result["results"][0].get("total", 0)

        # 최근 업데이트 시간
        latest_query = "SELECT MAX(created_at) as latest FROM welfare_policies"
        latest_result = d1.execute_query(latest_query)

        latest_update = None
        if latest_result and "results" in latest_result and len(latest_result["results"]) > 0:
            latest_update = latest_result["results"][0].get("latest")

        return {
            "total_policies": total_count,
            "latest_update": latest_update
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
