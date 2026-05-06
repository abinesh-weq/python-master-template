from typing import Any, Generic, Optional, TypeVar
from datetime import datetime

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseApiResponse(BaseModel, Generic[T]):
    """
    Mirrors Java ApiResponse<T>.
    Standard API response format for all endpoints.
    """
    status: str = Field(..., description="SUCCESS | ERROR")
    message: str = Field(..., description="Response message")
    data: Optional[T] = Field(None, description="Response data payload")

    @classmethod
    def success(cls, message: str = "Success", data: Any = None) -> "BaseApiResponse":
        return cls(status="SUCCESS", message=message, data=data)

    @classmethod
    def error(cls, message: str = "An error occurred", data: Any = None) -> "BaseApiResponse":
        return cls(status="ERROR", message=message, data=data)


class BaseEntitySchema(BaseModel):
    """
    Base schema for entities with common fields.
    Mirrors the base entity structure.
    """
    uuid: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator UUID")
    updated_by: Optional[str] = Field(None, description="Updater UUID")


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., ge=1, description="Current page number")
    size: int = Field(..., ge=1, le=100, description="Page size")
    total: int = Field(..., ge=0, description="Total items")
    pages: int = Field(..., ge=0, description="Total pages")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Mirrors Java Page<T> output.
    Shape: {"items": [...], "pagination": {...}}
    """
    items: list[T] = Field(..., description="List of items")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")

    @classmethod
    def build(
        cls,
        items: list,
        total: int,
        page: int,
        size: int,
    ) -> "PaginatedResponse":
        import math

        return cls(
            items=items,
            pagination=PaginationInfo(
                page=page,
                size=size,
                total=total,
                pages=math.ceil(total / size) if size else 0
            )
        )
