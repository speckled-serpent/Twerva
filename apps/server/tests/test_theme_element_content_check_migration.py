"""Upgrade and downgrade the optional text_source content check.

Production and a fresh database both store the check as
``ck_theme_elements_content``. A doubled name
``ck_theme_elements_ck_theme_elements_content`` is the spelling Alembic
emits when the rendered name is passed through the ``ck`` convention
again. Both shapes must land on ``ck_theme_elements_content``.
"""

import importlib.util
import os
import unittest
import uuid
from pathlib import Path
from types import ModuleType

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
PAPER_THEME_ID: str = "e8700eea-c086-5ce2-859d-b3d689af5c25"
NAMES_REVISION: str = "theme_element_names"
OPTIONAL_REVISION: str = "theme_element_text_optional"
RENDERED_CONTENT_CHECK: str = "ck_theme_elements_content"
DOUBLE_PREFIXED_CONTENT_CHECK: str = "ck_theme_elements_ck_theme_elements_content"


def _postgres_available() -> bool:
    """Return whether the local Postgres admin database accepts a connection."""

    admin_engine: Engine | None = None

    try:
        admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")

        with admin_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:

        return False
    else:

        return True
    finally:

        if admin_engine is not None:
            admin_engine.dispose()


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for migration tests")
class ThemeElementContentCheckMigrationTests(unittest.TestCase):
    """Fresh and double-prefixed databases at theme_element_names."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_content_{uuid.uuid4().hex[:10]}"
        self.database_url: str = (
            "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/"
            f"{self.database_name}"
        )
        self.previous_database_url: str | None = os.environ.get("DATABASE_URL")
        self.admin_engine: Engine = create_engine(
            ADMIN_DATABASE_URL,
            isolation_level="AUTOCOMMIT",
        )

        with self.admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{self.database_name}"'))

        os.environ["DATABASE_URL"] = self.database_url
        clear_settings_cache()

    def tearDown(self) -> None:
        """Drop the throwaway database and restore the previous URL."""

        clear_settings_cache()

        if self.previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self.previous_database_url

        clear_settings_cache()

        with self.admin_engine.connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": self.database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{self.database_name}"'))

        self.admin_engine.dispose()

    def test_fresh_database_upgrades_and_downgrades(self) -> None:
        """A database built from scratch keeps ck_theme_elements_content."""

        self._upgrade(NAMES_REVISION)
        self.assertEqual(set(self._content_checks()), {RENDERED_CONTENT_CHECK})
        self._insert_text_element(sort_order=1, text_source="title")

        self._upgrade(OPTIONAL_REVISION)
        self._assert_content_check(requires_text_source=False)
        self._insert_text_element(sort_order=2, text_source=None)

        with self.assertRaises(IntegrityError):
            self._downgrade(NAMES_REVISION)

        self._delete_text_element(sort_order=2)
        self._downgrade(NAMES_REVISION)
        self._assert_content_check(requires_text_source=True)

        with self.assertRaises(IntegrityError):
            self._insert_text_element(sort_order=3, text_source=None)

        self._insert_text_element(sort_order=3, text_source="title")
        self._upgrade(OPTIONAL_REVISION)
        self._assert_content_check(requires_text_source=False)
        self._insert_text_element(sort_order=4, text_source=None)

    def test_prod_check_sql_upgrades_and_downgrades(self) -> None:
        """Production's rendered check still requires text_source until upgrade."""

        self._upgrade(NAMES_REVISION)
        self._replace_content_check(self._requiring_text_source_sql())
        self._assert_content_check(requires_text_source=True)

        with self.assertRaises(IntegrityError):
            self._insert_text_element(sort_order=1, text_source=None)

        self._upgrade(OPTIONAL_REVISION)
        self._assert_content_check(requires_text_source=False)
        self._insert_text_element(sort_order=1, text_source=None)
        self._delete_text_element(sort_order=1)
        self._downgrade(NAMES_REVISION)
        self._assert_content_check(requires_text_source=True)

        with self.assertRaises(IntegrityError):
            self._insert_text_element(sort_order=1, text_source=None)

    def test_double_prefixed_check_upgrades_to_rendered_name(self) -> None:
        """The doubled constraint name is replaced by ck_theme_elements_content."""

        self._upgrade(NAMES_REVISION)
        self._rename_content_check(
            RENDERED_CONTENT_CHECK,
            DOUBLE_PREFIXED_CONTENT_CHECK,
        )
        self.assertEqual(
            set(self._content_checks()),
            {DOUBLE_PREFIXED_CONTENT_CHECK},
        )

        self._upgrade(OPTIONAL_REVISION)
        self._assert_content_check(requires_text_source=False)
        self._insert_text_element(sort_order=1, text_source=None)
        self._delete_text_element(sort_order=1)
        self._downgrade(NAMES_REVISION)
        self._assert_content_check(requires_text_source=True)
        self.assertNotIn(DOUBLE_PREFIXED_CONTENT_CHECK, self._content_checks())

    def _upgrade(self, revision: str) -> None:
        """Run alembic upgrade against this test database."""

        clear_settings_cache()
        command.upgrade(self._alembic_config(), revision)

    def _downgrade(self, revision: str) -> None:
        """Run alembic downgrade against this test database."""

        clear_settings_cache()
        command.downgrade(self._alembic_config(), revision)

    def _alembic_config(self) -> Config:
        """Return Alembic config for the server tree."""

        alembic_config: Config = Config(str(SERVER_ROOT / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(SERVER_ROOT / "alembic"))

        return alembic_config

    def _engine(self) -> Engine:
        """Return an engine for the throwaway database."""

        database_engine: Engine = create_engine(self.database_url)

        return database_engine

    def _content_checks(self) -> dict[str, str]:
        """Return content-check names mapped to their Postgres definitions."""

        database_engine: Engine = self._engine()

        try:

            with database_engine.connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT con.conname, pg_get_constraintdef(con.oid)
                        FROM pg_constraint AS con
                        JOIN pg_class AS rel ON rel.oid = con.conrelid
                        WHERE rel.relname = 'theme_elements'
                          AND con.contype = 'c'
                          AND con.conname LIKE '%content%'
                        """
                    ),
                ).fetchall()
        finally:
            database_engine.dispose()

        content_checks: dict[str, str] = {
            str(row[0]): str(row[1]) for row in rows
        }

        return content_checks

    def _assert_content_check(self, requires_text_source: bool) -> None:
        """The only content check is the rendered name, with the expected SQL."""

        content_checks: dict[str, str] = self._content_checks()
        definition: str = content_checks[RENDERED_CONTENT_CHECK]

        self.assertEqual(set(content_checks), {RENDERED_CONTENT_CHECK})
        self.assertEqual(
            "text_source IS NOT NULL" in definition,
            requires_text_source,
        )
        self.assertIn("text_source IS NULL", definition)

    def _requiring_text_source_sql(self) -> str:
        """Return the downgrade check, which is the SQL production still has."""

        revision_path: Path = (
            SERVER_ROOT
            / "alembic"
            / "versions"
            / "theme_element_text_optional.py"
        )
        module_spec = importlib.util.spec_from_file_location(
            "theme_element_text_optional_revision",
            revision_path,
        )

        if module_spec is None or module_spec.loader is None:
            raise RuntimeError("Content-check revision could not be loaded.")

        revision_module: ModuleType = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(revision_module)
        requiring_sql: str = revision_module.THEME_ELEMENT_CONTENT_CHECK_REQUIRING_TEXT_SOURCE_SQL

        return requiring_sql

    def _replace_content_check(self, check_sql: str) -> None:
        """Rewrite the rendered content check without going through Alembic."""

        database_engine: Engine = self._engine()

        try:

            with database_engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE theme_elements "
                        f"DROP CONSTRAINT IF EXISTS {RENDERED_CONTENT_CHECK}"
                    ),
                )
                connection.execute(
                    text(
                        "ALTER TABLE theme_elements "
                        f"ADD CONSTRAINT {RENDERED_CONTENT_CHECK} CHECK ({check_sql})"
                    ),
                )
        finally:
            database_engine.dispose()

    def _rename_content_check(self, current_name: str, next_name: str) -> None:
        """Rename one content check so the upgrade sees the other spelling."""

        database_engine: Engine = self._engine()

        try:

            with database_engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE theme_elements "
                        f"RENAME CONSTRAINT {current_name} TO {next_name}"
                    ),
                )
        finally:
            database_engine.dispose()

    def _insert_text_element(self, sort_order: int, text_source: str | None) -> None:
        """Insert one text element on the seeded Paper theme."""

        database_engine: Engine = self._engine()

        try:

            with database_engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO theme_elements (
                            theme_id,
                            band,
                            sort_order,
                            content_kind,
                            name,
                            font_family,
                            font_size,
                            font_color,
                            alignment,
                            text_source
                        ) VALUES (
                            CAST(:theme_id AS uuid),
                            'top',
                            :sort_order,
                            'text',
                            'Headline',
                            'Source Sans 3',
                            48,
                            '#112233',
                            'center',
                            CAST(:text_source AS theme_element_text_source)
                        )
                        """
                    ),
                    {
                        "theme_id": PAPER_THEME_ID,
                        "sort_order": sort_order,
                        "text_source": text_source,
                    },
                )
        finally:
            database_engine.dispose()

    def _delete_text_element(self, sort_order: int) -> None:
        """Remove one Paper-theme element so a stricter check can be restored."""

        database_engine: Engine = self._engine()

        try:

            with database_engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        DELETE FROM theme_elements
                        WHERE theme_id = CAST(:theme_id AS uuid)
                          AND sort_order = :sort_order
                        """
                    ),
                    {"theme_id": PAPER_THEME_ID, "sort_order": sort_order},
                )
        finally:
            database_engine.dispose()
