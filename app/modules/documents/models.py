from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Boolean, String, DateTime, Integer, Enum as SQLEnum
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.common_models.base_model import Base


class StorageProvider(str, Enum):
    LOCAL = "LOCAL"
    S3 = "S3"
    GCS = "GCS"


class AccessLevel(str, Enum):
    OPEN = "OPEN"
    PROTECTED = "PROTECTED"


class DocumentMaster(Base):
    """
    Mirrors Java DocumentMaster entity / document_master table.
    Central document storage and retrieval metadata.
    """

    __tablename__ = "document_master"

    # Document metadata
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Storage configuration
    provider_type: Mapped[StorageProvider] = mapped_column(
        SQLEnum(StorageProvider), nullable=False, default=StorageProvider.LOCAL
    )
    access_level: Mapped[AccessLevel] = mapped_column(
        SQLEnum(AccessLevel), nullable=False, default=AccessLevel.PROTECTED
    )
    
    # Storage identifiers
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)  # Path or S3 key
    file_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Public URL if OPEN
    
    # User association
    uploaded_by: Mapped[Optional[str]] = mapped_column(
        String(36), sa.ForeignKey("user_login.uuid", ondelete="SET NULL"), nullable=True
    )
    
    # Document state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Standard Timestamps (in addition to Base audit fields)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    
    # Additional metadata
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # JSON array of tags
