from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


# ── Standard API Envelope ─────────────────────────────────────────────────────
class ApiResponse(BaseModel, Generic[T]):
    """
    Mirrors Java ApiResponse<T>.
    Every endpoint MUST return this shape:
        {"status": "SUCCESS|ERROR", "message": "...", "data": {...}}
    """

    status: str
    message: str
    data: Optional[T] = None

    @classmethod
    def success(cls, message: str = "Success", data: Any = None) -> "ApiResponse":
        return cls(status="SUCCESS", message=message, data=data)

    @classmethod
    def error(cls, message: str = "An error occurred", data: Any = None) -> "ApiResponse":
        return cls(status="ERROR", message=message, data=data)


# ── Pagination Wrapper ────────────────────────────────────────────────────────
class PageableInfo(BaseModel):
    pageNumber: int
    pageSize: int


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Mirrors Java Page<T> output.
    Shape: {"content": [...], "pageable": {...}, "totalElements": 100, "totalPages": 5}
    """

    content: list[T]
    pageable: PageableInfo
    totalElements: int
    totalPages: int

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
            content=items,
            pageable=PageableInfo(pageNumber=page, pageSize=size),
            totalElements=total,
            totalPages=math.ceil(total / size) if size else 0,
        )
