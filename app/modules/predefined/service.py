import math
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status

from app.modules.predefined.models import PredefinedMaster
from app.modules.predefined.schemas import (
    PredefinedMasterCreateRequest,
    PredefinedMasterUpdateRequest,
)


class PredefinedService:

    async def get_all(
        self,
        db: AsyncSession,
        entity_type: Optional[str] = None,
        name: Optional[str] = None,
        code: Optional[str] = None,
        parent_uuid: Optional[str] = None,
        page: int = 0,
        size: int = 20,
    ) -> tuple[list[PredefinedMaster], int]:
        query = select(PredefinedMaster).where(PredefinedMaster.is_active.is_(True))

        if entity_type:
            query = query.where(PredefinedMaster.entity_type == entity_type)
        if name:
            query = query.where(PredefinedMaster.name.ilike(f"%{name}%"))
        if code:
            query = query.where(PredefinedMaster.code.ilike(f"%{code}%"))
        if parent_uuid:
            query = query.where(PredefinedMaster.parent_uuid == parent_uuid)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(
            PredefinedMaster.id.desc(), PredefinedMaster.entity_type, PredefinedMaster.sort_order
        ).offset(page * size).limit(size)

        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_uuid(
        self, db: AsyncSession, record_uuid: str
    ) -> Optional[PredefinedMaster]:
        result = await db.execute(
            select(PredefinedMaster).where(PredefinedMaster.uuid == record_uuid)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, db: AsyncSession, record_id: int
    ) -> Optional[PredefinedMaster]:
        result = await db.execute(
            select(PredefinedMaster).where(PredefinedMaster.id == record_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, payload: PredefinedMasterCreateRequest
    ) -> PredefinedMaster:
        record = PredefinedMaster(**payload.model_dump())
        db.add(record)
        await db.flush()
        return record

    async def update(
        self,
        db: AsyncSession,
        record_uuid: str,
        payload: PredefinedMasterUpdateRequest,
    ) -> Optional[PredefinedMaster]:
        record = await self.get_by_uuid(db, record_uuid)
        if not record:
            return None
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        await db.flush()
        return record

    async def delete(self, db: AsyncSession, record_uuid: str) -> bool:
        """
        Soft deletion by setting is_active = False.
        Mirrors Java soft delete pattern for master data.
        """
        record = await self.get_by_uuid(db, record_uuid)
        if not record:
            return False
        record.is_active = False
        await db.flush()
        return True


predefined_service = PredefinedService()
