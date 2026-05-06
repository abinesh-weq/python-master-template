from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.modules.documents.models import DocumentMaster, StorageProvider, AccessLevel


class DocumentRepository:
    """Repository pattern for Document database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_document(self, document_data: dict) -> DocumentMaster:
        """Create a new document record"""
        document = DocumentMaster(**document_data)
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def get_document_by_uuid(self, document_uuid: str) -> Optional[DocumentMaster]:
        """Get document by UUID"""
        result = await self.db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.uuid == document_uuid,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_document_by_file_key(self, file_key: str) -> Optional[DocumentMaster]:
        """Get document by file key"""
        result = await self.db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.file_key == file_key,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_document(self, document_uuid: str, update_data: dict) -> Optional[DocumentMaster]:
        """Update document by UUID"""
        document = await self.get_document_by_uuid(document_uuid)
        if not document:
            return None

        for field, value in update_data.items():
            if hasattr(document, field):
                setattr(document, field, value)

        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def soft_delete_document(self, document_uuid: str) -> bool:
        """Soft delete document by UUID"""
        document = await self.get_document_by_uuid(document_uuid)
        if not document:
            return False

        document.is_deleted = True
        document.is_active = False
        await self.db.commit()
        return True

    async def hard_delete_document(self, document_uuid: str) -> bool:
        """Hard delete document by UUID"""
        document = await self.get_document_by_uuid(document_uuid)
        if not document:
            return False

        await self.db.delete(document)
        await self.db.commit()
        return True

    async def search_documents(
        self,
        query: Optional[str] = None,
        mime_type: Optional[str] = None,
        access_level: Optional[AccessLevel] = None,
        provider_type: Optional[StorageProvider] = None,
        tags: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[DocumentMaster], int]:
        """Search documents with filters"""
        
        # Build query
        db_query = select(DocumentMaster).where(
            and_(
                DocumentMaster.is_active == True,
                DocumentMaster.is_deleted == False
            )
        )

        # Apply filters
        if query:
            db_query = db_query.where(
                or_(
                    DocumentMaster.original_name.ilike(f"%{query}%"),
                    DocumentMaster.description.ilike(f"%{query}%")
                )
            )

        if mime_type:
            db_query = db_query.where(DocumentMaster.mime_type == mime_type)

        if access_level:
            db_query = db_query.where(DocumentMaster.access_level == access_level)

        if provider_type:
            db_query = db_query.where(DocumentMaster.provider_type == provider_type)

        if tags:
            db_query = db_query.where(DocumentMaster.tags.ilike(f"%{tags}%"))

        if uploaded_by:
            db_query = db_query.where(DocumentMaster.uploaded_by == uploaded_by)

        # Get total count
        count_query = select(func.count()).select_from(db_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * size
        db_query = db_query.offset(offset).limit(size)

        # Execute query
        result = await self.db.execute(db_query)
        documents = result.scalars().all()

        return list(documents), total

    async def get_documents_by_uploader(self, uploaded_by: str, page: int = 1, size: int = 20) -> Tuple[List[DocumentMaster], int]:
        """Get documents uploaded by a specific user"""
        db_query = select(DocumentMaster).where(
            and_(
                DocumentMaster.uploaded_by == uploaded_by,
                DocumentMaster.is_active == True,
                DocumentMaster.is_deleted == False
            )
        )

        # Get total count
        count_query = select(func.count()).select_from(db_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * size
        db_query = db_query.offset(offset).limit(size)

        # Execute query
        result = await self.db.execute(db_query)
        documents = result.scalars().all()

        return list(documents), total

    async def get_documents_by_access_level(self, access_level: AccessLevel) -> List[DocumentMaster]:
        """Get all documents with specific access level"""
        result = await self.db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.access_level == access_level,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        return list(result.scalars().all())

    async def get_documents_by_provider(self, provider_type: StorageProvider) -> List[DocumentMaster]:
        """Get all documents from a specific storage provider"""
        result = await self.db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.provider_type == provider_type,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        return list(result.scalars().all())

    async def get_documents_by_mime_type(self, mime_type: str) -> List[DocumentMaster]:
        """Get all documents with specific MIME type"""
        result = await self.db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.mime_type == mime_type,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        return list(result.scalars().all())

    async def update_last_accessed(self, document_uuid: str) -> bool:
        """Update last accessed timestamp for a document"""
        document = await self.get_document_by_uuid(document_uuid)
        if not document:
            return False

        from datetime import datetime, timezone
        document.last_accessed_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True

    async def get_storage_usage_stats(self, provider_type: Optional[StorageProvider] = None) -> dict:
        """Get storage usage statistics"""
        query = select(
            func.count(DocumentMaster.id).label('count'),
            func.sum(DocumentMaster.size_bytes).label('total_size')
        ).where(
            and_(
                DocumentMaster.is_active == True,
                DocumentMaster.is_deleted == False
            )
        )

        if provider_type:
            query = query.where(DocumentMaster.provider_type == provider_type)

        result = await self.db.execute(query)
        stats = result.first()

        return {
            'count': stats.count or 0,
            'total_size_bytes': stats.total_size or 0,
            'total_size_mb': round((stats.total_size or 0) / (1024 * 1024), 2)
        }

    async def get_documents_by_size_range(
        self,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[DocumentMaster], int]:
        """Get documents within size range"""
        db_query = select(DocumentMaster).where(
            and_(
                DocumentMaster.is_active == True,
                DocumentMaster.is_deleted == False
            )
        )

        if min_size is not None:
            db_query = db_query.where(DocumentMaster.size_bytes >= min_size)

        if max_size is not None:
            db_query = db_query.where(DocumentMaster.size_bytes <= max_size)

        # Get total count
        count_query = select(func.count()).select_from(db_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * size
        db_query = db_query.offset(offset).limit(size)

        # Execute query
        result = await self.db.execute(db_query)
        documents = result.scalars().all()

        return list(documents), total

    async def bulk_soft_delete_documents(self, document_uuids: List[str]) -> Tuple[int, List[str]]:
        """Bulk soft delete documents"""
        successful = []
        failed = []

        for doc_uuid in document_uuids:
            try:
                if await self.soft_delete_document(doc_uuid):
                    successful.append(doc_uuid)
                else:
                    failed.append(doc_uuid)
            except Exception:
                failed.append(doc_uuid)

        return len(successful), failed

    async def get_duplicate_documents(self, original_name: str) -> List[DocumentMaster]:
        """Get documents with the same original name"""
        result = await self.db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.original_name == original_name,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        return list(result.scalars().all())
