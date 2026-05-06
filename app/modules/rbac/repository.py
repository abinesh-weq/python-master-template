from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.modules.rbac.models import RoleMaster, ModuleMaster, RoleModuleMapping, AccessControlMaster, RefreshToken


class RoleRepository:
    """Repository pattern for Role database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_role(self, role_data: dict) -> RoleMaster:
        """Create a new role"""
        role = RoleMaster(**role_data)
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def get_role_by_uuid(self, role_uuid: str) -> Optional[RoleMaster]:
        """Get role by UUID"""
        result = await self.db.execute(
            select(RoleMaster).where(RoleMaster.uuid == role_uuid)
        )
        return result.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Optional[RoleMaster]:
        """Get role by name"""
        result = await self.db.execute(
            select(RoleMaster).where(RoleMaster.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all_roles(self, active_only: bool = True) -> List[RoleMaster]:
        """Get all roles"""
        query = select(RoleMaster)
        if active_only:
            query = query.where(RoleMaster.is_active == True)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_role(self, role_uuid: str, update_data: dict) -> Optional[RoleMaster]:
        """Update role by UUID"""
        role = await self.get_role_by_uuid(role_uuid)
        if not role:
            return None

        for field, value in update_data.items():
            if hasattr(role, field):
                setattr(role, field, value)

        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def delete_role(self, role_uuid: str) -> bool:
        """Soft delete role by UUID"""
        role = await self.get_role_by_uuid(role_uuid)
        if not role:
            return False

        role.is_active = False
        await self.db.commit()
        return True


class ModuleRepository:
    """Repository pattern for Module database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_module(self, module_data: dict) -> ModuleMaster:
        """Create a new module"""
        module = ModuleMaster(**module_data)
        self.db.add(module)
        await self.db.commit()
        await self.db.refresh(module)
        return module

    async def get_module_by_uuid(self, module_uuid: str) -> Optional[ModuleMaster]:
        """Get module by UUID"""
        result = await self.db.execute(
            select(ModuleMaster).where(ModuleMaster.uuid == module_uuid)
        )
        return result.scalar_one_or_none()

    async def get_module_by_code(self, module_code: str) -> Optional[ModuleMaster]:
        """Get module by code"""
        result = await self.db.execute(
            select(ModuleMaster).where(ModuleMaster.module_code == module_code)
        )
        return result.scalar_one_or_none()

    async def get_all_modules(self, active_only: bool = True) -> List[ModuleMaster]:
        """Get all modules"""
        query = select(ModuleMaster)
        if active_only:
            query = query.where(ModuleMaster.is_active == True)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_module(self, module_uuid: str, update_data: dict) -> Optional[ModuleMaster]:
        """Update module by UUID"""
        module = await self.get_module_by_uuid(module_uuid)
        if not module:
            return None

        for field, value in update_data.items():
            if hasattr(module, field):
                setattr(module, field, value)

        await self.db.commit()
        await self.db.refresh(module)
        return module


class RoleModuleRepository:
    """Repository pattern for Role-Module mapping operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_role_module_mapping(self, mapping_data: dict) -> RoleModuleMapping:
        """Create a new role-module mapping"""
        mapping = RoleModuleMapping(**mapping_data)
        self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping

    async def get_role_module_mapping(self, role_uuid: str, module_uuid: str) -> Optional[RoleModuleMapping]:
        """Get role-module mapping"""
        result = await self.db.execute(
            select(RoleModuleMapping).where(
                and_(
                    RoleModuleMapping.role_uuid == role_uuid,
                    RoleModuleMapping.module_uuid == module_uuid
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_role_permissions(self, role_uuid: str) -> List[RoleModuleMapping]:
        """Get all module permissions for a role"""
        result = await self.db.execute(
            select(RoleModuleMapping)
            .options(selectinload(RoleModuleMapping.module_master))
            .where(RoleModuleMapping.role_uuid == role_uuid)
        )
        return list(result.scalars().all())

    async def get_module_roles(self, module_uuid: str) -> List[RoleModuleMapping]:
        """Get all roles that have permissions for a module"""
        result = await self.db.execute(
            select(RoleModuleMapping)
            .options(selectinload(RoleModuleMapping.role_master))
            .where(RoleModuleMapping.module_uuid == module_uuid)
        )
        return list(result.scalars().all())

    async def update_role_module_mapping(self, role_uuid: str, module_uuid: str, update_data: dict) -> Optional[RoleModuleMapping]:
        """Update role-module mapping"""
        mapping = await self.get_role_module_mapping(role_uuid, module_uuid)
        if not mapping:
            return None

        for field, value in update_data.items():
            if hasattr(mapping, field):
                setattr(mapping, field, value)

        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping

    async def delete_role_module_mapping(self, role_uuid: str, module_uuid: str) -> bool:
        """Delete role-module mapping"""
        mapping = await self.get_role_module_mapping(role_uuid, module_uuid)
        if not mapping:
            return False

        await self.db.delete(mapping)
        await self.db.commit()
        return True


class AccessControlRepository:
    """Repository pattern for Access Control operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_access_control(self, access_data: dict) -> AccessControlMaster:
        """Create a new access control entry"""
        access = AccessControlMaster(**access_data)
        self.db.add(access)
        await self.db.commit()
        await self.db.refresh(access)
        return access

    async def get_user_access_control(self, user_uuid: str, module_uuid: str) -> Optional[AccessControlMaster]:
        """Get user's access control for a module"""
        result = await self.db.execute(
            select(AccessControlMaster).where(
                and_(
                    AccessControlMaster.user_uuid == user_uuid,
                    AccessControlMaster.module_uuid == module_uuid
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_permissions(self, user_uuid: str) -> List[AccessControlMaster]:
        """Get all module permissions for a user"""
        result = await self.db.execute(
            select(AccessControlMaster)
            .options(selectinload(AccessControlMaster.module_master))
            .where(AccessControlMaster.user_uuid == user_uuid)
        )
        return list(result.scalars().all())

    async def update_user_access_control(self, user_uuid: str, module_uuid: str, update_data: dict) -> Optional[AccessControlMaster]:
        """Update user's access control for a module"""
        access = await self.get_user_access_control(user_uuid, module_uuid)
        if not access:
            # Create new access control if it doesn't exist
            access_data = {"user_uuid": user_uuid, "module_uuid": module_uuid, **update_data}
            return await self.create_access_control(access_data)

        for field, value in update_data.items():
            if hasattr(access, field):
                setattr(access, field, value)

        await self.db.commit()
        await self.db.refresh(access)
        return access

    async def delete_user_access_control(self, user_uuid: str, module_uuid: str) -> bool:
        """Delete user's access control for a module"""
        access = await self.get_user_access_control(user_uuid, module_uuid)
        if not access:
            return False

        await self.db.delete(access)
        await self.db.commit()
        return True

    async def clone_role_permissions_to_user(self, user_uuid: str, role_uuid: str) -> List[AccessControlMaster]:
        """Clone role permissions to user access control"""
        # Get role permissions
        role_repo = RoleModuleRepository(self.db)
        role_permissions = await role_repo.get_role_permissions(role_uuid)
        
        created_access_controls = []
        
        for role_perm in role_permissions:
            # Check if user already has access control for this module
            existing = await self.get_user_access_control(user_uuid, role_perm.module_uuid)
            
            if not existing:
                # Create new access control based on role permissions
                access_data = {
                    "user_uuid": user_uuid,
                    "module_uuid": role_perm.module_uuid,
                    "can_read": role_perm.can_read,
                    "can_write": role_perm.can_write,
                    "can_update": role_perm.can_update,
                    "can_delete": role_perm.can_delete,
                    "can_export": role_perm.can_export
                }
                access_control = await self.create_access_control(access_data)
                created_access_controls.append(access_control)
        
        return created_access_controls


class RefreshTokenRepository:
    """Repository pattern for Refresh Token operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_refresh_token(self, token_data: dict) -> RefreshToken:
        """Create a new refresh token"""
        token = RefreshToken(**token_data)
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_refresh_token(self, token: str) -> Optional[RefreshToken]:
        """Get refresh token by token string"""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()

    async def get_user_refresh_tokens(self, user_uuid: str) -> List[RefreshToken]:
        """Get all refresh tokens for a user"""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.user_uuid == user_uuid)
        )
        return list(result.scalars().all())

    async def revoke_refresh_token(self, token: str) -> bool:
        """Revoke a refresh token"""
        refresh_token = await self.get_refresh_token(token)
        if not refresh_token:
            return False

        refresh_token.is_revoked = True
        await self.db.commit()
        return True

    async def revoke_all_user_tokens(self, user_uuid: str) -> bool:
        """Revoke all refresh tokens for a user"""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.user_uuid == user_uuid)
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            token.is_revoked = True
        
        await self.db.commit()
        return True

    async def delete_expired_tokens(self) -> int:
        """Delete expired refresh tokens"""
        from datetime import datetime, timezone
        
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.expires_at < datetime.now(timezone.utc).isoformat())
        )
        expired_tokens = result.scalars().all()
        
        count = 0
        for token in expired_tokens:
            await self.db.delete(token)
            count += 1
        
        await self.db.commit()
        return count
