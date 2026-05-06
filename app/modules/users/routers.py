from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import ApiResponse, PaginatedResponse, ApiRouter
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.modules.users.params import API_PREFIX
from app.modules.users.schemas import (
    AdminPasswordResetRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.modules.users.service import user_service

router = ApiRouter(
    prefix=API_PREFIX,
    tags=["Admin - User Management"],
    dependencies=[Depends(require_permission("USER_MANAGEMENT", "READ"))],
)


@router.get("/", response_model=ApiResponse[PaginatedResponse[UserListResponse]])
async def list_users(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    users, total = await user_service.search_users(
        db, search=search, is_active=is_active, page=page, size=size
    )
    paginated = PaginatedResponse.build(
        items=[UserListResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
    )
    return ApiResponse.success(data=paginated.model_dump())


@router.get("/{uuid}", response_model=ApiResponse[UserResponse])
async def get_user(uuid: str, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_by_uuid(db, uuid)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return ApiResponse.success(data=UserResponse.model_validate(user).model_dump())


@router.put(
    "/{uuid}",
    response_model=ApiResponse[UserResponse],
    dependencies=[Depends(require_permission("USER_MANAGEMENT", "UPDATE"))],
)
async def update_user(
    uuid: str, payload: UserUpdateRequest, db: AsyncSession = Depends(get_db)
):
    user = await user_service.update_user(db, uuid, payload)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return ApiResponse.success(
        message="User updated.", data=UserResponse.model_validate(user).model_dump()
    )


@router.delete(
    "/{uuid}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission("USER_MANAGEMENT", "DELETE"))],
)
async def delete_user(uuid: str, db: AsyncSession = Depends(get_db)):
    deleted = await user_service.delete_user(db, uuid)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return ApiResponse.success(message="User deleted.")


@router.put(
    "/{uuid}/password",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission("USER_MANAGEMENT", "UPDATE"))],
)
async def admin_reset_password(
    uuid: str,
    payload: AdminPasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.admin_reset_password(db, uuid, payload.new_password)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return ApiResponse.success(message="Password reset by admin.")
