import logging
import traceback

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import exc as sqlalchemy_exc

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

    # ── SQLAlchemy/DB Errors ────────────────────────────────────────────────
    @app.exception_handler(sqlalchemy_exc.IntegrityError)
    async def sqlalchemy_integrity_handler(request: Request, exc: sqlalchemy_exc.IntegrityError):
        logger.warning("Integrity error: %s %s -> %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "status": "ERROR",
                "errorCode": "409",
                "message": "Database integrity error.",
                "data": None,
            },
        )

    @app.exception_handler(sqlalchemy_exc.DataError)
    async def sqlalchemy_data_handler(request: Request, exc: sqlalchemy_exc.DataError):
        logger.warning("Data error: %s %s -> %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "ERROR",
                "errorCode": "400",
                "message": "Invalid data format for database operation.",
                "data": None,
            },
        )

    @app.exception_handler(sqlalchemy_exc.OperationalError)
    async def sqlalchemy_operational_handler(request: Request, exc: sqlalchemy_exc.OperationalError):
        logger.error("Database operational error: %s %s -> %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "ERROR",
                "errorCode": "503",
                "message": "Database service unavailable.",
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
