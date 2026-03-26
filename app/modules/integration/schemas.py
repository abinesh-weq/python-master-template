from typing import Optional

from pydantic import BaseModel, Field

from app.core.common import PaginatedResponse


# ── Communication Provider Config ─────────────────────────────────────────────
class CommunicationProviderConfigCreateRequest(BaseModel):
    provider_name: str = Field(..., max_length=100, description="e.g., TWILIO, SENDGRID")
    provider_type: str = Field(..., description="SMS | EMAIL | PUSH")
    priority: int = Field(default=1, ge=1, description="Lower number = higher priority")
    is_active: bool = Field(default=True)


class CommunicationProviderConfigUpdateRequest(BaseModel):
    provider_name: Optional[str] = Field(None, max_length=100)
    provider_type: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class CommunicationProviderConfigResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    uuid: str
    provider_name: str
    provider_type: str
    priority: int
    is_active: bool


# ── Provider API Metadata ─────────────────────────────────────────────────────
class ProviderApiMetadataCreateRequest(BaseModel):
    provider_uuid: str = Field(..., description="UUID of the communication provider")
    base_url: str = Field(..., max_length=500)
    api_key: Optional[str] = Field(None, max_length=500)
    api_secret: Optional[str] = Field(None, max_length=500)
    headers_json: Optional[str] = Field(None, description="JSON string of extra headers")
    is_active: bool = Field(default=True)


class ProviderApiMetadataUpdateRequest(BaseModel):
    base_url: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = Field(None, max_length=500)
    api_secret: Optional[str] = Field(None, max_length=500)
    headers_json: Optional[str] = Field(None, description="JSON string of extra headers")
    is_active: Optional[bool] = None


class ProviderApiMetadataResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    uuid: str
    provider_uuid: str
    base_url: str
    api_key: Optional[str]
    api_secret: Optional[str]
    headers_json: Optional[str]
    is_active: bool


# ── Provider API Mapping ──────────────────────────────────────────────────────
class ProviderApiMappingCreateRequest(BaseModel):
    provider_uuid: str = Field(..., description="UUID of the communication provider")
    action_code: str = Field(..., max_length=100, description="OTP_SMS, OTP_EMAIL, etc.")
    endpoint_path: str = Field(..., max_length=500, description="Appended to base_url")
    http_method: str = Field(default="POST", description="HTTP method")
    request_body_template: str = Field(..., description="JSON template with {{VARIABLE}} placeholders")


class ProviderApiMappingUpdateRequest(BaseModel):
    action_code: Optional[str] = Field(None, max_length=100)
    endpoint_path: Optional[str] = Field(None, max_length=500)
    http_method: Optional[str] = None
    request_body_template: Optional[str] = None


class ProviderApiMappingResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    uuid: str
    provider_uuid: str
    action_code: str
    endpoint_path: str
    http_method: str
    request_body_template: str


# ── Notification Template Master ──────────────────────────────────────────────
class NotificationTemplateMasterCreateRequest(BaseModel):
    code: str = Field(..., max_length=100, description="Unique template code")
    subject: Optional[str] = Field(None, max_length=500)
    body_template: str = Field(..., description="HTML/text body with {{VARIABLE}} placeholders")
    channel: str = Field(..., description="EMAIL | SMS | PUSH")
    is_active: bool = Field(default=True)


class NotificationTemplateMasterUpdateRequest(BaseModel):
    subject: Optional[str] = Field(None, max_length=500)
    body_template: Optional[str] = None
    channel: Optional[str] = None
    is_active: Optional[bool] = None


class NotificationTemplateMasterResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    uuid: str
    code: str
    subject: Optional[str]
    body_template: str
    channel: str
    is_active: bool


# ── Notification Log (Read-only) ──────────────────────────────────────────────
class NotificationLogResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    uuid: str
    recipient: str
    channel: str
    template_code: str
    provider_name: Optional[str]
    http_status_code: Optional[int]
    status: str
    error_message: Optional[str]


class NotificationPayloadLogResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    uuid: str
    notification_log_uuid: str
    request_payload: Optional[str]
    response_payload: Optional[str]


# ── Paginated Responses ───────────────────────────────────────────────────────
# Note: These are used directly as PaginatedResponse[Type] in router response_model