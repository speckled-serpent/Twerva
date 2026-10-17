"""Add research items, drop them, then add the table again."""

import os
import unittest
import uuid
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
ALBUM_REVISION: str = "albums_from_slides"
RESEARCH_REVISION: str = "research_items"
HARBOR_RESEARCH_ID: str = "11111111-1111-4111-8111-111111111111"
HARBOR_TITLE: str = "Harbor notes"
HARBOR_SLUG: str = "harbor-notes"
HARBOR_BODY: str = "A lamp sits on the quay.\nThe tide is out."


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
class ResearchItemsMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again while album rows already exist."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_research_{uuid.uuid4().hex[:10]}"
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
        """Drop the empty database and restore the previous URL."""

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

    def test_upgrade_downgrade_upgrade_keeps_existing_album_rows(self) -> None:
        """Album rows survive. Research rows do not survive the downgrade."""

        self._upgrade(RESEARCH_REVISION)
        album_slugs: list[str] = self._album_slugs()
        self.assertIn("default", album_slugs)
        self._insert_research_row()
        self._assert_research_shape(present=True)
        self._assert_body_limit()

        self._downgrade(ALBUM_REVISION)
        self.assertIsNone(self._research_table())
        self.assertEqual(self._album_slugs(), album_slugs)
        self.assertEqual(self._carousel_research_columns(), [])

        self._upgrade(RESEARCH_REVISION)
        self.assertEqual(self._research_rows(), [])
        self.assertEqual(self._album_slugs(), album_slugs)
        self._insert_research_row()
        self._assert_research_shape(present=True)

    def _insert_research_row(self) -> None:
        """Insert one document into the new table."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (
                        CAST(:research_id AS uuid),
                        :title,
                        :slug,
                        :body
                    )
                    """
                ),
                {
                    "research_id": HARBOR_RESEARCH_ID,
                    "title": HARBOR_TITLE,
                    "slug": HARBOR_SLUG,
                    "body": HARBOR_BODY,
                },
            )

    def _assert_research_shape(self, present: bool) -> None:
        """The document is stored, and the check names are not doubled."""

        rows: list[tuple[str, str, str, str]] = self._research_rows()
        check_names: set[str] = self._check_names()

        if present:
            self.assertEqual(rows, [(HARBOR_RESEARCH_ID, HARBOR_TITLE, HARBOR_SLUG, HARBOR_BODY)])
        else:
            self.assertEqual(rows, [])

        self.assertIn("ck_research_items_title", check_names)
        self.assertIn("ck_research_items_body", check_names)
        self.assertNotIn("ck_research_items_ck_research_items_title", check_names)
        self.assertNotIn("ck_research_items_ck_research_items_body", check_names)
        self.assertEqual(self._carousel_research_columns(), [])

    def _research_rows(self) -> list[tuple[str, str, str, str]]:
        """Return id, title, slug, and body."""

        with self._engine().connect() as connection:
            rows: list[tuple[str, str, str, str]] = [
                (str(row[0]), str(row[1]), str(row[2]), str(row[3]))
                for row in connection.execute(
                    text(
                        """
                        SELECT id::text, title, slug, body
                        FROM research_items
                        ORDER BY slug
                        """
                    ),
                ).fetchall()
            ]

        return rows

    def _assert_body_limit(self) -> None:
        """One million characters fit. One more character does not."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (
                        CAST(:research_id AS uuid),
                        'Limit',
                        'limit',
                        :body
                    )
                    """
                ),
                {
                    "research_id": "22222222-2222-4222-8222-222222222222",
                    "body": "a" * 1_000_000,
                },
            )

        with self.assertRaises(IntegrityError):
            with self._engine().begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO research_items (id, title, slug, body)
                        VALUES (
                            CAST(:research_id AS uuid),
                            'Over',
                            'over',
                            :body
                        )
                        """
                    ),
                    {
                        "research_id": "33333333-3333-4333-8333-333333333333",
                        "body": "b" * 1_000_001,
                    },
                )

    def _album_slugs(self) -> list[str]:
        """Return album slugs that already existed before this revision."""

        with self._engine().connect() as connection:
            slugs: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text("SELECT slug FROM albums ORDER BY slug"),
                ).fetchall()
            ]

        return slugs

    def _research_table(self) -> str | None:
        """Return the research table name, or None after downgrade."""

        with self._engine().connect() as connection:
            table_name: str | None = connection.execute(
                text("SELECT to_regclass('public.research_items')::text"),
            ).scalar_one()

        return table_name

    def _check_names(self) -> set[str]:
        """Return check-constraint names on ``research_items``."""

        with self._engine().connect() as connection:
            names: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT pg_constraint.conname
                        FROM pg_constraint
                        JOIN pg_class ON pg_class.oid = pg_constraint.conrelid
                        WHERE pg_class.relname = 'research_items'
                          AND pg_constraint.contype = 'c'
                        """
                    ),
                ).fetchall()
            }

        return names

    def _carousel_research_columns(self) -> list[str]:
        """Return carousel columns that would attach research. There are none."""

        with self._engine().connect() as connection:
            column_names: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'carousels'
                          AND column_name = 'research_id'
                        """
                    ),
                ).fetchall()
            ]

        return column_names

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


if __name__ == "__main__":
    unittest.main()
