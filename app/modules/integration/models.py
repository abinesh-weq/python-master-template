from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, generate_uuid


# ── Communication Provider Config ─────────────────────────────────────────────
class CommunicationProviderConfig(Base):
    """Tracks globally configured communication services (SMS, EMAIL, PUSH)."""

    __tablename__ = "communication_provider_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "TWILIO", "SENDGRID"
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)   # SMS | EMAIL | PUSH
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Provider API Metadata ─────────────────────────────────────────────────────
class ProviderApiMetadata(Base):
    """Stores base URL, credentials, and header config for each provider."""

    __tablename__ = "provider_api_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    provider_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("communication_provider_config.uuid", ondelete="CASCADE"), nullable=False
    )
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=True)
    api_secret: Mapped[str] = mapped_column(String(500), nullable=True)
    # JSON string of extra headers {"Authorization": "Bearer ..."}
    headers_json: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Provider API Mapping ──────────────────────────────────────────────────────
class ProviderApiMapping(Base):
    """
    Stores the JSON request body template per provider per action.
    Variables like {{OTP}}, {{PHONE}} get dynamically substituted at dispatch time.
    """

    __tablename__ = "provider_api_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    provider_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("communication_provider_config.uuid", ondelete="CASCADE"), nullable=False
    )
    action_code: Mapped[str] = mapped_column(String(100), nullable=False)  # OTP_SMS, OTP_EMAIL, etc.
    endpoint_path: Mapped[str] = mapped_column(String(500), nullable=False)  # appended to base_url
    http_method: Mapped[str] = mapped_column(String(10), default="POST")
    # Raw JSON template with {{VARIABLE}} placeholders
    request_body_template: Mapped[str] = mapped_column(Text, nullable=False)


# ── Notification Template Master ──────────────────────────────────────────────
class NotificationTemplateMaster(Base):
    """Stores raw HTML / text layouts for notification content."""

    __tablename__ = "notification_template_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # OTP_EMAIL, OTP_SMS
    subject: Mapped[str] = mapped_column(String(500), nullable=True)
    # Full HTML or plain-text body with {{VARIABLE}} placeholders
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # EMAIL | SMS | PUSH
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Notification Log ──────────────────────────────────────────────────────────
class NotificationLog(Base):
    """DB audit trail for every dispatch attempt — mirrors Java notification_log."""

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    recipient: Mapped[str] = mapped_column(String(200), nullable=False)  # email or phone
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    template_code: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=True)
    http_status_code: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # SUCCESS | FAILURE
    error_message: Mapped[str] = mapped_column(Text, nullable=True)


# ── Notification Payload Log ──────────────────────────────────────────────────
class NotificationPayloadLog(Base):
    """Captures exact request/response payloads for debugging — fine-grained audit."""

    __tablename__ = "notification_payload_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    notification_log_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("notification_log.uuid", ondelete="CASCADE"), nullable=False
    )
    request_payload: Mapped[str] = mapped_column(Text, nullable=True)
    response_payload: Mapped[str] = mapped_column(Text, nullable=True)
