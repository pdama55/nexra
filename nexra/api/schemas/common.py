from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaResponse(BaseModel):
    request_id: str | None = None
    latency_ms: float | None = None


class DataResponse(BaseModel, Generic[T]):
    """Standard response envelope: { data: T, meta: {...} }"""

    data: T
    meta: MetaResponse = MetaResponse()


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Standard error envelope: { error: {...} }"""

    error: ErrorDetail


class PaginationParams(BaseModel):
    cursor: str | None = Field(
        None, description="Cursor from previous response for pagination"
    )
    limit: int = Field(50, ge=1, le=100, description="Number of items per page")


class PaginatedMeta(MetaResponse):
    next_cursor: str | None = None
    total_count: int | None = None
