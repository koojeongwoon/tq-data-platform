"""
Welfare Policy Router
"""
from fastapi import APIRouter, HTTPException

from shared.db.postgres import PostgresClient

router = APIRouter(prefix="/welfare", tags=["Welfare"])


@router.get("/policies")
async def get_welfare_policies(limit: int = 100, offset: int = 0):
    """
    PostgreSQL에서 복지 정책 목록 조회

    Args:
        limit: 조회할 정책 개수 (기본: 100)
        offset: 시작 위치 (기본: 0)
    """
    try:
        postgres = PostgresClient()

        query = f"""
        SELECT policy_id, title, summary, ministry, source_type,
               ctpv_nm, sgg_nm, support_provision, phone, website
        FROM welfare_policies
        ORDER BY created_at DESC
        LIMIT {limit} OFFSET {offset}
        """

        result = postgres.execute_query(query)

        if result:
            return {
                "total": len(result),
                "limit": limit,
                "offset": offset,
                "policies": result
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
    """
    복지 정책 통계 정보
    """
    try:
        postgres = PostgresClient()

        # 전체 정책 수
        total_count = postgres.count_policies()

        # 중앙/지방 정책 수
        central_count = postgres.count_policies({"source_type": "central"})
        regional_count = postgres.count_policies({"source_type": "regional"})

        return {
            "total_policies": total_count,
            "central_policies": central_count,
            "regional_policies": regional_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
