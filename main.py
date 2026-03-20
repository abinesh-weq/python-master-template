import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middlewares import AuditMiddleware, LoggingMiddleware, limiter

# ── Module Routers ────────────────────────────────────────────────────────────
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.rbac.router import router as rbac_router
from app.modules.predefined.router import router as predefined_router

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


# ── Route Registration ────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rbac_router)
app.include_router(predefined_router)


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "UP", "app": settings.APP_NAME, "version": settings.APP_VERSION}
