from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, String, Text, Integer
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """
    Tracks sensitive user and system actions (RBAC changes, profile updates, logins, etc.).
    """

    __tablename__ = "audit_logs"

    # Who did it
    user_uuid: Mapped[Optional[str]] = mapped_column(
        String(36), sa.ForeignKey("user_login.uuid", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # What did they do
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # Example: LOGIN, CREATE_USER
    module: Mapped[str] = mapped_column(String(100), nullable=False)   # Example: AUTH, RBAC
    
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
