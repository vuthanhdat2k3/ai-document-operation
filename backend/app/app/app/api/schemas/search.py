"""Search request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """Hybrid search request body."""

    query: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None
    top_k: int = Field(default=10, ge=1, le=100)


class SearchResultItem(BaseModel):
    """A single search result."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    text: str
    score: float
    page: int = 0


class SearchResponse(BaseModel):
    """Search endpoint response."""

    model_config = ConfigDict(frozen=True)

    results: list[SearchResultItem]
    total: int
    query: str
    cached: bool = False
