from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import ApiResponse, ApiRouter
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.middlewares import limiter
from app.modules.documents.params import API_PREFIX
from app.modules.documents.schemas import (
    DocumentUploadRequest, DocumentResponse, DocumentUpdateRequest,
    DocumentSearchRequest, DocumentListResponse, PresignedUrlResponse,
    BulkDocumentOperation, BulkOperationResponse
)
from app.modules.documents.service import document_service


router = ApiRouter(prefix=API_PREFIX, tags=["Document Management"])


# ── Upload Document ────────────────────────────────────────────────────────
@router.post("/upload", response_model=ApiResponse[DocumentResponse])
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    tags: Optional[str] = None,
    access_level: str = "PROTECTED",
    provider_type: Optional[str] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Upload a document with metadata"""
    
    # Use provider from request or fall back to config
    from app.core.config import settings
    provider_type = provider_type or settings.DEFAULT_STORAGE_PROVIDER
    
    # Convert string enums to proper enum types
    from app.modules.documents.models import AccessLevel, StorageProvider
    
    try:
        access_level_enum = AccessLevel(access_level.upper())
        provider_type_enum = StorageProvider(provider_type.upper())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid enum value: {str(e)}"
        )
    
    metadata = DocumentUploadRequest(
        description=description,
        tags=tags,
        access_level=access_level_enum,
        provider_type=provider_type_enum
    )
    
    document = await document_service.upload_document(
        db, file, metadata, getattr(current_user, "uuid", None) if current_user else None
    )
    
    return ApiResponse.success(
        message="Document uploaded successfully",
        data=document.model_dump()
    )


# ── Get Document Metadata ───────────────────────────────────────────────────
@router.get("/{document_uuid}", response_model=ApiResponse[DocumentResponse])
async def get_document(
    document_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Get document metadata by UUID"""
    
    document = await document_service.get_document_by_uuid(
        db, document_uuid, getattr(current_user, "uuid", None) if current_user else None
    )
    
    return ApiResponse.success(
        message="Document retrieved successfully",
        data=document.model_dump()
    )


# ── Download Document ───────────────────────────────────────────────────────
@router.get("/{document_uuid}/download")
async def download_document(
    document_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Download document content"""
    
    try:
        file_content, filename, content_type = await document_service.download_document(
            db, document_uuid, getattr(current_user, "uuid", None) if current_user else None
        )
        
        return StreamingResponse(
            file_content,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ── Generate Presigned URL ─────────────────────────────────────────────────
@router.get("/{document_uuid}/presigned-url", response_model=ApiResponse[PresignedUrlResponse])
async def generate_presigned_url(
    document_uuid: str,
    expiration_minutes: int = Query(15, ge=1, le=60, description="URL expiration in minutes"),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Generate presigned URL for document access"""
    
    presigned_url = await document_service.generate_presigned_url(
        db, document_uuid, expiration_minutes, getattr(current_user, "uuid", None) if current_user else None
    )
    
    return ApiResponse.success(
        message="Presigned URL generated successfully",
        data=presigned_url.model_dump()
    )


# ── Update Document Metadata ────────────────────────────────────────────────
@router.put("/{document_uuid}", response_model=ApiResponse[DocumentResponse])
async def update_document(
    document_uuid: str,
    update_data: DocumentUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Update document metadata"""
    
    document = await document_service.update_document(
        db, document_uuid, update_data, getattr(current_user, "uuid", None) if current_user else None
    )
    
    return ApiResponse.success(
        message="Document updated successfully",
        data=document.model_dump()
    )


# ── Delete Document ─────────────────────────────────────────────────────────
@router.delete("/{document_uuid}", response_model=ApiResponse[bool])
async def delete_document(
    document_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Delete a document (soft delete)"""
    
    success = await document_service.delete_document(
        db, document_uuid, getattr(current_user, "uuid", None) if current_user else None
    )
    
    return ApiResponse.success(
        message="Document deleted successfully",
        data=success
    )


# ── Search Documents ────────────────────────────────────────────────────────
@router.get("/", response_model=ApiResponse[DocumentListResponse])
async def search_documents(
    query: Optional[str] = Query(None, description="Search query"),
    mime_type: Optional[str] = Query(None, description="Filter by MIME type"),
    access_level: Optional[str] = Query(None, description="Filter by access level"),
    provider_type: Optional[str] = Query(None, description="Filter by storage provider"),
    tags: Optional[str] = Query(None, description="Filter by tags"),
    uploaded_by: Optional[str] = Query(None, description="Filter by uploader UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Search documents with filters"""
    
    # Convert string enums to proper enum types
    from app.modules.documents.models import AccessLevel, StorageProvider
    
    search_params = DocumentSearchRequest(
        query=query,
        mime_type=mime_type,
        access_level=AccessLevel(access_level.upper()) if access_level else None,
        provider_type=StorageProvider(provider_type.upper()) if provider_type else None,
        tags=tags,
        uploaded_by=uploaded_by,
        page=page,
        size=size
    )
    
    result = await document_service.search_documents(
        db, search_params, getattr(current_user, "uuid", None) if current_user else None
    )
    
    return ApiResponse.success(
        message="Documents retrieved successfully",
        data=result.model_dump()
    )


# ── Bulk Delete Documents ───────────────────────────────────────────────────
@router.post("/bulk-delete", response_model=ApiResponse[BulkOperationResponse])
@limiter.limit("5/minute")
async def bulk_delete_documents(
    request: Request,
    bulk_request: BulkDocumentOperation,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[object, Depends(get_current_user)] = None
):
    """Bulk delete multiple documents"""
    
    result = await document_service.bulk_delete_documents(
        db, bulk_request, getattr(current_user, "uuid", None) if current_user else None
    )
    
    return ApiResponse.success(
        message="Bulk delete operation completed",
        data=result.model_dump()
    )
