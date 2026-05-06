from typing import Optional, List, Tuple, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from fastapi import UploadFile, HTTPException, status
import json

from app.core.common import ApiResponse, PaginatedResponse
from app.core.database import get_db
from app.modules.documents.models import DocumentMaster, StorageProvider, AccessLevel
from app.modules.documents.schemas import (
    DocumentUploadRequest, DocumentResponse, DocumentUpdateRequest,
    DocumentSearchRequest, DocumentListResponse, PresignedUrlResponse,
    BulkDocumentOperation, BulkOperationResponse
)
from app.modules.documents.storage_providers import get_storage_provider


class DocumentService:
    """Service layer for document management operations"""

    def __init__(self):
        self.default_provider = StorageProvider.LOCAL

    async def upload_document(
        self,
        db: AsyncSession,
        file: UploadFile,
        metadata: DocumentUploadRequest,
        uploaded_by: Optional[str] = None
    ) -> DocumentResponse:
        """Upload a document and store metadata"""
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        if file.size and file.size > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 50MB limit"
            )

        try:
            # Get storage provider
            storage = get_storage_provider(metadata.provider_type.value)
            
            # Upload file to storage
            file_key, public_url = await storage.upload(
                file_data=file.file,
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream"
            )
            
            # Create document record
            document = DocumentMaster(
                original_name=file.filename,
                mime_type=file.content_type or "application/octet-stream",
                size_bytes=file.size or 0,
                provider_type=metadata.provider_type,
                access_level=metadata.access_level,
                file_key=file_key,
                file_url=public_url,
                uploaded_by=uploaded_by,
                description=metadata.description,
                tags=metadata.tags
            )
            
            db.add(document)
            await db.commit()
            await db.refresh(document)
            
            return DocumentResponse.model_validate(document)
            
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload document: {str(e)}"
            )

    async def get_document_by_uuid(
        self,
        db: AsyncSession,
        document_uuid: str,
        user_uuid: Optional[str] = None
    ) -> DocumentResponse:
        """Get document metadata by UUID"""
        
        result = await db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.uuid == document_uuid,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check access permissions for protected documents
        if document.access_level == AccessLevel.PROTECTED:
            if not user_uuid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required for protected documents"
                )
            # In a real implementation, you'd check if user has access to this document
            # For now, any authenticated user can access protected documents
        
        return DocumentResponse.model_validate(document)

    async def download_document(
        self,
        db: AsyncSession,
        document_uuid: str,
        user_uuid: Optional[str] = None
    ) -> Tuple[BinaryIO, str, str]:
        """Download document content"""
        
        # Get document metadata
        document = await self.get_document_by_uuid(db, document_uuid, user_uuid)
        
        # Get storage provider
        storage = get_storage_provider(document.provider_type.value)
        
        # Download file
        try:
            file_content = await storage.download(document.file_key)
            
            # Update last accessed timestamp
            await db.execute(
                select(DocumentMaster).where(DocumentMaster.uuid == document_uuid)
            )
            document_doc = (await db.execute(
                select(DocumentMaster).where(DocumentMaster.uuid == document_uuid)
            )).scalar_one()
            document_doc.last_accessed_at = func.now()
            await db.commit()
            
            return file_content, document.original_name, document.mime_type
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to download document: {str(e)}"
            )

    async def generate_presigned_url(
        self,
        db: AsyncSession,
        document_uuid: str,
        expiration_minutes: int = 15,
        user_uuid: Optional[str] = None
    ) -> PresignedUrlResponse:
        """Generate presigned URL for document access"""
        
        # Get document metadata
        document = await self.get_document_by_uuid(db, document_uuid, user_uuid)
        
        # For OPEN documents, return the public URL directly
        if document.access_level == AccessLevel.OPEN and document.file_url:
            return PresignedUrlResponse(
                url=document.file_url,
                expires_in_minutes=0,  # Public URL doesn't expire
                file_name=document.original_name
            )
        
        # For PROTECTED documents, generate presigned URL
        storage = get_storage_provider(document.provider_type.value)
        
        try:
            presigned_url = await storage.generate_presigned_url(
                document.file_key, expiration_minutes
            )
            
            return PresignedUrlResponse(
                url=presigned_url,
                expires_in_minutes=expiration_minutes,
                file_name=document.original_name
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate presigned URL: {str(e)}"
            )

    async def update_document(
        self,
        db: AsyncSession,
        document_uuid: str,
        update_data: DocumentUpdateRequest,
        user_uuid: Optional[str] = None
    ) -> DocumentResponse:
        """Update document metadata"""
        
        # Get document
        result = await db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.uuid == document_uuid,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check permissions (only uploader or admin can update)
        if user_uuid and document.uploaded_by != user_uuid:
            # In a real implementation, check for admin permissions
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this document"
            )
        
        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(document, field, value)
        
        await db.commit()
        await db.refresh(document)
        
        return DocumentResponse.model_validate(document)

    async def delete_document(
        self,
        db: AsyncSession,
        document_uuid: str,
        user_uuid: Optional[str] = None
    ) -> bool:
        """Soft delete a document"""
        
        # Get document
        result = await db.execute(
            select(DocumentMaster).where(
                and_(
                    DocumentMaster.uuid == document_uuid,
                    DocumentMaster.is_active == True,
                    DocumentMaster.is_deleted == False
                )
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check permissions
        if user_uuid and document.uploaded_by != user_uuid:
            # In a real implementation, check for admin permissions
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this document"
            )
        
        # Soft delete
        document.is_deleted = True
        document.is_active = False
        
        await db.commit()
        
        # Optionally delete from storage after a grace period
        # For now, just soft delete
        
        return True

    async def search_documents(
        self,
        db: AsyncSession,
        search_params: DocumentSearchRequest,
        user_uuid: Optional[str] = None
    ) -> DocumentListResponse:
        """Search documents with filters"""
        
        # Build query
        query = select(DocumentMaster).where(
            and_(
                DocumentMaster.is_active == True,
                DocumentMaster.is_deleted == False
            )
        )
        
        # Apply filters
        if search_params.query:
            query = query.where(
                or_(
                    DocumentMaster.original_name.ilike(f"%{search_params.query}%"),
                    DocumentMaster.description.ilike(f"%{search_params.query}%")
                )
            )
        
        if search_params.mime_type:
            query = query.where(DocumentMaster.mime_type == search_params.mime_type)
        
        if search_params.access_level:
            query = query.where(DocumentMaster.access_level == search_params.access_level)
        
        if search_params.provider_type:
            query = query.where(DocumentMaster.provider_type == search_params.provider_type)
        
        if search_params.uploaded_by:
            query = query.where(DocumentMaster.uploaded_by == search_params.uploaded_by)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (search_params.page - 1) * search_params.size
        query = query.offset(offset).limit(search_params.size)
        
        # Execute query
        result = await db.execute(query)
        documents = result.scalars().all()
        
        return DocumentListResponse(
            documents=[DocumentResponse.model_validate(doc) for doc in documents],
            total=total,
            page=search_params.page,
            size=search_params.size
        )

    async def bulk_delete_documents(
        self,
        db: AsyncSession,
        bulk_request: BulkDocumentOperation,
        user_uuid: Optional[str] = None
    ) -> BulkOperationResponse:
        """Bulk delete documents"""
        
        successful = []
        failed = []
        
        for doc_uuid in bulk_request.document_uuids:
            try:
                await self.delete_document(db, doc_uuid, user_uuid)
                successful.append(doc_uuid)
            except Exception as e:
                failed.append({"uuid": doc_uuid, "error": str(e)})
        
        return BulkOperationResponse(successful=successful, failed=failed)


# Singleton instance
document_service = DocumentService()
