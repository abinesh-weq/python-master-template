import logging
import traceback

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers all global exception handlers on the FastAPI app.
    Mirrors Java @RestControllerAdvice GlobalExceptionHandler.

    Every unhandled error is forced into:
        {"status": "ERROR", "errorCode": "...", "message": "..."}
    so the Frontend never receives an unstructured crash response.
    """

    # ── FastAPI HTTP Exceptions ───────────────────────────────────────────────
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "ERROR",
                "errorCode": str(exc.status_code),
                "message": exc.detail,
                "data": None,
            },
        )

    # ── Pydantic Validation Errors (RequestValidationError) ───────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        # Build a human-readable message from Pydantic errors
        messages = [
            f"{' → '.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in errors
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "ERROR",
                "errorCode": "422",
                "message": "; ".join(messages),
                "data": None,
            },
        )

    # ── Catch-all: Unhandled Python Exceptions ────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        tb = traceback.format_exc()
        logger.error(
            "Unhandled exception on %s %s: %s\n%s",
            request.method,
            request.url.path,
            exc,
            tb,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "ERROR",
                "errorCode": "500",
                "message": f"Internal Server Exception: {str(exc)}",
                "data": None,
            },
        )
