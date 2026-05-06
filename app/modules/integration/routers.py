from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import ApiResponse, PaginatedResponse, ApiRouter
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.modules.integration.params import API_PREFIX
from app.modules.integration.schemas import (
    CommunicationProviderConfigCreateRequest,
    CommunicationProviderConfigResponse,
    CommunicationProviderConfigUpdateRequest,
    NotificationLogResponse,
    NotificationPayloadLogResponse,
    NotificationTemplateMasterCreateRequest,
    NotificationTemplateMasterResponse,
    NotificationTemplateMasterUpdateRequest,
    ProviderApiMappingCreateRequest,
    ProviderApiMappingResponse,
    ProviderApiMappingUpdateRequest,
    ProviderApiMetadataCreateRequest,
    ProviderApiMetadataResponse,
    ProviderApiMetadataUpdateRequest,
)
from app.modules.integration.service import integration_service

router = ApiRouter(
    prefix=API_PREFIX,
    tags=["Admin - Integration Management"],
    dependencies=[Depends(require_permission("INTEGRATION_MANAGEMENT", "READ"))],
)


# ── Communication Provider Config ─────────────────────────────────────────────
@router.post("/providers", response_model=ApiResponse[CommunicationProviderConfigResponse])
async def create_provider_config(
    payload: CommunicationProviderConfigCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "WRITE"))] = None,
):
    provider = await integration_service.create_provider_config(db, payload.model_dump())
    return ApiResponse.success(
        message="Provider config created.",
        data=CommunicationProviderConfigResponse.model_validate(provider).model_dump(),
    )


@router.get("/providers", response_model=ApiResponse[PaginatedResponse[CommunicationProviderConfigResponse]])
async def list_provider_configs(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    providers, total = await integration_service.get_provider_configs(db, page, size)
    paginated = PaginatedResponse.build(
        items=[CommunicationProviderConfigResponse.model_validate(p).model_dump() for p in providers],
        total=total,
        page=page,
        size=size,
    )
    return ApiResponse.success(data=paginated.model_dump())


@router.get("/providers/{uuid}", response_model=ApiResponse[CommunicationProviderConfigResponse])
async def get_provider_config(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    provider = await integration_service.get_provider_config_by_uuid(db, uuid)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider config not found.")
    return ApiResponse.success(
        data=CommunicationProviderConfigResponse.model_validate(provider).model_dump()
    )


@router.put("/providers/{uuid}", response_model=ApiResponse[CommunicationProviderConfigResponse])
async def update_provider_config(
    uuid: str,
    payload: CommunicationProviderConfigUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "UPDATE"))] = None,
):
    provider = await integration_service.update_provider_config(db, uuid, payload.model_dump(exclude_unset=True))
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider config not found.")
    return ApiResponse.success(
        message="Provider config updated.",
        data=CommunicationProviderConfigResponse.model_validate(provider).model_dump(),
    )


@router.delete("/providers/{uuid}", response_model=ApiResponse[None])
async def delete_provider_config(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "DELETE"))] = None,
):
    deleted = await integration_service.delete_provider_config(db, uuid)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider config not found.")
    return ApiResponse.success(message="Provider config deleted.")


# ── Provider API Metadata ─────────────────────────────────────────────────────
@router.post("/metadata", response_model=ApiResponse[ProviderApiMetadataResponse])
async def create_provider_metadata(
    payload: ProviderApiMetadataCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "WRITE"))] = None,
):
    metadata = await integration_service.create_provider_metadata(db, payload.model_dump())
    return ApiResponse.success(
        message="Provider metadata created.",
        data=ProviderApiMetadataResponse.model_validate(metadata).model_dump(),
    )


@router.get("/metadata/{provider_uuid}", response_model=ApiResponse[ProviderApiMetadataResponse])
async def get_provider_metadata(
    provider_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    metadata = await integration_service.get_provider_metadata(db, provider_uuid)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider metadata not found.")
    return ApiResponse.success(
        data=ProviderApiMetadataResponse.model_validate(metadata).model_dump()
    )


@router.put("/metadata/{provider_uuid}", response_model=ApiResponse[ProviderApiMetadataResponse])
async def update_provider_metadata(
    provider_uuid: str,
    payload: ProviderApiMetadataUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "UPDATE"))] = None,
):
    metadata = await integration_service.update_provider_metadata(db, provider_uuid, payload.model_dump(exclude_unset=True))
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider metadata not found.")
    return ApiResponse.success(
        message="Provider metadata updated.",
        data=ProviderApiMetadataResponse.model_validate(metadata).model_dump(),
    )


@router.delete("/metadata/{provider_uuid}", response_model=ApiResponse[None])
async def delete_provider_metadata(
    provider_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "DELETE"))] = None,
):
    deleted = await integration_service.delete_provider_metadata(db, provider_uuid)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider metadata not found.")
    return ApiResponse.success(message="Provider metadata deleted.")


# ── Provider API Mapping ──────────────────────────────────────────────────────
@router.post("/mappings", response_model=ApiResponse[ProviderApiMappingResponse])
async def create_provider_mapping(
    payload: ProviderApiMappingCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "WRITE"))] = None,
):
    mapping = await integration_service.create_provider_mapping(db, payload.model_dump())
    return ApiResponse.success(
        message="Provider mapping created.",
        data=ProviderApiMappingResponse.model_validate(mapping).model_dump(),
    )


@router.get("/mappings", response_model=ApiResponse[PaginatedResponse[ProviderApiMappingResponse]])
async def list_provider_mappings(
    provider_uuid: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    mappings, total = await integration_service.get_provider_mappings(db, provider_uuid, page, size)
    paginated = PaginatedResponse.build(
        items=[ProviderApiMappingResponse.model_validate(m).model_dump() for m in mappings],
        total=total,
        page=page,
        size=size,
    )
    return ApiResponse.success(data=paginated.model_dump())


@router.get("/mappings/{uuid}", response_model=ApiResponse[ProviderApiMappingResponse])
async def get_provider_mapping(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    mapping = await integration_service.get_provider_mapping_by_uuid(db, uuid)
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider mapping not found.")
    return ApiResponse.success(
        data=ProviderApiMappingResponse.model_validate(mapping).model_dump()
    )


@router.put("/mappings/{uuid}", response_model=ApiResponse[ProviderApiMappingResponse])
async def update_provider_mapping(
    uuid: str,
    payload: ProviderApiMappingUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "UPDATE"))] = None,
):
    mapping = await integration_service.update_provider_mapping(db, uuid, payload.model_dump(exclude_unset=True))
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider mapping not found.")
    return ApiResponse.success(
        message="Provider mapping updated.",
        data=ProviderApiMappingResponse.model_validate(mapping).model_dump(),
    )


@router.delete("/mappings/{uuid}", response_model=ApiResponse[None])
async def delete_provider_mapping(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "DELETE"))] = None,
):
    deleted = await integration_service.delete_provider_mapping(db, uuid)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider mapping not found.")
    return ApiResponse.success(message="Provider mapping deleted.")


# ── Notification Template Master ──────────────────────────────────────────────
@router.post("/templates", response_model=ApiResponse[NotificationTemplateMasterResponse])
async def create_template(
    payload: NotificationTemplateMasterCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "WRITE"))] = None,
):
    # Check if code already exists
    existing = await integration_service.get_template_by_code(db, payload.code)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template code already exists.")
    
    template = await integration_service.create_template(db, payload.model_dump())
    return ApiResponse.success(
        message="Template created.",
        data=NotificationTemplateMasterResponse.model_validate(template).model_dump(),
    )


@router.get("/templates", response_model=ApiResponse[PaginatedResponse[NotificationTemplateMasterResponse]])
async def list_templates(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    templates, total = await integration_service.get_templates(db, page, size)
    paginated = PaginatedResponse.build(
        items=[NotificationTemplateMasterResponse.model_validate(t).model_dump() for t in templates],
        total=total,
        page=page,
        size=size,
    )
    return ApiResponse.success(data=paginated.model_dump())


@router.get("/templates/{uuid}", response_model=ApiResponse[NotificationTemplateMasterResponse])
async def get_template(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    template = await integration_service.get_template_by_uuid(db, uuid)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    return ApiResponse.success(
        data=NotificationTemplateMasterResponse.model_validate(template).model_dump()
    )


@router.put("/templates/{uuid}", response_model=ApiResponse[NotificationTemplateMasterResponse])
async def update_template(
    uuid: str,
    payload: NotificationTemplateMasterUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "UPDATE"))] = None,
):
    template = await integration_service.update_template(db, uuid, payload.model_dump(exclude_unset=True))
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    return ApiResponse.success(
        message="Template updated.",
        data=NotificationTemplateMasterResponse.model_validate(template).model_dump(),
    )


@router.delete("/templates/{uuid}", response_model=ApiResponse[None])
async def delete_template(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[None, Depends(require_permission("INTEGRATION_MANAGEMENT", "DELETE"))] = None,
):
    deleted = await integration_service.delete_template(db, uuid)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    return ApiResponse.success(message="Template deleted.")


# ── Notification Logs (Read-only) ─────────────────────────────────────────────
@router.get("/logs", response_model=ApiResponse[PaginatedResponse[NotificationLogResponse]])
async def list_notification_logs(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    logs, total = await integration_service.get_notification_logs(db, page, size)
    paginated = PaginatedResponse.build(
        items=[NotificationLogResponse.model_validate(log).model_dump() for log in logs],
        total=total,
        page=page,
        size=size,
    )
    return ApiResponse.success(data=paginated.model_dump())


@router.get("/logs/{uuid}", response_model=ApiResponse[NotificationLogResponse])
async def get_notification_log(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    log = await integration_service.get_notification_log_by_uuid(db, uuid)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification log not found.")
    
    return ApiResponse.success(
        data=NotificationLogResponse.model_validate(log).model_dump()
    )


@router.get("/logs/{uuid}/payloads", response_model=ApiResponse[list[NotificationPayloadLogResponse]])
async def get_notification_payloads(
    uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    payloads = await integration_service.get_payload_logs(db, uuid)
    return ApiResponse.success(
        data=[NotificationPayloadLogResponse.model_validate(p).model_dump() for p in payloads]
    )