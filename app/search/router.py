"""Search router for welfare policy semantic search"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import get_current_user
from app.search.schemas import SearchResponse, SearchResult
from shared.db.qdrant_client import QdrantClient

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/semantic", response_model=SearchResponse)
async def semantic_search(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query"),
    source_type: Optional[str] = Query(None, description="Filter by source: central or regional"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return")
):
    """
    Semantic search for welfare policies using multilingual-e5-large + BM25 hybrid search

    **Features**:
    - Meaning-based search (finds similar policies even with different words)
    - Korean language optimized
    - Optional filters by source type

    **Examples**:
    - q="임신부 지원" → Find pregnancy/maternity support policies
    - q="청년 창업" → Find youth entrepreneurship policies
    - q="어르신 건강" → Find elderly healthcare policies
    """
    # Get qdrant service from app state (pre-loaded at startup)
    qdrant_service = getattr(request.app.state, "qdrant_service", None)

    if not qdrant_service:
        raise HTTPException(
            status_code=503,
            detail="Search service is not available. Server may still be loading."
        )

    # Search in Qdrant using hybrid search
    try:
        results = qdrant_service.hybrid_search(
            query=q,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

    # Format response
    search_results = [
        SearchResult(
            policy_id=result.get("policy_id", ""),
            score=result.get("score", 0),
            title=result.get("title", ""),
            summary=result.get("summary", ""),
            ministry=result.get("ministry", ""),
            source_type=result.get("source_type", ""),
            ctpv_nm=result.get("ctpv_nm"),
            sgg_nm=result.get("sgg_nm"),
            phone=result.get("phone"),
            website=result.get("website"),
        )
        for result in results
    ]

    return SearchResponse(
        query=q,
        total=len(search_results),
        results=search_results
    )


@router.get("/health")
async def search_health(request: Request):
    """
    Check search service health

    Returns embedding service status and Qdrant connection
    """
    embedding_service = getattr(request.app.state, "embedding_service", None)
    qdrant = QdrantClient()

    return {
        "embedding_service": "ready" if embedding_service else "not_loaded",
        "qdrant": "ready" if qdrant.health_check() else "unavailable",
        "collection_count": qdrant.count_policies() if qdrant.health_check() else 0
    }
