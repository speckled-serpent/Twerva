"""Move existing slide images onto albums, then back, then forward again."""

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

from app.carousels.default_carousel import (
    DEFAULT_ALBUM_SLUG,
    default_album_carousel_id,
    default_library_album_id,
)
from app.settings import clear_settings_cache
from app.skeletons.default_images import DEFAULT_ALBUM_NAME


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
PRE_ALBUM_REVISION: str = "skeletons_carousels_slides"
ALBUM_REVISION: str = "albums_from_slides"
HARBOR_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"
HARBOR_SLIDE_ID: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1"
HARBOR_IMAGE_ID: str = "cccccccc-cccc-4ccc-8ccc-ccccccccccc1"
HARBOR_SLUG: str = "harbor-lamps"
HARBOR_NAME: str = "Harbor lamps"
HARBOR_PATH: str = (
    "albums/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1/"
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1/"
    "cccccccc-cccc-4ccc-8ccc-ccccccccccc1.jpg"
)
EMPTY_CAROUSEL_ID: str = "dddddddd-dddd-4ddd-8ddd-ddddddddddd1"
EMPTY_SLIDE_ID: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee1"
EMPTY_SLUG: str = "empty-notes"


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
class AlbumsFromSlidesMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again with rows that already exist."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_albums_{uuid.uuid4().hex[:10]}"
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

    def test_upgrade_downgrade_upgrade_keeps_existing_image_rows(self) -> None:
        """Ids and paths survive the move onto albums and the move back."""

        self._upgrade(PRE_ALBUM_REVISION)
        self._insert_existing_rows()
        before_images: list[tuple[str, str, str, str]] = self._slide_image_rows()
        before_backgrounds: list[tuple[str, str]] = self._skeleton_backgrounds()
        self.assertGreaterEqual(len(before_images), 7)

        self._upgrade(ALBUM_REVISION)
        self._assert_album_shape(before_images, before_backgrounds)

        self._downgrade(PRE_ALBUM_REVISION)
        self._assert_slide_image_shape(before_images, before_backgrounds)

        self._upgrade(ALBUM_REVISION)
        self._assert_album_shape(before_images, before_backgrounds)

    def _insert_existing_rows(self) -> None:
        """Add one carousel with an image and one carousel with none."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, inspiration, rules
                    )
                    SELECT
                        CAST(:carousel_id AS uuid),
                        skeleton_id,
                        :name,
                        :slug,
                        '',
                        ''
                    FROM carousels
                    WHERE slug = :default_slug
                    """
                ),
                {
                    "carousel_id": HARBOR_CAROUSEL_ID,
                    "name": HARBOR_NAME,
                    "slug": HARBOR_SLUG,
                    "default_slug": DEFAULT_ALBUM_SLUG,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, inspiration, rules
                    )
                    SELECT
                        CAST(:carousel_id AS uuid),
                        skeleton_id,
                        'Empty notes',
                        :slug,
                        '',
                        ''
                    FROM carousels
                    WHERE slug = :default_slug
                    """
                ),
                {
                    "carousel_id": EMPTY_CAROUSEL_ID,
                    "slug": EMPTY_SLUG,
                    "default_slug": DEFAULT_ALBUM_SLUG,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slides (id, carousel_id, position, name, text_status)
                    VALUES
                        (CAST(:harbor_slide AS uuid), CAST(:harbor_carousel AS uuid), 0, 'Lamp', 'live'),
                        (CAST(:empty_slide AS uuid), CAST(:empty_carousel AS uuid), 0, 'Notes', 'live')
                    """
                ),
                {
                    "harbor_slide": HARBOR_SLIDE_ID,
                    "harbor_carousel": HARBOR_CAROUSEL_ID,
                    "empty_slide": EMPTY_SLIDE_ID,
                    "empty_carousel": EMPTY_CAROUSEL_ID,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slide_images (
                        id,
                        slide_id,
                        position,
                        relative_path,
                        media_type,
                        byte_size,
                        width,
                        height,
                        alt_text,
                        license,
                        source,
                        license_note,
                        intake,
                        thumbnail_path
                    )
                    SELECT
                        CAST(:image_id AS uuid),
                        CAST(:slide_id AS uuid),
                        0,
                        :relative_path,
                        media_type,
                        byte_size,
                        width,
                        height,
                        'Harbor lamp',
                        license,
                        source,
                        license_note,
                        intake,
                        NULL
                    FROM slide_images
                    LIMIT 1
                    """
                ),
                {
                    "image_id": HARBOR_IMAGE_ID,
                    "slide_id": HARBOR_SLIDE_ID,
                    "relative_path": HARBOR_PATH,
                },
            )

    def _assert_album_shape(
        self,
        before_images: list[tuple[str, str, str, str]],
        before_backgrounds: list[tuple[str, str]],
    ) -> None:
        """Albums hold the same ids and paths. Empty carousels stay unattached."""

        with self._engine().connect() as connection:
            slide_image_tables: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = 'slide_images'
                        """
                    ),
                ).scalar_one(),
            )
            default_album = connection.execute(
                text(
                    """
                    SELECT id::text, name, slug
                    FROM albums
                    WHERE slug = :slug
                    """
                ),
                {"slug": DEFAULT_ALBUM_SLUG},
            ).one()
            default_carousel_album: str | None = connection.execute(
                text(
                    """
                    SELECT album_id::text
                    FROM carousels
                    WHERE id = CAST(:carousel_id AS uuid)
                    """
                ),
                {"carousel_id": str(default_album_carousel_id())},
            ).scalar_one()
            harbor_album = connection.execute(
                text(
                    """
                    SELECT albums.id::text, albums.name, albums.slug, carousels.album_id::text
                    FROM albums
                    JOIN carousels ON carousels.album_id = albums.id
                    WHERE carousels.id = CAST(:carousel_id AS uuid)
                    """
                ),
                {"carousel_id": HARBOR_CAROUSEL_ID},
            ).one()
            empty_album_id: str | None = connection.execute(
                text(
                    """
                    SELECT album_id::text
                    FROM carousels
                    WHERE id = CAST(:carousel_id AS uuid)
                    """
                ),
                {"carousel_id": EMPTY_CAROUSEL_ID},
            ).scalar_one()
            empty_album_count: int = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM albums WHERE slug = :slug"),
                    {"slug": EMPTY_SLUG},
                ).scalar_one(),
            )
            album_images: dict[str, str] = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    text("SELECT id::text, relative_path FROM album_images"),
                ).fetchall()
            }
            slide_pointers: dict[str, str] = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    text(
                        """
                        SELECT id::text, album_image_id::text
                        FROM slides
                        WHERE album_image_id IS NOT NULL
                        """
                    ),
                ).fetchall()
            }
            check_names: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT pg_constraint.conname
                        FROM pg_constraint
                        JOIN pg_class ON pg_class.oid = pg_constraint.conrelid
                        WHERE pg_class.relname IN ('albums', 'album_images')
                          AND pg_constraint.contype = 'c'
                        """
                    ),
                ).fetchall()
            }
            backgrounds: list[tuple[str, str]] = self._skeleton_backgrounds()

        self.assertEqual(slide_image_tables, 0)
        self.assertEqual(default_album[0], str(default_library_album_id()))
        self.assertEqual(default_album[1], DEFAULT_ALBUM_NAME)
        self.assertEqual(default_album[2], DEFAULT_ALBUM_SLUG)
        self.assertEqual(default_carousel_album, str(default_library_album_id()))
        self.assertEqual(harbor_album[1], HARBOR_NAME)
        self.assertEqual(harbor_album[2], HARBOR_SLUG)
        self.assertEqual(harbor_album[3], harbor_album[0])
        self.assertIsNone(empty_album_id)
        self.assertEqual(empty_album_count, 0)
        self.assertEqual(len(album_images), len(before_images))
        self.assertIn("ck_albums_name", check_names)
        self.assertIn("ck_album_images_position", check_names)
        self.assertNotIn("ck_albums_ck_albums_name", check_names)
        self.assertNotIn("ck_album_images_ck_album_images_position", check_names)
        self.assertEqual(backgrounds, before_backgrounds)

        for image_id, relative_path, slide_id, carousel_slug in before_images:
            self.assertEqual(album_images[image_id], relative_path)
            self.assertEqual(slide_pointers[slide_id], image_id)
            self.assertTrue(
                relative_path.startswith("theme-defaults/") or relative_path == HARBOR_PATH,
            )
            self.assertIn(carousel_slug, {DEFAULT_ALBUM_SLUG, HARBOR_SLUG})

        self.assertEqual(album_images[HARBOR_IMAGE_ID], HARBOR_PATH)
        self.assertTrue(
            all(
                path.startswith("theme-defaults/")
                for image_id, path in album_images.items()
                if image_id != HARBOR_IMAGE_ID
            ),
        )

    def _assert_slide_image_shape(
        self,
        before_images: list[tuple[str, str, str, str]],
        before_backgrounds: list[tuple[str, str]],
    ) -> None:
        """Downgrade restores slide_images and drops album tables."""

        with self._engine().connect() as connection:
            restored: dict[str, tuple[str, str, int]] = {
                str(row[0]): (str(row[1]), str(row[2]), int(row[3]))
                for row in connection.execute(
                    text(
                        """
                        SELECT id::text, slide_id::text, relative_path, position
                        FROM slide_images
                        """
                    ),
                ).fetchall()
            }
            album_tables: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name IN ('albums', 'album_images')
                        """
                    ),
                ).scalar_one(),
            )
            album_columns: int = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE column_name IN ('album_id', 'album_image_id')
                          AND table_name IN ('carousels', 'slides')
                        """
                    ),
                ).scalar_one(),
            )
            backgrounds: list[tuple[str, str]] = self._skeleton_backgrounds()

        self.assertEqual(album_tables, 0)
        self.assertEqual(album_columns, 0)
        self.assertEqual(len(restored), len(before_images))
        self.assertEqual(backgrounds, before_backgrounds)

        for image_id, relative_path, slide_id, _carousel_slug in before_images:
            restored_slide_id, restored_path, restored_position = restored[image_id]
            self.assertEqual(restored_slide_id, slide_id)
            self.assertEqual(restored_path, relative_path)
            self.assertEqual(restored_position, 0)

    def _slide_image_rows(self) -> list[tuple[str, str, str, str]]:
        """Return image id, path, slide id, and carousel slug before the move."""

        with self._engine().connect() as connection:
            rows: list[tuple[str, str, str, str]] = [
                (str(row[0]), str(row[1]), str(row[2]), str(row[3]))
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            slide_images.id::text,
                            slide_images.relative_path,
                            slides.id::text,
                            carousels.slug
                        FROM slide_images
                        JOIN slides ON slides.id = slide_images.slide_id
                        JOIN carousels ON carousels.id = slides.carousel_id
                        ORDER BY carousels.slug, slides.position, slide_images.position
                        """
                    ),
                ).fetchall()
            ]

        return rows

    def _skeleton_backgrounds(self) -> list[tuple[str, str]]:
        """Return skeleton id and stored background path, including blanks."""

        with self._engine().connect() as connection:
            rows: list[tuple[str, str]] = [
                (str(row[0]), "" if row[1] is None else str(row[1]))
                for row in connection.execute(
                    text(
                        """
                        SELECT id::text, background_asset_ref
                        FROM skeletons
                        ORDER BY id::text
                        """
                    ),
                ).fetchall()
            ]

        return rows

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
