from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, generate_uuid


class AuditLog(Base):
    """
    Tracks sensitive user and system actions (RBAC changes, profile updates, logins, etc).
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    
    # Who did it
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # What did they do
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # Example: LOGIN, CREATE_USER
    module: Mapped[str] = mapped_column(String(50), nullable=False)   # Example: AUTH, RBAC
    
    # Request metadata
    method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Details
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status_code: Mapped[int] = mapped_column(nullable=False, default=200)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
