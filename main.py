import logging

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.core.middlewares import AuditMiddleware, LoggingMiddleware, RequestIdMiddleware, limiter

# ── Module Routers ────────────────────────────────────────────────────
from app.modules.auth.routers import router as auth_router
from app.modules.users.routers import router as users_router
from app.modules.rbac.routers import router as rbac_router
from app.modules.predefined.routers import router as predefined_router
from app.modules.integration.routers import router as integration_router
from app.modules.documents.routers import router as documents_router

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# ── FastAPI Application ───────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "WeQ Python Backend — standalone FastAPI clone of the Java Spring Boot engine. "
        "Package-by-feature layout with RBAC, JWT, MFA, OTP, Social SSO, "
        "predefined tree masters, and a dynamic integration engine."
    ),
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
)

# ── Rate Limiting (Slowapi — mirrors Bucket4j) ────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Logging & Audit Middlewares (mirrors Java Interceptors) ───────────────────
app.add_middleware(RequestIdMiddleware)  # Must be first to set request ID
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuditMiddleware)

# ── CORS Middleware (mirrors Java WebMvcConfig — moved last for best practice)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Exception Handlers (mirrors Java GlobalExceptionHandler) ───────────
register_exception_handlers(app)

# ── Startup — Cache Initialization ────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    """
    Mirrors Java @PostConstruct / ApplicationReadyEvent.
    Initializes the InMemoryBackend for fastapi-cache2.
    Equivalent to Spring Boot's Caffeine CacheManager bean.
    """
    FastAPICache.init(InMemoryBackend(), prefix="weq-cache")
    logging.getLogger(__name__).info("✅ In-memory cache initialized.")


# ── Shutdown — Graceful Cleanup ───────────────────────────────────────────────
@app.on_event("shutdown")
async def shutdown_event():
    """
    Graceful shutdown: close database connections and clear cache.
    Ensures clean termination of resources.
    """
    from app.core.database import engine
    
    # Close database connections
    await engine.dispose()
    logging.getLogger(__name__).info("✅ Database connections closed.")
    
    # Clear cache
    try:
        from fastapi_cache import FastAPICache
        await FastAPICache.clear()
        logging.getLogger(__name__).info("✅ Cache cleared.")
    except Exception as e:
        logging.getLogger(__name__).warning(f"⚠️ Cache cleanup failed: {e}")


# ── Static Files ────────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
import os

# Create uploads directory if it doesn't exist
uploads_dir = "data/uploads"
os.makedirs(uploads_dir, exist_ok=True)

# Mount static files for document uploads
app.mount("/static/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# ── Route Registration ────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rbac_router)
app.include_router(predefined_router)
app.include_router(integration_router)
app.include_router(documents_router)


# ── Health & Cache APIs ───────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check DB and cache status."""
    from app.core.config import settings
    
    # Check database connectivity
    db_status = "UP"
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "DOWN"
        db_error = str(e)
    
    # Check cache connectivity
    cache_status = "UP"
    cache_error = None
    try:
        from fastapi_cache import FastAPICache
        from fastapi_cache.backends.inmemory import InMemoryBackend

        # Ensure FastAPICache is initialized
        try:
            backend = FastAPICache.get_backend()
        except AssertionError:
            FastAPICache.init(InMemoryBackend(), prefix="weq-cache")
            backend = FastAPICache.get_backend()

        # health probe via key roundtrip
        await backend.set("health_check", b"1", expire=5)
        found = await backend.get("health_check")
        if found is None:
            raise RuntimeError("Cache probe key unavailable")
    except Exception as e:
        cache_status = "DOWN"
        cache_error = str(e)
    
    # Overall status
    overall_status = "UP" if db_status == "UP" and cache_status == "UP" else "DOWN"
    
    return {
        "status": overall_status,
        "timestamp": settings.APP_VERSION and settings.APP_VERSION,
        "version": settings.APP_VERSION,
        "components": {
            "database": {
                "status": db_status,
                "details": {"error": db_error} if db_error else {}
            },
            "cache": {
                "status": cache_status,
                "details": {"error": cache_error} if cache_error else {}
            }
        }
    }


@app.post("/api/v1/admin/cache/clear", tags=["Admin - Cache"])
async def clear_cache():
    """Clear application cache (admin usage)."""
    try:
        await FastAPICache.clear()
        return {"status": "SUCCESS", "message": "Cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {e}")
