"""Add carousel step columns, drop them, then add them again."""

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

from app.carousels.default_carousel import (
    DEFAULT_ALBUM_SLUG,
    default_album_carousel_id,
    default_library_album_id,
)
from app.models.carousel import Carousel
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
RESEARCH_REVISION: str = "research_items"
CAROUSEL_STEPS_REVISION: str = "carousel_steps"
HARBOR_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"
HARBOR_ALBUM_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2"
HARBOR_SLIDE_ID: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1"
HARBOR_IMAGE_ID: str = "cccccccc-cccc-4ccc-8ccc-ccccccccccc1"
HARBOR_SLUG: str = "harbor-lamps"
HARBOR_NAME: str = "Harbor lamps"
HARBOR_INSPIRATION: str = "A lamp on the quay"
HARBOR_RULES: str = "Keep the tide in the caption"
HARBOR_PATH: str = (
    "albums/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1/"
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1/"
    "cccccccc-cccc-4ccc-8ccc-ccccccccccc1.jpg"
)
EMPTY_CAROUSEL_ID: str = "dddddddd-dddd-4ddd-8ddd-ddddddddddd1"
EMPTY_SLIDE_ID: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee1"
EMPTY_SLUG: str = "empty-notes"
HARBOR_RESEARCH_ID: str = "11111111-1111-4111-8111-111111111111"
HARBOR_RESEARCH_SLUG: str = "harbor-notes"
CASCADE_RESEARCH_ID: str = "22222222-2222-4222-8222-222222222222"
CASCADE_CAROUSEL_ID: str = "33333333-3333-4333-8333-333333333333"
LINK_ID: str = "44444444-4444-4444-8444-444444444444"

CarouselSnapshot = tuple[str, str | None, str, str]
SlideSnapshot = tuple[str, str, str | None]


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
class CarouselStepsMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again while carousel rows already exist."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_steps_{uuid.uuid4().hex[:10]}"
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
        self.database_engine: Engine = create_engine(self.database_url)

    def tearDown(self) -> None:
        """Drop the empty database and restore the previous URL."""

        clear_settings_cache()
        self.database_engine.dispose()

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

    def test_upgrade_downgrade_upgrade_keeps_existing_carousel_rows(self) -> None:
        """Albums, slides, and research survive. The new link starts empty."""

        self._upgrade(RESEARCH_REVISION)
        self._insert_existing_rows()
        before_carousels: list[CarouselSnapshot] = self._carousel_rows()
        before_slides: list[SlideSnapshot] = self._slide_pointers()
        before_research: list[str] = self._research_slugs()

        self._upgrade(CAROUSEL_STEPS_REVISION)
        self._assert_step_shape(before_carousels, before_slides, before_research)
        self._assert_checks_and_cascades()

        self._downgrade(RESEARCH_REVISION)
        self._assert_downgraded(before_carousels, before_slides, before_research)

        self._upgrade(CAROUSEL_STEPS_REVISION)
        self._assert_step_shape(before_carousels, before_slides, before_research)

    def _insert_existing_rows(self) -> None:
        """Add one carousel with an album, one with none, and one research item."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO albums (id, name, slug)
                    VALUES (CAST(:album_id AS uuid), :name, :slug)
                    """
                ),
                {
                    "album_id": HARBOR_ALBUM_ID,
                    "name": HARBOR_NAME,
                    "slug": HARBOR_SLUG,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, inspiration, rules, album_id
                    )
                    SELECT
                        CAST(:carousel_id AS uuid),
                        skeleton_id,
                        :name,
                        :slug,
                        :inspiration,
                        :rules,
                        CAST(:album_id AS uuid)
                    FROM carousels
                    WHERE slug = :default_slug
                    """
                ),
                {
                    "carousel_id": HARBOR_CAROUSEL_ID,
                    "name": HARBOR_NAME,
                    "slug": HARBOR_SLUG,
                    "inspiration": HARBOR_INSPIRATION,
                    "rules": HARBOR_RULES,
                    "album_id": HARBOR_ALBUM_ID,
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
                    INSERT INTO album_images (
                        id, album_id, position, relative_path, media_type,
                        byte_size, width, height, license, source, intake
                    )
                    VALUES (
                        CAST(:image_id AS uuid),
                        CAST(:album_id AS uuid),
                        0,
                        :relative_path,
                        'jpeg',
                        1200,
                        80,
                        60,
                        'cc0',
                        'https://example.com/harbor.jpg',
                        'upload'
                    )
                    """
                ),
                {
                    "image_id": HARBOR_IMAGE_ID,
                    "album_id": HARBOR_ALBUM_ID,
                    "relative_path": HARBOR_PATH,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slides (
                        id, carousel_id, position, name, text_status, album_image_id
                    )
                    VALUES (
                        CAST(:slide_id AS uuid),
                        CAST(:carousel_id AS uuid),
                        0,
                        'Lamp',
                        'live',
                        CAST(:image_id AS uuid)
                    )
                    """
                ),
                {
                    "slide_id": HARBOR_SLIDE_ID,
                    "carousel_id": HARBOR_CAROUSEL_ID,
                    "image_id": HARBOR_IMAGE_ID,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slides (id, carousel_id, position, name, text_status)
                    VALUES (
                        CAST(:slide_id AS uuid),
                        CAST(:carousel_id AS uuid),
                        0,
                        'Notes',
                        'live'
                    )
                    """
                ),
                {
                    "slide_id": EMPTY_SLIDE_ID,
                    "carousel_id": EMPTY_CAROUSEL_ID,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (
                        CAST(:research_id AS uuid),
                        'Harbor notes',
                        :slug,
                        'The tide is out.'
                    )
                    """
                ),
                {
                    "research_id": HARBOR_RESEARCH_ID,
                    "slug": HARBOR_RESEARCH_SLUG,
                },
            )

    def _assert_step_shape(
        self,
        before_carousels: list[CarouselSnapshot],
        before_slides: list[SlideSnapshot],
        before_research: list[str],
    ) -> None:
        """Every carousel is generation 1 on Slides, and nothing else moved."""

        carousels: dict[str, tuple[str | None, str, str, int, int, str]] = self._step_rows()
        slides: list[SlideSnapshot] = self._slide_pointers()
        check_names: set[str] = self._check_names("carousels")
        link_checks: set[str] = self._check_names("carousel_research_items")
        defaults: dict[str, str] = self._column_defaults()
        default_id: str = str(default_album_carousel_id())
        default_slides: list[SlideSnapshot] = [
            slide for slide in slides if slide[1] == default_id and slide[2] is not None
        ]

        self.assertEqual(self._research_link_count(), 0)
        self.assertEqual(self._research_id_columns(), [])
        self.assertNotIn("research_id", set(Carousel.__table__.columns.keys()))
        self.assertEqual(slides, before_slides)
        self.assertEqual(self._research_slugs(), before_research)
        self.assertEqual(len(default_slides), 6)
        self.assertEqual(carousels[default_id][0], str(default_library_album_id()))
        self.assertEqual(carousels[HARBOR_CAROUSEL_ID][0], HARBOR_ALBUM_ID)
        self.assertEqual(carousels[HARBOR_CAROUSEL_ID][1], HARBOR_INSPIRATION)
        self.assertEqual(carousels[HARBOR_CAROUSEL_ID][2], HARBOR_RULES)
        self.assertIsNone(carousels[EMPTY_CAROUSEL_ID][0])
        self.assertIn("ck_carousels_generation_number", check_names)
        self.assertIn("ck_carousels_editor_step", check_names)
        self.assertNotIn("ck_carousels_ck_carousels_generation_number", check_names)
        self.assertNotIn("ck_carousels_ck_carousels_editor_step", check_names)
        self.assertIn("ck_carousel_research_items_position", link_checks)
        self.assertNotIn(
            "ck_carousel_research_items_ck_carousel_research_items_position",
            link_checks,
        )
        self.assertEqual(_default_number(defaults["generation_number"]), "1")
        self.assertEqual(_default_number(defaults["editor_step"]), "3")
        self.assertEqual(self._delete_actions(), {"carousel_id": "c", "research_item_id": "c"})

        steps_by_slug: dict[str, tuple[str | None, str, str, int, int, str]] = {
            step_row[5]: step_row for step_row in carousels.values()
        }

        for slug, album_id, inspiration, rules in before_carousels:
            step_row: tuple[str | None, str, str, int, int, str] = steps_by_slug[slug]

            self.assertEqual(step_row[0], album_id)
            self.assertEqual(step_row[1], inspiration)
            self.assertEqual(step_row[2], rules)
            self.assertEqual(step_row[3], 1)
            self.assertEqual(step_row[4], 3)

    def _assert_downgraded(
        self,
        before_carousels: list[CarouselSnapshot],
        before_slides: list[SlideSnapshot],
        before_research: list[str],
    ) -> None:
        """The join and the two columns are gone. The older rows stay."""

        self.assertIsNone(self._regclass("carousel_research_items"))
        self.assertEqual(self._step_column_names(), [])
        self.assertEqual(self._research_id_columns(), [])
        self.assertIsNotNone(self._regclass("research_items"))
        self.assertIsNotNone(self._regclass("albums"))
        self.assertIsNotNone(self._regclass("slides"))
        self.assertEqual(self._carousel_rows(), before_carousels)
        self.assertEqual(self._slide_pointers(), before_slides)
        self.assertEqual(self._research_slugs(), before_research)

    def _assert_checks_and_cascades(self) -> None:
        """Allowed steps save. A bad step, a duplicate link, and deletes follow the keys."""

        self._set_step(HARBOR_CAROUSEL_ID, generation_number=2, editor_step=0)
        self._set_step(HARBOR_CAROUSEL_ID, generation_number=1, editor_step=2)
        self._set_step(HARBOR_CAROUSEL_ID, generation_number=1, editor_step=3)
        self._assert_rejected_step(generation_number=0, editor_step=3)
        self._assert_rejected_step(generation_number=1, editor_step=1)
        self._assert_rejected_step(generation_number=1, editor_step=4)

        self._insert_research(CASCADE_RESEARCH_ID, "cascade-notes")
        self._insert_link(LINK_ID, HARBOR_CAROUSEL_ID, CASCADE_RESEARCH_ID, 0)
        self._assert_rejected_link(
            "55555555-5555-4555-8555-555555555555",
            HARBOR_CAROUSEL_ID,
            CASCADE_RESEARCH_ID,
            1,
        )
        self._assert_rejected_link(
            "66666666-6666-4666-8666-666666666666",
            HARBOR_CAROUSEL_ID,
            HARBOR_RESEARCH_ID,
            0,
        )
        self._assert_rejected_position()

        with self._engine().begin() as connection:
            connection.execute(
                text("DELETE FROM research_items WHERE id = CAST(:research_id AS uuid)"),
                {"research_id": CASCADE_RESEARCH_ID},
            )

        self.assertEqual(self._research_link_count(), 0)
        self.assertIn(HARBOR_CAROUSEL_ID, self._step_rows())

        self._insert_research(CASCADE_RESEARCH_ID, "cascade-notes")
        self._insert_carousel(CASCADE_CAROUSEL_ID, "cascade-carousel")
        self._insert_link(LINK_ID, CASCADE_CAROUSEL_ID, CASCADE_RESEARCH_ID, 0)

        with self._engine().begin() as connection:
            connection.execute(
                text("DELETE FROM carousels WHERE id = CAST(:carousel_id AS uuid)"),
                {"carousel_id": CASCADE_CAROUSEL_ID},
            )

        self.assertEqual(self._research_link_count(), 0)
        self.assertIn(CASCADE_RESEARCH_ID, self._research_ids())
        self.assertNotIn(CASCADE_CAROUSEL_ID, self._step_rows())

        with self._engine().begin() as connection:
            connection.execute(
                text("DELETE FROM research_items WHERE id = CAST(:research_id AS uuid)"),
                {"research_id": CASCADE_RESEARCH_ID},
            )

    def _set_step(
        self,
        carousel_id: str,
        generation_number: int,
        editor_step: int,
    ) -> None:
        """Store one allowed generation and editor step."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE carousels
                    SET generation_number = :generation_number,
                        editor_step = :editor_step
                    WHERE id = CAST(:carousel_id AS uuid)
                    """
                ),
                {
                    "carousel_id": carousel_id,
                    "generation_number": generation_number,
                    "editor_step": editor_step,
                },
            )

    def _assert_rejected_step(self, generation_number: int, editor_step: int) -> None:
        """A generation below 1, or a step other than 0, 2, or 3, does not save."""

        with self.assertRaises(IntegrityError):
            self._set_step(HARBOR_CAROUSEL_ID, generation_number, editor_step)

        stored: tuple[str | None, str, str, int, int, str] = (
            self._step_rows()[HARBOR_CAROUSEL_ID]
        )
        self.assertEqual(stored[3], 1)
        self.assertEqual(stored[4], 3)

    def _assert_rejected_link(
        self,
        link_id: str,
        carousel_id: str,
        research_id: str,
        position: int,
    ) -> None:
        """The same research item, or the same position, cannot be stored twice."""

        with self.assertRaises(IntegrityError):
            self._insert_link(link_id, carousel_id, research_id, position)

    def _assert_rejected_position(self) -> None:
        """A negative position does not save."""

        with self.assertRaises(IntegrityError):
            self._insert_link(
                "77777777-7777-4777-8777-777777777777",
                EMPTY_CAROUSEL_ID,
                HARBOR_RESEARCH_ID,
                -1,
            )

    def _insert_research(self, research_id: str, slug: str) -> None:
        """Insert one research document used by the cascade checks."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (CAST(:research_id AS uuid), :title, :slug, '')
                    """
                ),
                {
                    "research_id": research_id,
                    "title": slug,
                    "slug": slug,
                },
            )

    def _insert_carousel(self, carousel_id: str, slug: str) -> None:
        """Insert one carousel on Default's skeleton, with no album."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (id, skeleton_id, name, slug)
                    SELECT CAST(:carousel_id AS uuid), skeleton_id, :name, :slug
                    FROM carousels
                    WHERE slug = :default_slug
                    """
                ),
                {
                    "carousel_id": carousel_id,
                    "name": slug,
                    "slug": slug,
                    "default_slug": DEFAULT_ALBUM_SLUG,
                },
            )

    def _insert_link(
        self,
        link_id: str,
        carousel_id: str,
        research_id: str,
        position: int,
    ) -> None:
        """Insert one ordered research link."""

        with self._engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_research_items (
                        id, carousel_id, research_item_id, position
                    )
                    VALUES (
                        CAST(:link_id AS uuid),
                        CAST(:carousel_id AS uuid),
                        CAST(:research_id AS uuid),
                        :position
                    )
                    """
                ),
                {
                    "link_id": link_id,
                    "carousel_id": carousel_id,
                    "research_id": research_id,
                    "position": position,
                },
            )

    def _carousel_rows(self) -> list[CarouselSnapshot]:
        """Return slug, album id, inspiration, and rules."""

        with self._engine().connect() as connection:
            rows: list[CarouselSnapshot] = [
                (
                    str(row[0]),
                    None if row[1] is None else str(row[1]),
                    str(row[2]),
                    str(row[3]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT slug, album_id::text, inspiration, rules
                        FROM carousels
                        ORDER BY slug
                        """
                    ),
                ).fetchall()
            ]

        return rows

    def _step_rows(self) -> dict[str, tuple[str | None, str, str, int, int, str]]:
        """Return each carousel keyed by id, including generation and editor step."""

        with self._engine().connect() as connection:
            rows: dict[str, tuple[str | None, str, str, int, int, str]] = {
                str(row[0]): (
                    None if row[1] is None else str(row[1]),
                    str(row[2]),
                    str(row[3]),
                    int(row[4]),
                    int(row[5]),
                    str(row[6]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            id::text,
                            album_id::text,
                            inspiration,
                            rules,
                            generation_number,
                            editor_step,
                            slug
                        FROM carousels
                        """
                    ),
                ).fetchall()
            }

        return rows

    def _slide_pointers(self) -> list[SlideSnapshot]:
        """Return slide id, carousel id, and album image id."""

        with self._engine().connect() as connection:
            rows: list[SlideSnapshot] = [
                (
                    str(row[0]),
                    str(row[1]),
                    None if row[2] is None else str(row[2]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT id::text, carousel_id::text, album_image_id::text
                        FROM slides
                        ORDER BY carousel_id::text, position, id::text
                        """
                    ),
                ).fetchall()
            ]

        return rows

    def _research_slugs(self) -> list[str]:
        """Return research slugs that already existed."""

        with self._engine().connect() as connection:
            slugs: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text("SELECT slug FROM research_items ORDER BY slug"),
                ).fetchall()
            ]

        return slugs

    def _research_ids(self) -> set[str]:
        """Return research ids."""

        with self._engine().connect() as connection:
            research_ids: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text("SELECT id::text FROM research_items"),
                ).fetchall()
            }

        return research_ids

    def _research_link_count(self) -> int:
        """Return how many research links the upgrade inserted. It is zero."""

        with self._engine().connect() as connection:
            link_count: int = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM carousel_research_items"),
                ).scalar_one(),
            )

        return link_count

    def _research_id_columns(self) -> list[str]:
        """Return a ``research_id`` column on carousels. There is none."""

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

    def _step_column_names(self) -> list[str]:
        """Return the step columns. Downgrade removes both."""

        with self._engine().connect() as connection:
            column_names: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'carousels'
                          AND column_name IN ('generation_number', 'editor_step')
                        ORDER BY column_name
                        """
                    ),
                ).fetchall()
            ]

        return column_names

    def _column_defaults(self) -> dict[str, str]:
        """Return the server defaults for the two new columns."""

        with self._engine().connect() as connection:
            defaults: dict[str, str] = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name, column_default
                        FROM information_schema.columns
                        WHERE table_name = 'carousels'
                          AND column_name IN ('generation_number', 'editor_step')
                        """
                    ),
                ).fetchall()
            }

        return defaults

    def _check_names(self, table_name: str) -> set[str]:
        """Return check-constraint names on one table."""

        with self._engine().connect() as connection:
            names: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT pg_constraint.conname
                        FROM pg_constraint
                        JOIN pg_class ON pg_class.oid = pg_constraint.conrelid
                        WHERE pg_class.relname = :table_name
                          AND pg_constraint.contype = 'c'
                        """
                    ),
                    {"table_name": table_name},
                ).fetchall()
            }

        return names

    def _delete_actions(self) -> dict[str, str]:
        """Return Postgres ON DELETE actions for the research link."""

        with self._engine().connect() as connection:
            actions: dict[str, str] = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    text(
                        """
                        SELECT attribute.attname, pg_constraint.confdeltype
                        FROM pg_constraint
                        JOIN pg_class ON pg_class.oid = pg_constraint.conrelid
                        JOIN pg_attribute AS attribute
                          ON attribute.attrelid = pg_class.oid
                         AND attribute.attnum = pg_constraint.conkey[1]
                        WHERE pg_class.relname = 'carousel_research_items'
                          AND pg_constraint.contype = 'f'
                        """
                    ),
                ).fetchall()
            }

        return actions

    def _regclass(self, table_name: str) -> str | None:
        """Return the table name, or None when the relation is gone."""

        with self._engine().connect() as connection:
            registered_name: str | None = connection.execute(
                text("SELECT to_regclass(:table_name)::text"),
                {"table_name": f"public.{table_name}"},
            ).scalar_one()

        return registered_name

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

        return self.database_engine


def _default_number(column_default: str) -> str:
    """Return the integer inside a Postgres column default expression."""

    number_text: str = column_default.split("::", maxsplit=1)[0].strip("'")

    return number_text


if __name__ == "__main__":
    unittest.main()
