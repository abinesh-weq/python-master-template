import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Mirrors Java @MappedSuperclass BaseEntity.
    Every SQLAlchemy model inherits audit columns automatically.
    Required Properties per specification:
    - id: Integer (Primary Key, Auto-increment)
    - uuid: UUID4 (Default to uuid.uuid4)
    - created_at: DateTime (Default func.now())
    - updated_at: DateTime (Default func.now(), onupdate=func.now())
    - created_by / updated_by: String/UUID (Capturing the active context principal)
    """

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # UUID for public APIs - use CHAR(36) for better MySQL performance
    uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)

    # Audit fields - MySQL compatible datetime without timezone
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False
    )
    updated_by: Mapped[str] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


def generate_uuid() -> str:
    """Helper - returns a new UUID4 string for use as PK."""
    return str(uuid.uuid4())
