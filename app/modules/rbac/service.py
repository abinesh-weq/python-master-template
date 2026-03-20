from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rbac.models import (
    AccessControlMaster,
    ModuleMaster,
    RefreshToken,
    RoleMaster,
    RoleModuleMapping,
)
from app.modules.rbac.schemas import PermissionToggleRequest, RoleCreateRequest


class RbacService:

    # ── Roles ─────────────────────────────────────────────────────────────────

    async def create_role(self, db: AsyncSession, payload: RoleCreateRequest) -> RoleMaster:
        role = RoleMaster(**payload.model_dump())
        db.add(role)
        await db.flush()
        return role

    async def get_all_roles(self, db: AsyncSession) -> list[RoleMaster]:
        result = await db.execute(select(RoleMaster))
        return list(result.scalars().all())

    async def get_role_by_id(self, db: AsyncSession, role_id: str) -> Optional[RoleMaster]:
        result = await db.execute(select(RoleMaster).where(RoleMaster.id == role_id))
        return result.scalar_one_or_none()

    async def get_role_by_name(self, db: AsyncSession, name: str) -> Optional[RoleMaster]:
        result = await db.execute(select(RoleMaster).where(RoleMaster.name == name))
        return result.scalar_one_or_none()

    async def delete_role(self, db: AsyncSession, role_id: str) -> bool:
        role = await self.get_role_by_id(db, role_id)
        if not role:
            return False
        await db.delete(role)
        return True

    # ── Modules ───────────────────────────────────────────────────────────────

    async def get_all_modules(self, db: AsyncSession) -> list[ModuleMaster]:
        result = await db.execute(select(ModuleMaster).where(ModuleMaster.is_active.is_(True)))
        return list(result.scalars().all())

    async def get_module_by_code(self, db: AsyncSession, code: str) -> Optional[ModuleMaster]:
        result = await db.execute(
            select(ModuleMaster).where(ModuleMaster.module_code == code)
        )
        return result.scalar_one_or_none()

    # ── Role-Module Mappings ───────────────────────────────────────────────────

    async def get_role_modules(self, db: AsyncSession, role_id: str) -> list[RoleModuleMapping]:
        result = await db.execute(
            select(RoleModuleMapping).where(RoleModuleMapping.role_id == role_id)
        )
        return list(result.scalars().all())

    async def upsert_role_module(
        self, db: AsyncSession, role_id: str, module_id: str, payload: PermissionToggleRequest
    ) -> RoleModuleMapping:
        """
        Upserts a role-module permission entry.
        Mirrors Java RbacService.toggleRoleModulePermission().
        """
        result = await db.execute(
            select(RoleModuleMapping).where(
                and_(
                    RoleModuleMapping.role_id == role_id,
                    RoleModuleMapping.module_id == module_id,
                )
            )
        )
        mapping = result.scalar_one_or_none()

        if not mapping:
            mapping = RoleModuleMapping(role_id=role_id, module_id=module_id)
            db.add(mapping)

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(mapping, field, value)

        await db.flush()
        return mapping

    async def delete_role_module(
        self, db: AsyncSession, role_id: str, module_id: str
    ) -> bool:
        result = await db.execute(
            select(RoleModuleMapping).where(
                and_(
                    RoleModuleMapping.role_id == role_id,
                    RoleModuleMapping.module_id == module_id,
                )
            )
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            return False
        await db.delete(mapping)
        return True

    # ── User Access Control Overrides ─────────────────────────────────────────

    async def get_user_access(
        self, db: AsyncSession, user_id: str, module_id: str
    ) -> Optional[AccessControlMaster]:
        result = await db.execute(
            select(AccessControlMaster).where(
                and_(
                    AccessControlMaster.user_id == user_id,
                    AccessControlMaster.module_id == module_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all_user_access(
        self, db: AsyncSession, user_id: str
    ) -> list[AccessControlMaster]:
        result = await db.execute(
            select(AccessControlMaster).where(AccessControlMaster.user_id == user_id)
        )
        return list(result.scalars().all())

    async def upsert_user_access(
        self,
        db: AsyncSession,
        user_id: str,
        module_id: str,
        payload: PermissionToggleRequest,
    ) -> AccessControlMaster:
        record = await self.get_user_access(db, user_id, module_id)

        if not record:
            record = AccessControlMaster(user_id=user_id, module_id=module_id)
            db.add(record)

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(record, field, value)

        await db.flush()
        return record

    async def delete_user_access(
        self, db: AsyncSession, user_id: str, module_id: str
    ) -> bool:
        record = await self.get_user_access(db, user_id, module_id)
        if not record:
            return False
        await db.delete(record)
        return True

    # ── Refresh Token Management ──────────────────────────────────────────────

    async def save_refresh_token(
        self, db: AsyncSession, user_id: str, token: str, expires_at: str
    ) -> RefreshToken:
        rt = RefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        db.add(rt)
        await db.flush()
        return rt

    async def get_refresh_token(
        self, db: AsyncSession, token: str
    ) -> Optional[RefreshToken]:
        result = await db.execute(
            select(RefreshToken).where(
                and_(RefreshToken.token == token, RefreshToken.is_revoked.is_(False))
            )
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, db: AsyncSession, token: str) -> None:
        rt = await self.get_refresh_token(db, token)
        if rt:
            rt.is_revoked = True
            await db.flush()

    async def revoke_all_user_tokens(self, db: AsyncSession, user_id: str) -> None:
        result = await db.execute(
            select(RefreshToken).where(
                and_(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False))
            )
        )
        tokens = result.scalars().all()
        for rt in tokens:
            rt.is_revoked = True
        await db.flush()


rbac_service = RbacService()
