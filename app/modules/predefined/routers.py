from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_cache.decorator import cache
from fastapi_cache import FastAPICache
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import ApiResponse, PaginatedResponse, ApiRouter
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.modules.predefined.params import API_PREFIX
from app.modules.predefined.schemas import (
    PredefinedMasterCreateRequest,
    PredefinedMasterResponse,
    PredefinedMasterUpdateRequest,
)
from app.modules.predefined.service import predefined_service

router = ApiRouter(
    prefix=API_PREFIX,
    tags=["Predefined Master"],
    dependencies=[Depends(require_permission("MASTER", "READ"))],
)


@router.get("/", response_model=ApiResponse[PaginatedResponse[PredefinedMasterResponse]])
@cache(expire=3600)  # Mirrors Java @Cacheable — freeze HTTP response for 1 hour
async def list_predefined(
    entity_type: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    code: Optional[str] = Query(None),
    parent_uuid: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    records, total = await predefined_service.get_all(
        db,
        entity_type=entity_type,
        name=name,
        code=code,
        parent_uuid=parent_uuid,
        page=page,
        size=size,
    )
    paginated = PaginatedResponse.build(
        items=[PredefinedMasterResponse.model_validate(r) for r in records],
        total=total,
        page=page,
        size=size,
    )
    return ApiResponse.success(data=paginated.model_dump())


@router.get("/{uuid}", response_model=ApiResponse[PredefinedMasterResponse])
async def get_predefined(record_uuid: str, db: AsyncSession = Depends(get_db)):
    record = await predefined_service.get_by_uuid(db, record_uuid)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    return ApiResponse.success(
        data=PredefinedMasterResponse.model_validate(record).model_dump()
    )


@router.post(
    "/",
    response_model=ApiResponse[PredefinedMasterResponse],
    dependencies=[Depends(require_permission("MASTER", "WRITE"))],
)
async def create_predefined(
    payload: PredefinedMasterCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    record = await predefined_service.create(db, payload)
    await FastAPICache.clear()  # Mirrors Java @CacheEvict — bust all cached responses
    return ApiResponse.success(
        message="Record created.",
        data=PredefinedMasterResponse.model_validate(record).model_dump(),
    )


@router.put(
    "/{uuid}",
    response_model=ApiResponse[PredefinedMasterResponse],
    dependencies=[Depends(require_permission("MASTER", "UPDATE"))],
)
async def update_predefined(
    record_uuid: str,
    payload: PredefinedMasterUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    record = await predefined_service.update(db, record_uuid, payload)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    await FastAPICache.clear()  # Bust cache on every mutation
    return ApiResponse.success(
        message="Record updated.",
        data=PredefinedMasterResponse.model_validate(record).model_dump(),
    )


@router.delete(
    "/{uuid}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission("MASTER", "DELETE"))],
)
async def delete_predefined(uuid: str, db: AsyncSession = Depends(get_db)):
    # IntegrityError (orphan FK) is caught inside the service layer
    deleted = await predefined_service.delete(db, uuid)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    await FastAPICache.clear()  # Bust cache after structural deletion
    return ApiResponse.success(message="Record deleted.")
