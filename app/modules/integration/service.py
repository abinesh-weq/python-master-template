import json
import re
from typing import Optional

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import generate_uuid
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
        if not provider:
            await self._write_log(
                db, recipient=recipient, channel=channel,
                template_code=template_code, provider_name=None,
                http_status=None, status="FAILURE",
                error_message=f"No active provider found for channel '{channel}'.",
            )
            return False

        # ── Step 3: Load provider API metadata + mapping ──────────────────────
        metadata = await self._get_metadata(db, provider.id)
        mapping = await self._get_mapping(db, provider.id, template_code)

        if not metadata or not mapping:
            await self._write_log(
                db, recipient=recipient, channel=channel,
                template_code=template_code, provider_name=provider.provider_name,
                http_status=None, status="FAILURE",
                error_message="Provider metadata or API mapping not configured.",
            )
            return False

        # ── Step 4: Build rendered body ───────────────────────────────────────
        rendered_body = self._render_template(mapping.request_body_template, variables)
        rendered_body_str = json.dumps(rendered_body) if isinstance(rendered_body, dict) else rendered_body

        headers = {"Content-Type": "application/json"}
        if metadata.headers_json:
            try:
                headers.update(json.loads(metadata.headers_json))
            except json.JSONDecodeError:
                pass
        if metadata.api_key:
            headers["Authorization"] = f"Bearer {metadata.api_key}"

        url = f"{metadata.base_url.rstrip('/')}/{mapping.endpoint_path.lstrip('/')}"

        # ── Step 5: Fire async HTTP request ───────────────────────────────────
        http_status: Optional[int] = None
        response_text: str = ""
        dispatch_status = "FAILURE"
        error_message: Optional[str] = None

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
        log_id = await self._write_log(
            db, recipient=recipient, channel=channel,
            template_code=template_code, provider_name=provider.provider_name,
            http_status=http_status, status=dispatch_status,
            error_message=error_message,
        )
        await self._write_payload_log(
            db,
            log_id=log_id,
            request_payload=rendered_body_str,
            response_payload=response_text,
        )

        return dispatch_status == "SUCCESS"

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
        db: AsyncSession, provider_id: str
    ) -> Optional[ProviderApiMetadata]:
        result = await db.execute(
            select(ProviderApiMetadata).where(
                and_(
                    ProviderApiMetadata.provider_id == provider_id,
                    ProviderApiMetadata.is_active.is_(True),
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_mapping(
        db: AsyncSession, provider_id: str, action_code: str
    ) -> Optional[ProviderApiMapping]:
        result = await db.execute(
            select(ProviderApiMapping).where(
                and_(
                    ProviderApiMapping.provider_id == provider_id,
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
            id=generate_uuid(),
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
        return log.id

    @staticmethod
    async def _write_payload_log(
        db: AsyncSession,
        log_id: str,
        request_payload: str,
        response_payload: str,
    ) -> None:
        payload_log = NotificationPayloadLog(
            notification_log_id=log_id,
            request_payload=request_payload,
            response_payload=response_payload,
        )
        db.add(payload_log)
        await db.flush()


integration_service = IntegrationService()
