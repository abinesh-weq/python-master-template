from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


# ── Standard API Envelope ─────────────────────────────────────────────────────
class ApiResponse(BaseModel, Generic[T]):
    """
    Mirrors Java ApiResponse<T>.
    Every endpoint MUST return this shape:
        {"status": "success|error", "message": "...", "data": {...}}
    """

    status: str
    message: str
    data: Optional[T] = None

    @classmethod
    def success(cls, message: str = "Success", data: Any = None) -> "ApiResponse":
        return cls(status="success", message=message, data=data)

    @classmethod
    def error(cls, message: str = "An error occurred", data: Any = None) -> "ApiResponse":
        return cls(status="error", message=message, data=data)


def get_default_error_responses() -> dict:
    from fastapi import status as http_status

    error_codes = {
        http_status.HTTP_400_BAD_REQUEST: "Bad Request",
        http_status.HTTP_401_UNAUTHORIZED: "Unauthorized",
        http_status.HTTP_403_FORBIDDEN: "Forbidden",
        http_status.HTTP_404_NOT_FOUND: "Not Found",
        http_status.HTTP_409_CONFLICT: "Conflict",
        http_status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal Server Error",
    }

    return {
        code: {"model": ApiResponse, "description": description}
        for code, description in error_codes.items()
    }


from fastapi import APIRouter


class ApiRouter(APIRouter):
    def add_api_route(self, path, endpoint, *, response_model=None, responses=None, **kwargs):
        merged_responses = {} if responses is None else dict(responses)
        for code, entry in get_default_error_responses().items():
            merged_responses.setdefault(code, entry)
        super().add_api_route(
            path,
            endpoint,
            response_model=response_model,
            responses=merged_responses,
            **kwargs,
        )


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
