"""Alembic environment.

Uses the same `DATABASE_URL` as the FastAPI process (`app.settings`).
No domain models yet — `target_metadata` is the empty 1.2a declarative base.
"""

from logging.config import fileConfig
from typing import Any

from alembic import context
from alembic.config import Config
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection, Engine

from app.models.base import Base
from app.settings import Settings, get_settings


alembic_configuration: Config = context.config

if alembic_configuration.config_file_name is not None:
    fileConfig(alembic_configuration.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in SQL-generation mode (no live connection)."""

    sqlalchemy_url: str = _resolve_database_url()
    context.configure(
        url=sqlalchemy_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""

    _apply_database_url_to_alembic_configuration()
    configuration_section: dict[str, Any] | None = alembic_configuration.get_section(
        alembic_configuration.config_ini_section,
    )

    if configuration_section is None:
        raise RuntimeError("Alembic configuration section is missing.")

    our_migration_engine: Engine = engine_from_config(
        configuration_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with our_migration_engine.connect() as our_database_connection:
        _run_migrations_on_connection(our_database_connection)

    our_migration_engine.dispose()


def _run_migrations_on_connection(our_database_connection: Connection) -> None:
    """Configure Alembic context and apply revisions on an open connection."""

    context.configure(
        connection=our_database_connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


def _apply_database_url_to_alembic_configuration() -> None:
    """Copy Settings.database_url into Alembic's sqlalchemy.url option."""

    sqlalchemy_url: str = _resolve_database_url()
    alembic_configuration.set_main_option("sqlalchemy.url", sqlalchemy_url)


def _resolve_database_url() -> str:
    """Return DATABASE_URL from the shared settings module."""

    settings: Settings = get_settings()

    return settings.database_url


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
