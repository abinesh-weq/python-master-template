from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from app.modules.documents.models import StorageProvider, AccessLevel


class DocumentUploadRequest(BaseModel):
    """Request schema for document upload"""
    description: Optional[str] = Field(None, max_length=1000, description="Document description")
    tags: Optional[str] = Field(None, max_length=500, description="JSON array of tags")
    access_level: AccessLevel = Field(AccessLevel.PROTECTED, description="Access level for the document")
    provider_type: StorageProvider = Field(StorageProvider.LOCAL, description="Storage provider type")


class DocumentResponse(BaseModel):
    """Response schema for document metadata"""
    uuid: str
    original_name: str
    mime_type: str
    size_bytes: int
    provider_type: StorageProvider
    access_level: AccessLevel
    file_key: str
    file_url: Optional[str] = None
    uploaded_by: Optional[str] = None
    is_active: bool
    uploaded_at: datetime
    last_accessed_at: Optional[datetime] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Response schema for document list"""
    documents: List[DocumentResponse]
    total: int
    page: int
    size: int


class DocumentUpdateRequest(BaseModel):
    """Request schema for document metadata update"""
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[str] = Field(None, max_length=500)
    access_level: Optional[AccessLevel] = None


class DocumentSearchRequest(BaseModel):
    """Request schema for document search"""
    query: Optional[str] = Field(None, description="Search query for filename/description")
    mime_type: Optional[str] = Field(None, description="Filter by MIME type")
    access_level: Optional[AccessLevel] = Field(None, description="Filter by access level")
    provider_type: Optional[StorageProvider] = Field(None, description="Filter by storage provider")
    tags: Optional[str] = Field(None, description="Filter by tags")
    uploaded_by: Optional[str] = Field(None, description="Filter by uploader UUID")
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")


class PresignedUrlResponse(BaseModel):
    """Response schema for presigned URL"""
    url: str
    expires_in_minutes: int
    file_name: str


class BulkDocumentOperation(BaseModel):
    """Request schema for bulk operations"""
    document_uuids: List[str] = Field(..., min_items=1, max_items=50, description="List of document UUIDs")


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations"""
    successful: List[str]
    failed: List[dict]  # {"uuid": "error_message"}
