from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.modules.users.models import UserLogin
from app.modules.rbac.models import RoleMaster


class UserRepository:
    """Repository pattern for User database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_data: dict) -> UserLogin:
        """Create a new user"""
        user = UserLogin(**user_data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_user_by_uuid(self, user_uuid: str) -> Optional[UserLogin]:
        """Get user by UUID"""
        result = await self.db.execute(
            select(UserLogin)
            .options(selectinload(UserLogin.role_master))
            .where(UserLogin.uuid == user_uuid)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[UserLogin]:
        """Get user by email"""
        result = await self.db.execute(
            select(UserLogin)
            .options(selectinload(UserLogin.role_master))
            .where(UserLogin.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[UserLogin]:
        """Get user by username"""
        result = await self.db.execute(
            select(UserLogin)
            .options(selectinload(UserLogin.role_master))
            .where(UserLogin.username == username)
        )
        return result.scalar_one_or_none()

    async def get_user_by_phone(self, phone_number: str) -> Optional[UserLogin]:
        """Get user by phone number"""
        result = await self.db.execute(
            select(UserLogin)
            .options(selectinload(UserLogin.role_master))
            .where(UserLogin.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def update_user(self, user_uuid: str, update_data: dict) -> Optional[UserLogin]:
        """Update user by UUID"""
        user = await self.get_user_by_uuid(user_uuid)
        if not user:
            return None

        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_user(self, user_uuid: str) -> bool:
        """Soft delete user by UUID"""
        user = await self.get_user_by_uuid(user_uuid)
        if not user:
            return False

        user.is_active = False
        await self.db.commit()
        return True

    async def search_users(
        self,
        query: Optional[str] = None,
        is_active: Optional[bool] = None,
        role_uuid: Optional[str] = None,
        provider: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> tuple[List[UserLogin], int]:
        """Search users with filters"""
        
        # Build query
        db_query = select(UserLogin).options(selectinload(UserLogin.role_master))

        # Apply filters
        if query:
            db_query = db_query.where(
                or_(
                    UserLogin.username.ilike(f"%{query}%"),
                    UserLogin.email.ilike(f"%{query}%"),
                    UserLogin.name.ilike(f"%{query}%")
                )
            )

        if is_active is not None:
            db_query = db_query.where(UserLogin.is_active == is_active)

        if role_uuid:
            db_query = db_query.where(UserLogin.role_uuid == role_uuid)

        if provider:
            db_query = db_query.where(UserLogin.provider == provider)

        # Get total count
        count_query = select(func.count()).select_from(db_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * size
        db_query = db_query.offset(offset).limit(size)

        # Execute query
        result = await self.db.execute(db_query)
        users = result.scalars().all()

        return list(users), total

    async def get_users_by_role(self, role_uuid: str) -> List[UserLogin]:
        """Get all users with a specific role"""
        result = await self.db.execute(
            select(UserLogin)
            .options(selectinload(UserLogin.role_master))
            .where(UserLogin.role_uuid == role_uuid)
        )
        return list(result.scalars().all())

    async def email_exists(self, email: str) -> bool:
        """Check if email already exists"""
        result = await self.db.execute(
            select(func.count()).select_from(UserLogin).where(UserLogin.email == email)
        )
        return result.scalar() > 0

    async def username_exists(self, username: str) -> bool:
        """Check if username already exists"""
        result = await self.db.execute(
            select(func.count()).select_from(UserLogin).where(UserLogin.username == username)
        )
        return result.scalar() > 0

    async def phone_exists(self, phone_number: str) -> bool:
        """Check if phone number already exists"""
        result = await self.db.execute(
            select(func.count()).select_from(UserLogin).where(UserLogin.phone_number == phone_number)
        )
        return result.scalar() > 0

    async def get_active_users_count(self) -> int:
        """Get count of active users"""
        result = await self.db.execute(
            select(func.count()).select_from(UserLogin).where(UserLogin.is_active == True)
        )
        return result.scalar()

    async def get_users_by_provider(self, provider: str) -> List[UserLogin]:
        """Get all users from a specific provider"""
        result = await self.db.execute(
            select(UserLogin)
            .options(selectinload(UserLogin.role_master))
            .where(UserLogin.provider == provider)
        )
        return list(result.scalars().all())
