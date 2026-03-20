"""Alembic environment — imports all models so autogenerate detects them."""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Path Setup ────────────────────────────────────────────────────────────────
# Ensure the project root is on sys.path so app.* imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Load Settings ─────────────────────────────────────────────────────────────
from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

# ── Import ALL models so Alembic autogenerate sees every table ────────────────
import app.modules.users.models  # noqa: F401
import app.modules.rbac.models  # noqa: F401
import app.modules.predefined.models  # noqa: F401
import app.modules.integration.models  # noqa: F401
import app.modules.audit.models  # noqa: F401
import app.modules.otp.models  # noqa: F401

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from settings so .env is the single source of truth
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Migration Runners ─────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
