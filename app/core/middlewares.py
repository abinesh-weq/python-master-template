import json
import logging
import time
from typing import Any, Optional

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.concurrency import iterate_in_threadpool

from app.modules.audit.service import audit_service
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.modules.users.service import user_service

logger = logging.getLogger(__name__)

# ── Rate Limiter (Slowapi — mirrors Java Bucket4j) ────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Logging Middleware (mirrors Java LoggingInterceptor) ──────────────────────
class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Captures IP, method, URL, and execution time (ms) for every request.
    Mirrors Java's HandlerInterceptor pre/postHandle pattern.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        url = str(request.url)

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "[%s] %s %s — %d — %.2fms",
            client_ip,
            method,
            url,
            response.status_code,
            elapsed_ms,
        )
        return response


# ── Audit Middleware (mirrors Enterprise Audit Interceptors) ──────────────────
class AuditMiddleware(BaseHTTPMiddleware):
    """
    Automatic Audit Logging Middleware.
    Captures request/response payloads and stores them in the audit_logs table.
    Ensures storage strategy: Logs all endpoints, but skips successful list responses.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.config import settings
        if not settings.AUDIT_LOG_ENABLED:
            return await call_next(request)

        # 1. Skip noisy or non-API endpoints
        path = request.url.path
        if path in ["/health", "/swagger", "/redoc", "/api/v1/openapi.json"] or not path.startswith("/api"):
            return await call_next(request)

        # 2. Capture Request Body (for mutations)
        request_payload = None
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                body_bytes: bytes = await request.body()
                if body_bytes:
                    try:
                        request_payload = json.loads(body_bytes)
                    except json.JSONDecodeError:
                        request_payload = {"raw": body_bytes.decode("utf-8", errors="ignore")[:2000]}
                
                # Restore the request body stream for downstream route handlers
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive
            except Exception as e:
                logger.warning(f"AuditMiddleware: Could not capture request body: {e}")

        # 3. Execute the Request
        response: Response = await call_next(request)

        # 4. Skip global logging if already audited by a high-context manual call
        if getattr(request.state, "audited", False):
            return response

        # 5. Capture Response Body
        response_data = None
        try:
            # Consume and then recreate the response iterator
            response_body_chunks = [chunk async for chunk in response.body_iterator]
            response.body_iterator = iterate_in_threadpool(iter(response_body_chunks))
            
            full_bytes: bytes = b"".join(response_body_chunks)
            if full_bytes:
                try:
                    response_data = json.loads(full_bytes)
                except json.JSONDecodeError:
                    response_data = {"raw": full_bytes.decode("utf-8", errors="ignore")[:1000]}
        except Exception as e:
            logger.warning(f"AuditMiddleware: Could not capture response body: {e}")

        # 6. Background Log to DB
        import asyncio
        task: asyncio.Task = asyncio.create_task(self._log_interaction(request, response, request_payload, response_data))
        
        if not hasattr(self, "_tasks"):
            self._tasks = set()
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        return response

    async def _log_interaction(self, request: Request, response: Response, payload: Any, response_data: Any):
        """Internal helper to identify user and persist audit record."""
        try:
            async with AsyncSessionLocal() as db:
                user_id = None
                username = None
                
                # Identify user from JWT
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.lower().startswith("bearer "):
                    token = auth_header.split(" ")[1]
                    try:
                        token_payload = decode_token(token)
                        email = token_payload.get("sub")
                        if email:
                            user = await user_service.get_by_email(db, email)
                            if user:
                                user_id = user.id
                                username = user.username
                    except Exception:
                        pass
                
                # Metadata extraction
                url_path: str = str(request.url.path)
                path_parts: list[str] = url_path.strip("/").split("/")
                module = path_parts[2].upper() if len(path_parts) > 2 else "CORE"
                action_name = f"{request.method} {url_path}"

                await audit_service.log(
                    db=db,
                    user_id=user_id,
                    username=username,
                    action=action_name,
                    module=module,
                    payload=payload,
                    response_body=response_data,
                    request=request,
                    status_code=response.status_code
                )
                await db.commit()
        except Exception as e:
            # Fail silently to avoid crashing the main thread, but log the error
            logger.error(f"AuditMiddleware indexing failed: {e}")
