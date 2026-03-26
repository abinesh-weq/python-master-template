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
        result = await db.execute(select(RoleMaster).where(RoleMaster.is_active.is_(True)).order_by(RoleMaster.id.desc()))
        return list(result.scalars().all())

    async def get_role_by_uuid(self, db: AsyncSession, role_uuid: str) -> Optional[RoleMaster]:
        result = await db.execute(select(RoleMaster).where(RoleMaster.uuid == role_uuid))
        return result.scalar_one_or_none()

    async def get_role_by_id(self, db: AsyncSession, role_id: int) -> Optional[RoleMaster]:
        result = await db.execute(select(RoleMaster).where(RoleMaster.id == role_id))
        return result.scalar_one_or_none()

    async def get_role_by_name(self, db: AsyncSession, name: str) -> Optional[RoleMaster]:
        result = await db.execute(select(RoleMaster).where(RoleMaster.name == name))
        return result.scalar_one_or_none()

    async def delete_role(self, db: AsyncSession, role_uuid: str) -> bool:
        role = await self.get_role_by_uuid(db, role_uuid)
        if not role:
            return False
        role.is_active = False
        await db.flush()
        return True

    # ── Modules ───────────────────────────────────────────────────────────────

    async def get_all_modules(self, db: AsyncSession) -> list[ModuleMaster]:
        result = await db.execute(select(ModuleMaster).where(ModuleMaster.is_active.is_(True)).order_by(ModuleMaster.created_at.desc()))
        return list(result.scalars().all())

    async def get_module_by_code(self, db: AsyncSession, code: str) -> Optional[ModuleMaster]:
        result = await db.execute(
            select(ModuleMaster).where(ModuleMaster.module_code == code)
        )
        return result.scalar_one_or_none()

    # ── Role-Module Mappings ───────────────────────────────────────────────────

    async def get_role_modules(self, db: AsyncSession, role_uuid: str) -> list[RoleModuleMapping]:
        result = await db.execute(
            select(RoleModuleMapping).where(RoleModuleMapping.role_uuid == role_uuid).order_by(RoleModuleMapping.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_role_modules_by_uuid(self, db: AsyncSession, role_uuid: str) -> list[RoleModuleMapping]:
        return await self.get_role_modules(db, role_uuid)

    async def get_module_by_uuid(self, db: AsyncSession, module_uuid: str) -> Optional[ModuleMaster]:
        result = await db.execute(select(ModuleMaster).where(ModuleMaster.uuid == module_uuid))
        return result.scalar_one_or_none()

    async def get_module_by_id(self, db: AsyncSession, module_id: int) -> Optional[ModuleMaster]:
        result = await db.execute(select(ModuleMaster).where(ModuleMaster.id == module_id))
        return result.scalar_one_or_none()

    async def upsert_role_module(
        self, db: AsyncSession, role_uuid: str, module_uuid: str, payload: PermissionToggleRequest
    ) -> RoleModuleMapping:
        """
        Upserts a role-module permission entry.
        """
        result = await db.execute(
            select(RoleModuleMapping).where(
                and_(
                    RoleModuleMapping.role_uuid == role_uuid,
                    RoleModuleMapping.module_uuid == module_uuid,
                )
            )
        )
        mapping = result.scalar_one_or_none()

        if not mapping:
            mapping = RoleModuleMapping(role_uuid=role_uuid, module_uuid=module_uuid)
            db.add(mapping)

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(mapping, field, value)

        await db.flush()
        return mapping

    async def upsert_role_module_by_uuids(
        self, db: AsyncSession, role_uuid: str, module_uuid: str, payload: PermissionToggleRequest
    ) -> RoleModuleMapping:
        return await self.upsert_role_module(db, role_uuid, module_uuid, payload)

    async def delete_role_module(
        self, db: AsyncSession, role_uuid: str, module_uuid: str
    ) -> bool:
        result = await db.execute(
            select(RoleModuleMapping).where(
                and_(
                    RoleModuleMapping.role_uuid == role_uuid,
                    RoleModuleMapping.module_uuid == module_uuid,
                )
            )
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            return False
        await db.delete(mapping)
        return True

    async def delete_role_module_by_uuids(
        self, db: AsyncSession, role_uuid: str, module_uuid: str
    ) -> bool:
        return await self.delete_role_module(db, role_uuid, module_uuid)

    # ── User Access Control Overrides ─────────────────────────────────────────

    async def get_user_access(
        self, db: AsyncSession, user_uuid: str, module_uuid: str
    ) -> Optional[AccessControlMaster]:
        result = await db.execute(
            select(AccessControlMaster).where(
                and_(
                    AccessControlMaster.user_uuid == user_uuid,
                    AccessControlMaster.module_uuid == module_uuid,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_access_by_uuids(
        self, db: AsyncSession, user_uuid: str, module_uuid: str
    ) -> Optional[AccessControlMaster]:
        return await self.get_user_access(db, user_uuid, module_uuid)

    async def get_all_user_access(
        self, db: AsyncSession, user_uuid: str
    ) -> list[AccessControlMaster]:
        result = await db.execute(
            select(AccessControlMaster).where(AccessControlMaster.user_uuid == user_uuid).order_by(AccessControlMaster.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all_user_access_by_uuid(
        self, db: AsyncSession, user_uuid: str
    ) -> list[AccessControlMaster]:
        return await self.get_all_user_access(db, user_uuid)

    async def upsert_user_access(
        self,
        db: AsyncSession,
        user_uuid: str,
        module_uuid: str,
        payload: PermissionToggleRequest,
    ) -> AccessControlMaster:
        record = await self.get_user_access(db, user_uuid, module_uuid)

        if not record:
            record = AccessControlMaster(user_uuid=user_uuid, module_uuid=module_uuid)
            db.add(record)

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(record, field, value)

        await db.flush()
        return record

    async def upsert_user_access_by_uuids(
        self,
        db: AsyncSession,
        user_uuid: str,
        module_uuid: str,
        payload: PermissionToggleRequest,
    ) -> AccessControlMaster:
        return await self.upsert_user_access(db, user_uuid, module_uuid, payload)

    async def delete_user_access(
        self, db: AsyncSession, user_uuid: str, module_uuid: str
    ) -> bool:
        record = await self.get_user_access(db, user_uuid, module_uuid)
        if not record:
            return False
        await db.delete(record)
        return True

    async def delete_user_access_by_uuids(
        self, db: AsyncSession, user_uuid: str, module_uuid: str
    ) -> bool:
        return await self.delete_user_access(db, user_uuid, module_uuid)

    # ── Refresh Token Management ──────────────────────────────────────────────

    async def save_refresh_token(
        self, db: AsyncSession, user_uuid: str, token: str, expires_at: str
    ) -> RefreshToken:
        rt = RefreshToken(user_uuid=user_uuid, token=token, expires_at=expires_at)
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

    async def revoke_all_user_tokens(self, db: AsyncSession, user_uuid: str) -> None:
        result = await db.execute(
            select(RefreshToken).where(
                and_(RefreshToken.user_uuid == user_uuid, RefreshToken.is_revoked.is_(False))
            )
        )
        tokens = result.scalars().all()
        for rt in tokens:
            rt.is_revoked = True
        await db.flush()


rbac_service = RbacService()
