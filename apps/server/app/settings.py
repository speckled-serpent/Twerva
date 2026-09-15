"""Process settings loaded from the environment.

`DATABASE_URL` is required outside tests. Local override: `apps/server/.env`
or an exported shell variable. On `twerva-server`, systemd / the operator
loads `/opt/twerva/database_url.env` into the process environment.

`ARTIFACT_STORAGE_DIR` is the local carousel PNG root (default
`/opt/twerva/artifacts`). Local README path is `./data/artifacts`.
S3 is not used.
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


TEST_PLACEHOLDER_DATABASE_URL: str = (
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva_test"
)
DEFAULT_SPOTMU_API_BASE_URL: str = "https://spotmu.com"
DEFAULT_ARTIFACT_STORAGE_DIR: str = "/opt/twerva/artifacts"
MISSING_DATABASE_URL_MESSAGE: str = (
    "DATABASE_URL is required outside tests. Export DATABASE_URL, place it in "
    "apps/server/.env, or on twerva-server load /opt/twerva/database_url.env."
)
POSTGRESQL_URL_PREFIX: str = "postgresql://"
POSTGRES_URL_PREFIX: str = "postgres://"
PSYCOPG3_URL_PREFIX: str = "postgresql+psycopg://"


class MissingDatabaseUrlError(RuntimeError):
    """Raised when DATABASE_URL is unset or blank outside tests."""


class Settings(BaseSettings):
    """Runtime settings for the Twerva API process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default="")
    spotmu_api_base_url: str = Field(default=DEFAULT_SPOTMU_API_BASE_URL)
    artifact_storage_dir: str = Field(default=DEFAULT_ARTIFACT_STORAGE_DIR)


_cached_settings: Settings | None = None


def get_settings() -> Settings:
    """Load process settings, caching the first successful result.

    Failed loads are not cached, so a missing URL can be corrected and retried.

    Returns:
        Settings whose `database_url` is a usable SQLAlchemy URL.

    Raises:
        MissingDatabaseUrlError: If `DATABASE_URL` is missing outside tests.
    """

    global _cached_settings

    if _cached_settings is not None:

        return _cached_settings

    loaded_settings: Settings = _load_settings()
    _cached_settings = loaded_settings

    return loaded_settings


def clear_settings_cache() -> None:
    """Drop the cached Settings instance so tests can change the environment."""

    global _cached_settings

    _cached_settings = None


def _load_settings() -> Settings:
    """Read env / `.env`, normalize the driver, and fail fast when required."""

    loaded_settings: Settings = Settings()
    stripped_database_url: str = loaded_settings.database_url.strip()
    stripped_artifact_storage_dir: str = loaded_settings.artifact_storage_dir.strip()

    if stripped_artifact_storage_dir == "":
        stripped_artifact_storage_dir = DEFAULT_ARTIFACT_STORAGE_DIR

    if stripped_database_url == "":

        if _running_in_test_environment():
            placeholder_settings: Settings = Settings(
                database_url=TEST_PLACEHOLDER_DATABASE_URL,
                artifact_storage_dir=stripped_artifact_storage_dir,
                spotmu_api_base_url=loaded_settings.spotmu_api_base_url,
            )

            return placeholder_settings

        raise MissingDatabaseUrlError(MISSING_DATABASE_URL_MESSAGE)

    normalized_database_url: str = _normalize_database_url(stripped_database_url)

    return Settings(
        database_url=normalized_database_url,
        artifact_storage_dir=stripped_artifact_storage_dir,
        spotmu_api_base_url=loaded_settings.spotmu_api_base_url,
    )


def _running_in_test_environment() -> bool:
    """Return True when pytest or an explicit Twerva test flag is active."""

    pytest_current_test: str | None = os.environ.get("PYTEST_CURRENT_TEST")
    twerva_environment_name: str = os.environ.get("TWERVA_ENV", "").strip().lower()
    twerva_testing_flag: str = os.environ.get("TWERVA_TESTING", "").strip().lower()

    if pytest_current_test is not None:

        return True

    if twerva_environment_name in {"test", "testing"}:

        return True

    if twerva_testing_flag in {"1", "true", "yes"}:

        return True

    return False


def _normalize_database_url(database_url: str) -> str:
    """Rewrite bare Postgres URLs to the psycopg3 SQLAlchemy dialect.

    Args:
        database_url: URL from the environment or `.env`.

    Returns:
        The same URL, or `postgresql+psycopg://...` when the driver was omitted.
    """

    if database_url.startswith(POSTGRESQL_URL_PREFIX):
        remainder: str = database_url[len(POSTGRESQL_URL_PREFIX):]

        return f"{PSYCOPG3_URL_PREFIX}{remainder}"

    if database_url.startswith(POSTGRES_URL_PREFIX):
        remainder_from_postgres: str = database_url[len(POSTGRES_URL_PREFIX):]

        return f"{PSYCOPG3_URL_PREFIX}{remainder_from_postgres}"

    return database_url
