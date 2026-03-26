from typing import Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, generate_uuid


class PredefinedMaster(Base):
    """
    Mirrors Java PredefinedMaster / predefined_master table.
    Self-referential tree structure for dropdowns, lookup data, etc.

    Tree traversal: follow parent_id upward until parent_id is NULL (root node).
    """

    __tablename__ = "predefined_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)

    # Classification — e.g., "COUNTRY", "STATE", "CITY", "CATEGORY"
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Short machine-readable code — unique within entity_type
    code: Mapped[str] = mapped_column(String(100), nullable=False)

    # Human-readable display name
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional long description
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Self-referential FK — NULL means root node
    parent_uuid: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("predefined_master.uuid", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Display ordering within siblings
    sort_order: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
