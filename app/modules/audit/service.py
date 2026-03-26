from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.modules.audit.models import AuditLog


class AuditService:

    async def log(
        self,
        db: AsyncSession,
        action: str,
        module: str,
        user_uuid: Optional[str] = None,
        username: Optional[str] = None,
        description: Optional[str] = None,
        payload: Optional[dict] = None,
        response_body: Optional[Any] = None,
        request: Optional[Request] = None,
        status_code: int = 200,
        force_save_response: bool = False,
    ) -> Optional[AuditLog]:
        # Debugging
        print(f"DEBUG: AuditService.log called for action={action}, module={module}")
        """
        Persists a record of a sensitive action.
        - status_code: The HTTP status code of the response.
        - force_save_response: If True, saves the response even if status_code is 200.
        """
        from app.core.config import settings

        if not settings.AUDIT_LOG_ENABLED:
            return None
        ip_addr = None
        user_agent = None
        method = None
        path = None

        if request:
            ip_addr = request.headers.get("x-forwarded-for") or request.client.host
            user_agent = request.headers.get("user-agent")
            method = request.method
            path = str(request.url.path)
            # Mark as audited to prevent duplicate logging in global middleware
            request.state.audited = True

        # 1. Censor and process payload (Request)
        if payload:
            payload = self._censor_sensitive_fields(payload)

        # 2. Censor and process response body
        stored_response = None
        if response_body is not None:
            # Policy: Store response for every API for every status code.
            # EXCEPTION: Avoid storing the response of list APIs for success (200/201) to save space.

            is_success = 200 <= status_code < 300

            # Detect if this is a "list" response (raw list or wrapped list)
            is_list = isinstance(response_body, list)
            if not is_list:
                # Check for ApiResponse or PaginatedResponse wrappers
                if hasattr(response_body, "data") and isinstance(
                    getattr(response_body, "data"), list
                ):
                    is_list = True
                elif hasattr(response_body, "content") and isinstance(
                    getattr(response_body, "content"), list
                ):
                    is_list = True
                elif isinstance(response_body, dict):
                    if isinstance(response_body.get("data"), list) or isinstance(
                        response_body.get("content"), list
                    ):
                        is_list = True

            # Decide whether to store based on user's market standard policy
            should_store = not (is_list and is_success)

            if should_store or force_save_response:
                # Safely convert to serializable format
                if hasattr(response_body, "model_dump"):
                    # Use getattr to satisfy static analyzers that might think it's a dict
                    stored_response = getattr(response_body, "model_dump")()
                elif isinstance(response_body, dict):
                    stored_response = response_body.copy()
                elif isinstance(response_body, list):
                    # For lists (if forced or not success), store a summarized version
                    # to keep the audit log manageable.
                    stored_response = {"items": self._summarize_lists(response_body)}
                else:
                    stored_response = {"data": str(response_body)}

                # Censor sensitive fields in response
                stored_response = self._censor_sensitive_fields(stored_response)

                # Summarize lists recursively to avoid bloat in nested structures
                stored_response = self._summarize_lists(stored_response)

        log_entry = AuditLog(
            user_uuid=user_uuid,
            username=username,
            action=action,
            module=module,
            method=method,
            path=path,
            description=description,
            payload=payload,
            response_body=stored_response,
            ip_address=ip_addr,
            user_agent=user_agent,
            status_code=status_code,
        )

        db.add(log_entry)
        await db.flush()
        return log_entry

    def _censor_sensitive_fields(self, data: Any) -> Any:
        """Recursively censors passwords, tokens, etc."""
        if not isinstance(data, dict):
            return data

        keys_to_censor = {
            "password",
            "token",
            "refresh_token",
            "access_token",
            "otp",
            "secret",
        }
        censored = data.copy()

        for key in list(censored.keys()):
            if any(target in key.lower() for target in keys_to_censor):
                censored[key] = "********"
            elif isinstance(censored[key], dict):
                censored[key] = self._censor_sensitive_fields(censored[key])
            elif isinstance(censored[key], list):
                censored[key] = [
                    self._censor_sensitive_fields(i) for i in censored[key]
                ]

        return censored

    def _summarize_lists(self, data: Any) -> Any:
        """Replaces large lists with a summary string like '[List of 50 items]'."""
        if isinstance(data, list):
            if len(data) > 5:  # Threshold for summarization
                return f"[List of {len(data)} items]"
            return [self._summarize_lists(i) for i in data]
        elif isinstance(data, dict):
            return {k: self._summarize_lists(v) for k, v in data.items()}
        return data


audit_service = AuditService()
