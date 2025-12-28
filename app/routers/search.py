"""Search router for welfare policy semantic search"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from shared.db.qdrant_client import QdrantClient

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    """Search result response model"""

    policy_id: str = Field(..., description="Policy ID")
    score: float = Field(..., description="Similarity score (0-1)")
    title: str = Field(..., description="Policy title")
    summary: str = Field(..., description="Policy summary")
    ministry: str = Field(..., description="Ministry name")
    source_type: str = Field(..., description="central or regional")
    ctpv_nm: Optional[str] = Field(None, description="Province/City name")
    sgg_nm: Optional[str] = Field(None, description="District name")
    phone: Optional[str] = Field(None, description="Contact phone")
    website: Optional[str] = Field(None, description="Policy website")


class SearchResponse(BaseModel):
    """Search API response"""

    query: str = Field(..., description="Search query")
    total: int = Field(..., description="Number of results")
    results: List[SearchResult] = Field(..., description="Search results")


@router.get("/semantic", response_model=SearchResponse)
async def semantic_search(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query"),
    source_type: Optional[str] = Query(None, description="Filter by source: central or regional"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
):
    """
    Semantic search for welfare policies using BGE-M3 embeddings

    **Features**:
    - Meaning-based search (finds similar policies even with different words)
    - Korean language optimized
    - Optional filters by source type

    **Examples**:
    - q="임신부 지원" → Find pregnancy/maternity support policies
    - q="청년 창업" → Find youth entrepreneurship policies
    - q="어르신 건강" → Find elderly healthcare policies
    """
    # Get embedding service from app state (pre-loaded at startup)
    embedding_service = request.app.state.embedding_service

    if not embedding_service:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not available. Server may still be loading."
        )

    # 1. Generate query embedding
    try:
        query_vector = embedding_service.encode_query(q)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate query embedding: {str(e)}"
        )

    # 2. Search in Qdrant
    qdrant = QdrantClient()

    # Build filters
    filters = {}
    if source_type:
        if source_type not in ["central", "regional"]:
            raise HTTPException(
                status_code=400,
                detail="source_type must be 'central' or 'regional'"
            )
        filters["source_type"] = source_type

    try:
        results = qdrant.search(
            query_vector=query_vector,
            filters=filters,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

    # 3. Format response
    search_results = [
        SearchResult(
            policy_id=result["id"],
            score=result["score"],
            title=result["metadata"].get("title", ""),
            summary=result["metadata"].get("summary", ""),
            ministry=result["metadata"].get("ministry", ""),
            source_type=result["metadata"].get("source_type", ""),
            ctpv_nm=result["metadata"].get("ctpv_nm"),
            sgg_nm=result["metadata"].get("sgg_nm"),
            phone=result["metadata"].get("phone"),
            website=result["metadata"].get("website"),
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
    embedding_service = request.app.state.embedding_service
    qdrant = QdrantClient()

    return {
        "embedding_service": "ready" if embedding_service else "not_loaded",
        "qdrant": "ready" if qdrant.health_check() else "unavailable",
        "collection_count": qdrant.count_policies() if qdrant.health_check() else 0
    }
