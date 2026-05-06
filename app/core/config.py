import json
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "WeQ Backend API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    AUDIT_LOG_ENABLED: bool = True
    AUTH_ENABLED: bool = True  # Set to False for local dev (bypasses JWT and RBAC)

    # ── Database (MySQL) ──────────────────────────────────────────────────────
    DB_HOST: str = ""
    DB_PORT: int = 3306
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = ""

    # ── Security (JWT & Password) ─────────────────────────────────────────────
    JWT_SECRET_KEY: str  # Required - no default for security
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_REGEX: str = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&])[A-Za-z\\d@$!%*?&]{8,}$"
    USERNAME_REGEX: str = r"^[A-Za-z0-9_.-]{3,30}$"
    PHONE_NUMBER_REGEX: str = r"^[0-9]{7,15}$"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long for security")
        return v

    @field_validator("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    @classmethod
    def validate_database_fields(cls, v: str) -> str:
        if not v:
            raise ValueError(f"Database configuration field must be provided in .env file")
        return v

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Stored as a plain str — pydantic-settings NEVER auto-JSON-parses str
    # fields, so ALLOWED_ORIGINS=* just works. cors_origins property below
    # converts it to the list that CORSMiddleware needs.
    ALLOWED_ORIGINS: str = "*"

    @property
    def cors_origins(self) -> list:
        """
        Parses ALLOWED_ORIGINS into a list for CORSMiddleware.
        Supported .env formats:
          ALLOWED_ORIGINS=*                              (wildcard)
          ALLOWED_ORIGINS=http://a.com,http://b.com      (comma-separated)
          ALLOWED_ORIGINS=["http://a.com","http://b.com"] (JSON array)
        """
        v = self.ALLOWED_ORIGINS.strip()
        if v.startswith("["):
            return json.loads(v)
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    # ── OTP ───────────────────────────────────────────────────────────────────
    OTP_EXPIRE_MINUTES: int = 5

    # ── Default Roles ─────────────────────────────────────────────────────────
    DEFAULT_USER_ROLE: str = "user"
    DEFAULT_ADMIN_ROLE: str = "admin"

    # ── Computed DB URLs ──────────────────────────────────────────────────────
    @property
    def DATABASE_URL(self) -> str:
        """Async URL for SQLAlchemy (aiomysql driver)."""
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync URL for Alembic migrations (pymysql driver)."""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "allow"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
