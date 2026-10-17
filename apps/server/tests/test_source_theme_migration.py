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

    def test_free_text_and_fields_land_on_theme_text_elements(self) -> None:
        """Free text then field values fill text elements. Downgrade keeps the first."""

        self._upgrade("sources_theme_bound")
        theme_id: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        top_element_id: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        bottom_element_id: str = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        source_id: str = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        unit_id: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
        self._insert_text_unit(
            theme_id,
            top_element_id,
            bottom_element_id,
            source_id,
            unit_id,
        )
        self._upgrade("head")

        with self._engine().connect() as connection:
            stored_rows = connection.execute(
                text(
                    """
                    SELECT skeleton_element_id::text, value
                    FROM slide_element_texts
                    WHERE slide_id = CAST(:unit_id AS uuid)
                    """
                ),
                {"unit_id": unit_id},
            ).fetchall()
            free_text_columns: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = 'slides' AND column_name = 'free_text'
                        """
                    ),
                ).scalar_one(),
            )
            field_tables: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = 'unit_fields'
                        """
                    ),
                ).scalar_one(),
            )
            stored_names = connection.execute(
                text(
                    """
                    SELECT id::text, name
                    FROM skeleton_elements
                    WHERE skeleton_id = CAST(:theme_id AS uuid)
                    """
                ),
                {"theme_id": theme_id},
            ).fetchall()

        stored_by_element: dict[str, str] = {
            str(stored_row[0]): str(stored_row[1]) for stored_row in stored_rows
        }

        self.assertEqual(stored_by_element[top_element_id], "Fog line")
        self.assertEqual(stored_by_element[bottom_element_id], "Field one")
        self.assertEqual(len(stored_by_element), 2)
        names_by_element: dict[str, str] = {
            str(stored_name[0]): str(stored_name[1]) for stored_name in stored_names
        }

        self.assertEqual(names_by_element[top_element_id], "Interest heading")
        self.assertEqual(names_by_element[bottom_element_id], "Title")
        self.assertEqual(free_text_columns, 0)
        self.assertEqual(field_tables, 0)

        self._downgrade("sources_theme_bound")

        with self._engine().connect() as connection:
            restored = connection.execute(
                text(
                    """
                    SELECT free_text, tags::text
                    FROM units
                    WHERE id = CAST(:unit_id AS uuid)
                    """
                ),
                {"unit_id": unit_id},
            ).one()
            field_count: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM unit_fields
                        WHERE unit_id = CAST(:unit_id AS uuid)
                        """
                    ),
                    {"unit_id": unit_id},
                ).scalar_one(),
            )

        self.assertEqual(restored[0], "Fog line")
        self.assertEqual(restored[1], "{}")
        self.assertEqual(field_count, 0)

    def test_deleting_a_unit_removes_exclusion_rows(self) -> None:
        """Both directions disappear when either unit is deleted."""

        self._upgrade("head")
        source_id: str = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        harbor_id: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
        desert_id: str = "ffffffff-ffff-4fff-8fff-ffffffffffff"

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (id, skeleton_id, name, slug)
                    VALUES (
                        CAST(:source_id AS uuid),
                        CAST(:theme_id AS uuid),
                        'Pairs',
                        'pairs'
                    )
                    """
                ),
                {
                    "source_id": source_id,
                    "theme_id": str(DEFAULT_ALBUM_THEME_ID),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slides (id, carousel_id, position, name)
                    VALUES
                        (CAST(:harbor_id AS uuid), CAST(:source_id AS uuid), 0, 'Harbor'),
                        (CAST(:desert_id AS uuid), CAST(:source_id AS uuid), 1, 'Desert')
                    """
                ),
                {
                    "source_id": source_id,
                    "harbor_id": harbor_id,
                    "desert_id": desert_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slide_exclusions (id, slide_id, excluded_slide_id)
                    VALUES
                        (
                            CAST(:forward_id AS uuid),
                            CAST(:harbor_id AS uuid),
                            CAST(:desert_id AS uuid)
                        ),
                        (
                            CAST(:backward_id AS uuid),
                            CAST(:desert_id AS uuid),
                            CAST(:harbor_id AS uuid)
                        )
                    """
                ),
                {
                    "harbor_id": harbor_id,
                    "desert_id": desert_id,
                    "forward_id": "11111111-1111-4111-8111-111111111111",
                    "backward_id": "22222222-2222-4222-8222-222222222222",
                },
            )
            connection.execute(
                text("DELETE FROM slides WHERE id = CAST(:harbor_id AS uuid)"),
                {"harbor_id": harbor_id},
            )
            remaining: int = int(
                connection.execute(text("SELECT COUNT(*) FROM slide_exclusions")).scalar_one(),
            )

        self.assertEqual(remaining, 0)
        self._downgrade("unit_element_texts")

        with self._engine().connect() as connection:
            exclusion_tables: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = 'unit_exclusions'
                        """
                    ),
                ).scalar_one(),
            )

        self.assertEqual(exclusion_tables, 0)

    def test_existing_units_stay_live_and_downgrade_drops_drafts(self) -> None:
        """Inspiration defaults empty. Existing units stay live. Downgrade drops both."""

        self._upgrade("head")
        source_id: str = "abababab-abab-4aba-8aba-abababababab"
        unit_id: str = "cdcdcdcd-cdcd-4cdc-8cdc-cdcdcdcdcdcd"

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (id, skeleton_id, name, slug)
                    VALUES (
                        CAST(:source_id AS uuid),
                        CAST(:theme_id AS uuid),
                        'Guidance',
                        'guidance'
                    )
                    """
                ),
                {
                    "source_id": source_id,
                    "theme_id": str(DEFAULT_ALBUM_THEME_ID),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slides (id, carousel_id, position, name)
                    VALUES (
                        CAST(:unit_id AS uuid),
                        CAST(:source_id AS uuid),
                        0,
                        'Harbor'
                    )
                    """
                ),
                {"unit_id": unit_id, "source_id": source_id},
            )
            inspiration: str = str(
                connection.execute(
                    text("SELECT inspiration FROM carousels WHERE slug = 'guidance'"),
                ).scalar_one(),
            )
            text_status: str = str(
                connection.execute(
                    text("SELECT text_status::text FROM slides WHERE name = 'Harbor'"),
                ).scalar_one(),
            )

        self.assertEqual(inspiration, "")
        self.assertEqual(text_status, "live")
        self._downgrade("unit_exclusions")

        with self._engine().connect() as connection:
            inspiration_columns: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = 'sources'
                          AND column_name = 'inspiration'
                        """
                    ),
                ).scalar_one(),
            )

        self.assertEqual(inspiration_columns, 0)

    def test_existing_campaigns_keep_a_null_theme_and_source(self) -> None:
        """A campaign saved before this phase is kept, with both new columns empty."""

        self._upgrade("head")
        campaign_id: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO campaigns (
                        id,
                        name,
                        slug,
                        hashtag,
                        campaign_type,
                        advertisement_type,
                        status,
                        platforms
                    )
                    VALUES (
                        CAST(:campaign_id AS uuid),
                        'Old harbor',
                        'old-harbor',
                        '#old-harbor',
                        'spotmu',
                        'carousel',
                        'ready',
                        '[]'::jsonb
                    )
                    """
                ),
                {"campaign_id": campaign_id},
            )
            stored_theme_id: object | None = connection.execute(
                text("SELECT skeleton_id FROM campaigns WHERE slug = 'old-harbor'"),
            ).scalar_one()
            stored_source_id: object | None = connection.execute(
                text("SELECT carousel_id FROM campaigns WHERE slug = 'old-harbor'"),
            ).scalar_one()

        self.assertIsNone(stored_theme_id)
        self.assertIsNone(stored_source_id)
        self._downgrade("unit_text_drafts")

        with self._engine().connect() as connection:
            theme_columns: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = 'campaigns'
                          AND column_name = 'theme_id'
                        """
                    ),
                ).scalar_one(),
            )
            carousel_tables: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = 'campaign_carousels'
                        """
                    ),
                ).scalar_one(),
            )

        self.assertEqual(theme_columns, 0)
        self.assertEqual(carousel_tables, 0)

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
                for row in connection.execute(text("SELECT slug FROM carousels")).fetchall()
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
                    SELECT id::text, skeleton_id::text, slug
                    FROM carousels
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
                        FROM slides
                        WHERE carousel_id = CAST(:source_id AS uuid)
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
                        WHERE table_name = 'carousels' AND column_name = 'kind'
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
                        FROM slide_images
                        GROUP BY slide_id
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

    def _insert_text_unit(
        self,
        theme_id: str,
        top_element_id: str,
        bottom_element_id: str,
        source_id: str,
        unit_id: str,
    ) -> None:
        """Add a theme with two text elements and a unit that still has free text."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO themes (
                        id,
                        name,
                        slug,
                        advertisement_type,
                        template_key,
                        status,
                        page_margin,
                        element_gap,
                        element_margin,
                        background_kind,
                        background_color,
                        background_gradient,
                        background_asset_ref,
                        created_by
                    )
                    SELECT
                        CAST(:theme_id AS uuid),
                        'Copy theme',
                        'copy-theme',
                        advertisement_type,
                        NULL,
                        status,
                        page_margin,
                        element_gap,
                        element_margin,
                        background_kind,
                        background_color,
                        background_gradient,
                        background_asset_ref,
                        created_by
                    FROM themes
                    WHERE id = CAST(:paper_id AS uuid)
                    """
                ),
                {
                    "theme_id": theme_id,
                    "paper_id": str(DEFAULT_ALBUM_THEME_ID),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO theme_elements (
                        id,
                        theme_id,
                        band,
                        sort_order,
                        content_kind,
                        text_source,
                        font_family,
                        font_size,
                        font_color,
                        alignment
                    )
                    VALUES
                        (
                            CAST(:top_element_id AS uuid),
                            CAST(:theme_id AS uuid),
                            'top',
                            0,
                            'text',
                            'interest_heading',
                            'DejaVu Sans',
                            48,
                            '#112233',
                            'left'
                        ),
                        (
                            CAST(:bottom_element_id AS uuid),
                            CAST(:theme_id AS uuid),
                            'bottom',
                            0,
                            'text',
                            'title',
                            'DejaVu Sans',
                            64,
                            '#112233',
                            'left'
                        )
                    """
                ),
                {
                    "theme_id": theme_id,
                    "top_element_id": top_element_id,
                    "bottom_element_id": bottom_element_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO sources (id, theme_id, name, slug)
                    VALUES (
                        CAST(:source_id AS uuid),
                        CAST(:theme_id AS uuid),
                        'Copy shelf',
                        'copy-shelf'
                    )
                    """
                ),
                {"source_id": source_id, "theme_id": theme_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO units (id, source_id, position, name, free_text, tags)
                    VALUES (
                        CAST(:unit_id AS uuid),
                        CAST(:source_id AS uuid),
                        0,
                        'Harbor note',
                        'Fog line',
                        ARRAY['dropped']::text[]
                    )
                    """
                ),
                {"unit_id": unit_id, "source_id": source_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO unit_fields (id, unit_id, position, label, value)
                    VALUES
                        (
                            CAST(:first_field_id AS uuid),
                            CAST(:unit_id AS uuid),
                            0,
                            'Line',
                            'Field one'
                        ),
                        (
                            CAST(:second_field_id AS uuid),
                            CAST(:unit_id AS uuid),
                            1,
                            'Extra',
                            'Dropped line'
                        )
                    """
                ),
                {
                    "unit_id": unit_id,
                    "first_field_id": "ffffffff-ffff-4fff-8fff-fffffffffff1",
                    "second_field_id": "ffffffff-ffff-4fff-8fff-fffffffffff2",
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
