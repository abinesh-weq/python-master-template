from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.models import UserLogin
from app.modules.users.schemas import UserCreateRequest, UserUpdateRequest


class UserService:

    async def get_by_id(self, db: AsyncSession, user_id: str) -> Optional[UserLogin]:
        result = await db.execute(select(UserLogin).where(UserLogin.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[UserLogin]:
        result = await db.execute(
            select(UserLogin).where(UserLogin.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, db: AsyncSession, phone: str) -> Optional[UserLogin]:
        result = await db.execute(
            select(UserLogin).where(UserLogin.phone_number == phone)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self, db: AsyncSession, payload: UserCreateRequest
    ) -> UserLogin:
        data = payload.model_dump()
        if data.get("password"):
            data["password"] = hash_password(data["password"])
        user = UserLogin(**data)
        db.add(user)
        await db.flush()
        return user

    async def update_user(
        self, db: AsyncSession, user_id: str, payload: UserUpdateRequest
    ) -> Optional[UserLogin]:
        user = await self.get_by_id(db, user_id)
        if not user:
            return None
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await db.flush()
        return user

    async def delete_user(self, db: AsyncSession, user_id: str) -> bool:
        user = await self.get_by_id(db, user_id)
        if not user:
            return False
        await db.delete(user)
        return True

    async def admin_reset_password(
        self, db: AsyncSession, user_id: str, new_password: str
    ) -> Optional[UserLogin]:
        user = await self.get_by_id(db, user_id)
        if not user:
            return None
        user.password = hash_password(new_password)
        await db.flush()
        return user

    async def search_users(
        self,
        db: AsyncSession,
        search: Optional[str] = None,
        role_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 0,
        size: int = 20,
    ) -> tuple[list[UserLogin], int]:
        """Paginated user search with optional filters."""
        query = select(UserLogin)

        if search:
            query = query.where(
                or_(
                    UserLogin.username.ilike(f"%{search}%"),
                    UserLogin.email.ilike(f"%{search}%"),
                    UserLogin.phone_number.ilike(f"%{search}%"),
                )
            )
        if is_active is not None:
            query = query.where(UserLogin.is_active == is_active)

        # Count total before pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        query = query.offset(page * size).limit(size)
        result = await db.execute(query)
        users = list(result.scalars().all())
        return users, total


user_service = UserService()
