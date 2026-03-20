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
        parent_id: Optional[str] = None,
        page: int = 0,
        size: int = 20,
    ) -> tuple[list[PredefinedMaster], int]:
        query = select(PredefinedMaster)

        if entity_type:
            query = query.where(PredefinedMaster.entity_type == entity_type)
        if name:
            query = query.where(PredefinedMaster.name.ilike(f"%{name}%"))
        if code:
            query = query.where(PredefinedMaster.code.ilike(f"%{code}%"))
        if parent_id:
            query = query.where(PredefinedMaster.parent_id == parent_id)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(
            PredefinedMaster.entity_type, PredefinedMaster.sort_order
        ).offset(page * size).limit(size)

        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(
        self, db: AsyncSession, record_id: str
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
        record_id: str,
        payload: PredefinedMasterUpdateRequest,
    ) -> Optional[PredefinedMaster]:
        record = await self.get_by_id(db, record_id)
        if not record:
            return None
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        await db.flush()
        return record

    async def delete(self, db: AsyncSession, record_id: str) -> bool:
        """
        Structural deletion with explicit IntegrityError catch.
        Mirrors Java catch(DataIntegrityViolationException) to block
        deletion of parent nodes that have child foreign key references.
        """
        record = await self.get_by_id(db, record_id)
        if not record:
            return False
        try:
            await db.delete(record)
            await db.flush()
            return True
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot delete this record — it has child records referencing it. "
                    "Remove all child nodes first."
                ),
            )


predefined_service = PredefinedService()
