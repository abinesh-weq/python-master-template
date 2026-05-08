import asyncio
import json
import re
import smtplib
from email.message import EmailMessage
from typing import List, Optional, Tuple

import httpx
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common_models.base_model import generate_uuid
from app.modules.integration.models import (
    CommunicationProviderConfig,
    NotificationLog,
    NotificationPayloadLog,
    NotificationTemplateMaster,
    ProviderApiMapping,
    ProviderApiMetadata,
)


class IntegrationService:
    """
    Dynamic Notification Dispatch Engine.
    Mirrors Java IntegrationService with DB-driven provider routing.
    No hardcoded API keys — all credentials live in the database.
    """

    def _is_smtp_provider(self, provider, metadata) -> bool:
        """Determine whether to use SMTP driver instead of httpx."""
        prov_name = (provider.provider_name or "").upper()
        base_url = (metadata.base_url or "").lower()
        if prov_name.endswith("_SMTP"):
            return True
        if base_url.startswith("smtp://") or base_url.startswith("smtp."):
            return True
        # If not clearly HTTP and looks like smtp host:port
        if "smtp" in base_url and not base_url.startswith("http"):
            return True
        return False

    async def _send_email_via_smtp(
        self,
        metadata,
        recipient: str,
        subject: str,
        body: str,
        variables: dict,
    ) -> bool:
        """Send email through SMTP as a fallback for SMTP provider definitions."""
        base_url = metadata.base_url.strip()
        if base_url.startswith("smtp://"):
            base_url = base_url[len("smtp://") :]

        parts = base_url.split(":")
        smtp_host = parts[0] if parts else "localhost"
        smtp_port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 587

        username = metadata.api_key or ""
        password = metadata.api_secret or ""

        from_address = username or "noreply@example.com"
        if metadata.headers_json:
            try:
                headers = json.loads(metadata.headers_json)
                from_address = headers.get("from_address", from_address)
            except Exception:
                pass

        rendered_body = body
        for key, value in variables.items():
            rendered_body = rendered_body.replace("{" + key + "}", str(value))

        message = EmailMessage()
        message["From"] = from_address
        message["To"] = recipient
        message["Subject"] = subject or "Your OTP"

        if rendered_body.strip().startswith("<"):
            message.add_alternative(rendered_body, subtype="html")
        else:
            message.set_content(rendered_body)

        def _sync_send():
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
                smtp.ehlo()
                if smtp_port in (587, 25):
                    smtp.starttls()
                    smtp.ehlo()
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)

        try:
            await asyncio.to_thread(_sync_send)
            print(f"INFO: SMTP send succeeded for recipient={recipient} via {smtp_host}:{smtp_port}")
            return True
        except Exception as exc:
            self._last_smtp_error = str(exc)
            print(f"ERROR: SMTP send failed for recipient={recipient} via {smtp_host}:{smtp_port}")
            print(f"ERROR: SMTP exception: {exc}")
            return False

    async def dispatch(
        self,
        db: AsyncSession,
        template_code: str,
        recipient: str,
        variables: dict,
    ) -> bool:
        """
        Full dispatch algorithm:
        1. Load template by code
        2. Find highest-priority active provider for the channel
        3. Load provider metadata + API mapping
        4. Substitute {{VARIABLE}} placeholders
        5. Fire async HTTP request via httpx
        6. Write NotificationLog + NotificationPayloadLog
        """
        # ── Step 1: Load template ─────────────────────────────────────────────
        template = await self._get_template(db, template_code)
        if not template:
            await self._write_log(
                db, recipient=recipient, channel="UNKNOWN",
                template_code=template_code, provider_name=None,
                http_status=None, status="FAILURE",
                error_message=f"Template '{template_code}' not found.",
            )
            return False

        channel = template.channel  # EMAIL | SMS | PUSH

        # ── Step 2: Find best provider ────────────────────────────────────────
        provider = await self._get_active_provider(db, channel)
        print(f"Selected provider for {channel}: {provider.provider_name if provider else None}")
        if not provider:
            await self._write_log(
                db, recipient=recipient, channel=channel,
                template_code=template_code, provider_name=None,
                http_status=None, status="FAILURE",
                error_message=f"No active provider found for channel '{channel}'.",
            )
            return False

        # ── Step 3: Load provider API metadata + mapping ──────────────────────
        metadata = await self._get_metadata(db, provider.uuid)
        mapping = await self._get_mapping(db, provider.uuid, template_code)

        if not metadata or not mapping:
            await self._write_log(
                db, recipient=recipient, channel=channel,
                template_code=template_code, provider_name=provider.provider_name,
                http_status=None, status="FAILURE",
                error_message="Provider metadata or API mapping not configured.",
            )
            return False

        # ── Step 4: SMTP provider path ───────────────────────────────────────
        if channel == "EMAIL" and self._is_smtp_provider(provider, metadata):
            smtp_success = await self._send_email_via_smtp(
                metadata=metadata,
                recipient=recipient,
                subject=template.subject,
                body=template.body_template,
                variables=variables,
            )

            dispatch_status = "SUCCESS" if smtp_success else "FAILURE"
            http_status = 250 if smtp_success else None
            response_text = "SMTP send succeeded" if smtp_success else getattr(self, "_last_smtp_error", "SMTP send failed")
            error_message = None if smtp_success else response_text

            # log and store payload; body template used for record
            log_uuid = await self._write_log(
                db, recipient=recipient, channel=channel,
                template_code=template_code, provider_name=provider.provider_name,
                http_status=http_status, status=dispatch_status,
                error_message=error_message,
            )
            await self._write_payload_log(
                db,
                notification_log_uuid=log_uuid,
                request_payload=template.body_template,
                response_payload=response_text,
            )

            return smtp_success

        # ── Step 4: Prepare headers & Build rendered body (HTTP paths) ───────────
        headers = {"Content-Type": "application/json"}
        if metadata.headers_json:
            try:
                headers.update(json.loads(metadata.headers_json))
            except json.JSONDecodeError:
                pass

        if "RECIPIENT" not in variables:
            variables["RECIPIENT"] = recipient

        # If the provider expects form-urlencoded (like Twilio), URL-encode the variables so '+' doesn't become ' '
        if headers.get("Content-Type") == "application/x-www-form-urlencoded":
            import urllib.parse
            encoded_vars = {k: urllib.parse.quote(str(v)) for k, v in variables.items()}
            rendered_body = self._render_template(mapping.request_body_template, encoded_vars)
        else:
            rendered_body = self._render_template(mapping.request_body_template, variables)

        rendered_body_str = json.dumps(rendered_body) if isinstance(rendered_body, dict) else rendered_body
        if metadata.api_key:
            headers["Authorization"] = f"Bearer {metadata.api_key}"

        url = f"{metadata.base_url.rstrip('/')}/{mapping.endpoint_path.lstrip('/')}"

        # ── Step 5: Fire async HTTP request ───────────────────────────────────
        http_status: Optional[int] = None
        response_text: str = ""
        dispatch_status = "FAILURE"
        error_message: Optional[str] = None

        print(f"DEBUG: Provider URL -> {url}")
        print(f"DEBUG: Provider Headers -> {headers}")
        print(f"DEBUG: Provider Body -> {rendered_body_str}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(
                    method=mapping.http_method.upper(),
                    url=url,
                    content=rendered_body_str,
                    headers=headers,
                )
                http_status = response.status_code
                response_text = response.text
                if 200 <= http_status < 300:
                    dispatch_status = "SUCCESS"
                else:
                    error_message = f"HTTP {http_status}: {response_text[:500]}"
        except Exception as exc:
            error_message = str(exc)[:500]

        # ── Step 6: Write audit logs ──────────────────────────────────────────
        log_uuid = await self._write_log(
            db, recipient=recipient, channel=channel,
            template_code=template_code, provider_name=provider.provider_name,
            http_status=http_status, status=dispatch_status,
            error_message=error_message,
        )
        await self._write_payload_log(
            db,
            notification_log_uuid=log_uuid,
            request_payload=rendered_body_str,
            response_payload=response_text,
        )

        return dispatch_status == "SUCCESS"

    # ── Admin CRUD Methods ────────────────────────────────────────────────────

    # Communication Provider Config
    async def create_provider_config(
        self, db: AsyncSession, data: dict
    ) -> CommunicationProviderConfig:
        provider = CommunicationProviderConfig(**data)
        db.add(provider)
        await db.flush()
        return provider

    async def get_provider_configs(
        self, db: AsyncSession, page: int = 0, size: int = 20
    ) -> Tuple[List[CommunicationProviderConfig], int]:
        query = select(CommunicationProviderConfig)
        total_result = await db.execute(
            select(func.count(CommunicationProviderConfig.id))
        )
        total = total_result.scalar()
        
        result = await db.execute(query.offset(page * size).limit(size))
        return result.scalars().all(), total

    async def get_provider_config_by_uuid(
        self, db: AsyncSession, uuid: str
    ) -> Optional[CommunicationProviderConfig]:
        result = await db.execute(
            select(CommunicationProviderConfig).where(CommunicationProviderConfig.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def update_provider_config(
        self, db: AsyncSession, uuid: str, data: dict
    ) -> Optional[CommunicationProviderConfig]:
        provider = await self.get_provider_config_by_uuid(db, uuid)
        if not provider:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(provider, key, value)
        await db.flush()
        return provider

    async def delete_provider_config(self, db: AsyncSession, uuid: str) -> bool:
        provider = await self.get_provider_config_by_uuid(db, uuid)
        if not provider:
            return False
        await db.delete(provider)
        await db.flush()
        return True

    # Provider API Metadata
    async def create_provider_metadata(
        self, db: AsyncSession, data: dict
    ) -> ProviderApiMetadata:
        metadata = ProviderApiMetadata(**data)
        db.add(metadata)
        await db.flush()
        return metadata

    async def get_provider_metadata(
        self, db: AsyncSession, provider_uuid: str
    ) -> Optional[ProviderApiMetadata]:
        result = await db.execute(
            select(ProviderApiMetadata).where(ProviderApiMetadata.provider_uuid == provider_uuid)
        )
        return result.scalar_one_or_none()

    async def update_provider_metadata(
        self, db: AsyncSession, provider_uuid: str, data: dict
    ) -> Optional[ProviderApiMetadata]:
        metadata = await self.get_provider_metadata(db, provider_uuid)
        if not metadata:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(metadata, key, value)
        await db.flush()
        return metadata

    async def delete_provider_metadata(self, db: AsyncSession, provider_uuid: str) -> bool:
        metadata = await self.get_provider_metadata(db, provider_uuid)
        if not metadata:
            return False
        await db.delete(metadata)
        await db.flush()
        return True

    # Provider API Mapping
    async def create_provider_mapping(
        self, db: AsyncSession, data: dict
    ) -> ProviderApiMapping:
        mapping = ProviderApiMapping(**data)
        db.add(mapping)
        await db.flush()
        return mapping

    async def get_provider_mappings(
        self, db: AsyncSession, provider_uuid: Optional[str] = None, page: int = 0, size: int = 20
    ) -> Tuple[List[ProviderApiMapping], int]:
        query = select(ProviderApiMapping)
        if provider_uuid:
            query = query.where(ProviderApiMapping.provider_uuid == provider_uuid)
        
        total_result = await db.execute(
            select(func.count(ProviderApiMapping.id))
        )
        total = total_result.scalar()
        
        result = await db.execute(query.offset(page * size).limit(size))
        return result.scalars().all(), total

    async def get_provider_mapping_by_uuid(
        self, db: AsyncSession, uuid: str
    ) -> Optional[ProviderApiMapping]:
        result = await db.execute(
            select(ProviderApiMapping).where(ProviderApiMapping.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def update_provider_mapping(
        self, db: AsyncSession, uuid: str, data: dict
    ) -> Optional[ProviderApiMapping]:
        mapping = await self.get_provider_mapping_by_uuid(db, uuid)
        if not mapping:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(mapping, key, value)
        await db.flush()
        return mapping

    async def delete_provider_mapping(self, db: AsyncSession, uuid: str) -> bool:
        mapping = await self.get_provider_mapping_by_uuid(db, uuid)
        if not mapping:
            return False
        await db.delete(mapping)
        await db.flush()
        return True

    # Notification Template Master
    async def create_template(
        self, db: AsyncSession, data: dict
    ) -> NotificationTemplateMaster:
        template = NotificationTemplateMaster(**data)
        db.add(template)
        await db.flush()
        return template

    async def get_templates(
        self, db: AsyncSession, page: int = 0, size: int = 20
    ) -> Tuple[List[NotificationTemplateMaster], int]:
        query = select(NotificationTemplateMaster)
        total_result = await db.execute(
            select(func.count(NotificationTemplateMaster.id))
        )
        total = total_result.scalar()
        
        result = await db.execute(query.offset(page * size).limit(size))
        return result.scalars().all(), total

    async def get_template_by_uuid(
        self, db: AsyncSession, uuid: str
    ) -> Optional[NotificationTemplateMaster]:
        result = await db.execute(
            select(NotificationTemplateMaster).where(NotificationTemplateMaster.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def get_template_by_code(
        self, db: AsyncSession, code: str
    ) -> Optional[NotificationTemplateMaster]:
        result = await db.execute(
            select(NotificationTemplateMaster).where(NotificationTemplateMaster.code == code)
        )
        return result.scalar_one_or_none()

    async def update_template(
        self, db: AsyncSession, uuid: str, data: dict
    ) -> Optional[NotificationTemplateMaster]:
        template = await self.get_template_by_uuid(db, uuid)
        if not template:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(template, key, value)
        await db.flush()
        return template

    async def delete_template(self, db: AsyncSession, uuid: str) -> bool:
        template = await self.get_template_by_uuid(db, uuid)
        if not template:
            return False
        await db.delete(template)
        await db.flush()
        return True

    # Notification Logs (Read-only)
    async def get_notification_logs(
        self, db: AsyncSession, page: int = 0, size: int = 20
    ) -> Tuple[List[NotificationLog], int]:
        query = select(NotificationLog).order_by(NotificationLog.id.desc())
        total_result = await db.execute(
            select(func.count(NotificationLog.id))
        )
        total = total_result.scalar()
        
        result = await db.execute(query.offset(page * size).limit(size))
        return result.scalars().all(), total

    async def get_notification_log_by_uuid(
        self, db: AsyncSession, uuid: str
    ) -> Optional[NotificationLog]:
        result = await db.execute(
            select(NotificationLog).where(NotificationLog.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def get_payload_logs(
        self, db: AsyncSession, notification_log_uuid: str
    ) -> List[NotificationPayloadLog]:
        result = await db.execute(
            select(NotificationPayloadLog).where(
                NotificationPayloadLog.notification_log_uuid == notification_log_uuid
            )
        )
        return result.scalars().all()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _render_template(template_str: str, variables: dict) -> str:
        """Substitutes {{VARIABLE}} placeholders in template string."""
        result = template_str
        for key, value in variables.items():
            result = re.sub(r"\{\{" + re.escape(key) + r"\}\}", str(value), result)
        return result

    @staticmethod
    async def _get_template(
        db: AsyncSession, code: str
    ) -> Optional[NotificationTemplateMaster]:
        result = await db.execute(
            select(NotificationTemplateMaster).where(
                and_(
                    NotificationTemplateMaster.code == code,
                    NotificationTemplateMaster.is_active.is_(True),
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_active_provider(
        db: AsyncSession, channel: str
    ) -> Optional[CommunicationProviderConfig]:
        """Returns highest-priority (lowest priority number) active provider."""
        result = await db.execute(
            select(CommunicationProviderConfig)
            .where(
                and_(
                    CommunicationProviderConfig.provider_type == channel,
                    CommunicationProviderConfig.is_active.is_(True),
                )
            )
            .order_by(CommunicationProviderConfig.priority.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_metadata(
        db: AsyncSession, provider_uuid: str
    ) -> Optional[ProviderApiMetadata]:
        result = await db.execute(
            select(ProviderApiMetadata).where(
                and_(
                    ProviderApiMetadata.provider_uuid == provider_uuid,
                    ProviderApiMetadata.is_active.is_(True),
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_mapping(
        db: AsyncSession, provider_uuid: str, action_code: str
    ) -> Optional[ProviderApiMapping]:
        result = await db.execute(
            select(ProviderApiMapping).where(
                and_(
                    ProviderApiMapping.provider_uuid == provider_uuid,
                    ProviderApiMapping.action_code == action_code,
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _write_log(
        db: AsyncSession,
        recipient: str,
        channel: str,
        template_code: str,
        provider_name: Optional[str],
        http_status: Optional[int],
        status: str,
        error_message: Optional[str],
    ) -> str:
        log = NotificationLog(
            recipient=recipient,
            channel=channel,
            template_code=template_code,
            provider_name=provider_name,
            http_status_code=http_status,
            status=status,
            error_message=error_message,
        )
        db.add(log)
        await db.flush()
        return log.uuid

    @staticmethod
    async def _write_payload_log(
        db: AsyncSession,
        notification_log_uuid: str,
        request_payload: str,
        response_payload: str,
    ) -> None:
        payload_log = NotificationPayloadLog(
            notification_log_uuid=notification_log_uuid,
            request_payload=request_payload,
            response_payload=response_payload,
        )
        db.add(payload_log)
        await db.flush()


integration_service = IntegrationService()
