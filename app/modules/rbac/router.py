from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import ApiResponse
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.modules.audit.service import audit_service
from app.modules.rbac.schemas import (
    AccessControlResponse,
    ModuleResponse,
    PermissionToggleRequest,
    RoleCreateRequest,
    RoleModuleMappingResponse,
    RoleResponse,
)
from app.modules.rbac.service import rbac_service

router = APIRouter(
    prefix="/api/v1/admin/rbac",
    tags=["Admin - RBAC Management"],
    dependencies=[Depends(require_permission("RBAC_MANAGEMENT", "READ"))],
)


# ── Roles ─────────────────────────────────────────────────────────────────────

@router.get("/roles", response_model=ApiResponse)
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[Any, Depends(get_current_user)],
):
    roles = await rbac_service.get_all_roles(db)

    await audit_service.log(
        db=db,
        user_id=admin.id,
        username=admin.username,
        action="LIST_ROLES",
        module="RBAC",
        response_body=roles,
        status_code=status.HTTP_200_OK
    )

    return ApiResponse.success(
        data=[RoleResponse.model_validate(r).model_dump() for r in roles]
    )


@router.post(
    "/roles",
    response_model=ApiResponse,
    dependencies=[Depends(require_permission("RBAC_MANAGEMENT", "WRITE"))],
)
async def create_role(
    payload: RoleCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[Any, Depends(get_current_user)],  # Any for simplicity
):
    try:
        role = await rbac_service.create_role(db, payload)

        await audit_service.log(
            db=db,
            user_id=admin.id,
            username=admin.username,
            action="CREATE_ROLE",
            module="RBAC",
            description=f"Created role: {role.name}",
            payload=payload.model_dump(),
            status_code=status.HTTP_201_CREATED,
            response_body=role  # AuditService will summarize or log as needed
        )

        return ApiResponse.success(
            message="Role created.", data=RoleResponse.model_validate(role).model_dump()
        )
    except Exception as e:
        await audit_service.log(
            db=db,
            user_id=admin.id,
            username=admin.username,
            action="CREATE_ROLE_FAILED",
            module="RBAC",
            description=f"Error: {str(e)}",
            payload=payload.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise e


@router.delete(
    "/roles/{uuid}",
    response_model=ApiResponse,
    dependencies=[Depends(require_permission("RBAC_MANAGEMENT", "DELETE"))],
)
async def delete_role(
    uuid: str, db: AsyncSession = Depends(get_db), admin=Depends(get_current_user)
):
    deleted = await rbac_service.delete_role(db, uuid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found."
        )

    await audit_service.log(
        db=db,
        user_id=admin.id,
        username=admin.username,
        action="DELETE_ROLE",
        module="RBAC",
        description=f"Deleted role ID: {uuid}"
    )

    return ApiResponse.success(message="Role deleted.")


# ── Modules ───────────────────────────────────────────────────────────────────

@router.get("/modules", response_model=ApiResponse)
async def list_modules(
    db: AsyncSession = Depends(get_db),
    admin: Any = Depends(get_current_user),
):
    modules = await rbac_service.get_all_modules(db)

    await audit_service.log(
        db=db,
        user_id=admin.id,
        username=admin.username,
        action="LIST_MODULES",
        module="RBAC",
        response_body=modules,
        status_code=status.HTTP_200_OK
    )

    return ApiResponse.success(
        data=[ModuleResponse.model_validate(m).model_dump() for m in modules]
    )


# ── Role-Module Mapping Matrix ────────────────────────────────────────────────

@router.get("/roles/{role_uuid}/modules", response_model=ApiResponse)
async def get_role_modules(role_uuid: str, db: AsyncSession = Depends(get_db)):
    mappings = await rbac_service.get_role_modules(db, role_uuid)
    return ApiResponse.success(
        data=[RoleModuleMappingResponse.model_validate(m).model_dump() for m in mappings]
    )


@router.put(
    "/roles/{role_uuid}/modules/{module_uuid}",
    response_model=ApiResponse,
    dependencies=[Depends(require_permission("RBAC_MANAGEMENT", "UPDATE"))],
)
async def upsert_role_module(
    role_uuid: str,
    module_uuid: str,
    payload: PermissionToggleRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_user),
):
    mapping = await rbac_service.upsert_role_module(db, role_uuid, module_uuid, payload)

    await audit_service.log(
        db=db,
        user_id=admin.id,
        username=admin.username,
        action="UPDATE_ROLE_PERMISSIONS",
        module="RBAC",
        description=f"Updated permissions for Role {role_uuid} on Module {module_uuid}",
        payload=payload.model_dump()
    )

    return ApiResponse.success(
        message="Role-module permissions updated.",
        data=RoleModuleMappingResponse.model_validate(mapping).model_dump(),
    )


@router.delete(
    "/roles/{role_uuid}/modules/{module_uuid}",
    response_model=ApiResponse,
    dependencies=[Depends(require_permission("RBAC_MANAGEMENT", "DELETE"))],
)
async def delete_role_module(
    role_uuid: str, module_uuid: str, db: AsyncSession = Depends(get_db)
):
    deleted = await rbac_service.delete_role_module(db, role_uuid, module_uuid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found."
        )
    return ApiResponse.success(message="Role-module mapping deleted. Role reverts to defaults.")


# ── User Access Control Overrides ─────────────────────────────────────────────

@router.get("/users/{user_uuid}/access", response_model=ApiResponse)
async def get_user_access(user_uuid: str, db: AsyncSession = Depends(get_db)):
    records = await rbac_service.get_all_user_access(db, user_uuid)
    return ApiResponse.success(
        data=[AccessControlResponse.model_validate(r).model_dump() for r in records]
    )


@router.put(
    "/users/{user_uuid}/access/{module_uuid}",
    response_model=ApiResponse,
    dependencies=[Depends(require_permission("RBAC_MANAGEMENT", "UPDATE"))],
)
async def upsert_user_access(
    user_uuid: str,
    module_uuid: str,
    payload: PermissionToggleRequest,
    db: AsyncSession = Depends(get_db),
):
    record = await rbac_service.upsert_user_access(db, user_uuid, module_uuid, payload)
    return ApiResponse.success(
        message="User access override updated.",
        data=AccessControlResponse.model_validate(record).model_dump(),
    )


@router.delete(
    "/users/{user_uuid}/access/{module_uuid}",
    response_model=ApiResponse,
    dependencies=[Depends(require_permission("RBAC_MANAGEMENT", "DELETE"))],
)
async def delete_user_access(
    user_uuid: str, module_uuid: str, db: AsyncSession = Depends(get_db)
):
    deleted = await rbac_service.delete_user_access(db, user_uuid, module_uuid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Access override not found."
        )
    return ApiResponse.success(
        message="User access override removed. Falls back to role permissions."
    )
