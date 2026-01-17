"""Search schemas - 검색 관련 Pydantic 모델"""

from typing import List, Optional

from pydantic import BaseModel, Field


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
