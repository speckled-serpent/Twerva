"""Upgrade and downgrade the theme-bound source revision on a clean database."""

import os
import unittest
import uuid
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.settings import clear_settings_cache
from app.sources.default_album import (
    DEFAULT_ALBUM_SLUG,
    DEFAULT_ALBUM_THEME_ID,
    default_album_source_id,
)


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
STORED_LAMP_PATH: str = "albums/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222/lamp.jpg"


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
class SourceThemeMigrationTests(unittest.TestCase):
    """Clean upgrade, downgrade, and a stored path that blocks deletion."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_phase1_{uuid.uuid4().hex[:10]}"
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

    def test_upgrade_and_downgrade_on_a_clean_database(self) -> None:
        """Head binds Default. Downgrade restores kind. Upgrade binds it again."""

        self._upgrade("head")
        self._assert_theme_bound_shape()
        self._downgrade("sources_resource_files")
        self._assert_pre_theme_shape()
        self._upgrade("head")
        self._assert_theme_bound_shape()

    def test_stored_path_blocks_deletion_then_unreferenced_rows_go(self) -> None:
        """A theme path stops the upgrade. Clearing it deletes the extra source."""

        self._upgrade("sources_resource_files")
        self._insert_resource_and_referenced_album()

        with self.assertRaises(Exception) as raised:
            self._upgrade("head")

        self.assertIn("Refusing to delete image paths", str(raised.exception))
        self._assert_pre_theme_shape()
        self._clear_stored_lamp_path()
        self._upgrade("head")

        with self._engine().connect() as connection:
            source_slugs: list[str] = [
                str(row[0])
                for row in connection.execute(text("SELECT slug FROM sources")).fetchall()
            ]
            resource_tables: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = 'resource_files'
                        """
                    ),
                ).scalar_one(),
            )

        self.assertEqual(source_slugs, [DEFAULT_ALBUM_SLUG])
        self.assertEqual(resource_tables, 0)
        self._assert_theme_bound_shape()

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

    def _assert_theme_bound_shape(self) -> None:
        """Default is bound to Paper, units are named, and kind is gone."""

        with self._engine().connect() as connection:
            source_row = connection.execute(
                text(
                    """
                    SELECT id::text, theme_id::text, slug
                    FROM sources
                    WHERE slug = :slug
                    """
                ),
                {"slug": DEFAULT_ALBUM_SLUG},
            ).one()
            unit_names: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT name
                        FROM units
                        WHERE source_id = CAST(:source_id AS uuid)
                        ORDER BY position
                        """
                    ),
                    {"source_id": str(default_album_source_id())},
                ).fetchall()
            ]
            kind_columns: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = 'sources' AND column_name = 'kind'
                        """
                    ),
                ).scalar_one(),
            )
            image_counts: list[int] = [
                int(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM unit_images
                        GROUP BY unit_id
                        """
                    ),
                ).fetchall()
            ]

        self.assertEqual(source_row[0], str(default_album_source_id()))
        self.assertEqual(source_row[1], str(DEFAULT_ALBUM_THEME_ID))
        self.assertEqual(source_row[2], DEFAULT_ALBUM_SLUG)
        self.assertEqual(unit_names[0], "Hong Kong Skyline")
        self.assertEqual(len(unit_names), 6)
        self.assertEqual(kind_columns, 0)
        self.assertTrue(all(image_count == 1 for image_count in image_counts))

    def _assert_pre_theme_shape(self) -> None:
        """The previous revision still has kind and resource_files."""

        with self._engine().connect() as connection:
            kind_column = connection.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'sources' AND column_name = 'kind'
                    """
                ),
            ).fetchone()
            resource_table = connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_name = 'resource_files'
                    """
                ),
            ).fetchone()
            theme_column = connection.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'sources' AND column_name = 'theme_id'
                    """
                ),
            ).fetchone()

        self.assertIsNotNone(kind_column)
        self.assertIsNotNone(resource_table)
        self.assertIsNone(theme_column)

    def _insert_resource_and_referenced_album(self) -> None:
        """Add a resource and an album whose image a theme still stores."""

        resource_id: str = "33333333-3333-4333-8333-333333333333"
        album_id: str = "11111111-1111-4111-8111-111111111111"
        unit_id: str = "22222222-2222-4222-8222-222222222222"
        image_id: str = "44444444-4444-4444-8444-444444444444"

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO sources (id, kind, name, slug)
                    VALUES (
                        CAST(:source_id AS uuid),
                        'resource',
                        'Bench notes',
                        'bench-notes'
                    )
                    """
                ),
                {"source_id": resource_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO resource_files (
                        source_id,
                        relative_path,
                        media_type,
                        byte_size,
                        original_filename,
                        provenance
                    )
                    VALUES (
                        CAST(:source_id AS uuid),
                        :relative_path,
                        'markdown',
                        12,
                        'notes.md',
                        'From the bench'
                    )
                    """
                ),
                {
                    "source_id": resource_id,
                    "relative_path": f"resources/{resource_id}/body.md",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO sources (id, kind, name, slug)
                    VALUES (
                        CAST(:source_id AS uuid),
                        'album',
                        'Lamps',
                        'lamps'
                    )
                    """
                ),
                {"source_id": album_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO units (id, source_id, position, free_text, tags)
                    VALUES (
                        CAST(:unit_id AS uuid),
                        CAST(:source_id AS uuid),
                        0,
                        NULL,
                        '{}'::text[]
                    )
                    """
                ),
                {"unit_id": unit_id, "source_id": album_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO unit_images (
                        id,
                        unit_id,
                        position,
                        relative_path,
                        media_type,
                        byte_size,
                        width,
                        height,
                        license,
                        source,
                        license_note,
                        intake
                    )
                    VALUES (
                        CAST(:image_id AS uuid),
                        CAST(:unit_id AS uuid),
                        0,
                        :relative_path,
                        'jpeg',
                        12,
                        8,
                        8,
                        'owned',
                        'bench',
                        '',
                        'upload'
                    )
                    """
                ),
                {
                    "image_id": image_id,
                    "unit_id": unit_id,
                    "relative_path": STORED_LAMP_PATH,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE themes
                    SET background_asset_ref = :relative_path
                    WHERE id = CAST(:theme_id AS uuid)
                    """
                ),
                {
                    "relative_path": STORED_LAMP_PATH,
                    "theme_id": str(DEFAULT_ALBUM_THEME_ID),
                },
            )

    def _clear_stored_lamp_path(self) -> None:
        """Remove the theme reference so the extra album can be deleted."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE themes
                    SET background_asset_ref = NULL
                    WHERE background_asset_ref = :relative_path
                    """
                ),
                {"relative_path": STORED_LAMP_PATH},
            )


if __name__ == "__main__":
    unittest.main()
