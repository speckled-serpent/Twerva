"""Move carousels that fail the album rule from Slides to Content."""

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

from app.carousels.default_carousel import DEFAULT_ALBUM_SLUG, default_library_album_id
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
CAROUSEL_STEPS_REVISION: str = "carousel_steps"
CONTENT_REVISION: str = "carousel_editor_step_content"
EDITOR_STEP_BASIC: int = 0
EDITOR_STEP_CONTENT: int = 2
EDITOR_STEP_SLIDES: int = 3


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
class CarouselEditorStepContentMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again while carousel rows already exist."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_step_gate_{uuid.uuid4().hex[:10]}"
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

    def test_album_rule_moves_failing_carousels_to_content(self) -> None:
        """Slides stays for Default and for skeletons that need no picture.

        A picture background or an image element with a null album moves
        to Content. An attached album stays on Slides, including an album
        with no images. Research does not keep a failing carousel on
        Slides. Downgrade returns the moved rows to Slides.
        """

        self._upgrade(CAROUSEL_STEPS_REVISION)
        self._insert_rows()
        before_steps: dict[str, int] = self._editor_steps()
        before_albums: dict[str, str | None] = self._album_ids()
        before_links: int = self._research_link_count()

        self.assertEqual(before_steps[DEFAULT_ALBUM_SLUG], EDITOR_STEP_SLIDES)
        self.assertEqual(before_albums[DEFAULT_ALBUM_SLUG], str(default_library_album_id()))
        self.assertEqual(before_steps["picture-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(before_steps["picture-basic"], EDITOR_STEP_BASIC)
        self.assertEqual(before_steps["color-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(before_steps["color-basic"], EDITOR_STEP_BASIC)
        self.assertEqual(before_steps["gradient-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(before_steps["image-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(before_steps["image-album"], EDITOR_STEP_SLIDES)
        self.assertEqual(before_links, 1)

        self._upgrade(CONTENT_REVISION)
        self._assert_content_steps(before_albums, before_links)

        self._downgrade(CAROUSEL_STEPS_REVISION)
        downgraded: dict[str, int] = self._editor_steps()

        self.assertEqual(downgraded[DEFAULT_ALBUM_SLUG], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["picture-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["picture-basic"], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["image-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["image-album"], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["empty-album"], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["color-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["color-basic"], EDITOR_STEP_BASIC)
        self.assertEqual(downgraded["gradient-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["text-only"], EDITOR_STEP_SLIDES)
        self.assertEqual(self._album_ids(), before_albums)
        self.assertEqual(self._research_link_count(), before_links)

        self._upgrade(CONTENT_REVISION)
        self._assert_content_steps(before_albums, before_links)

    def _assert_content_steps(
        self,
        before_albums: dict[str, str | None],
        before_links: int,
    ) -> None:
        """Failing rows are on Content. Every other stored step is unchanged."""

        steps: dict[str, int] = self._editor_steps()

        self.assertEqual(steps[DEFAULT_ALBUM_SLUG], EDITOR_STEP_SLIDES)
        self.assertEqual(steps["picture-open"], EDITOR_STEP_CONTENT)
        self.assertEqual(steps["picture-basic"], EDITOR_STEP_CONTENT)
        self.assertEqual(steps["image-open"], EDITOR_STEP_CONTENT)
        self.assertEqual(steps["image-album"], EDITOR_STEP_SLIDES)
        self.assertEqual(steps["empty-album"], EDITOR_STEP_SLIDES)
        self.assertEqual(steps["color-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(steps["color-basic"], EDITOR_STEP_BASIC)
        self.assertEqual(steps["gradient-open"], EDITOR_STEP_SLIDES)
        self.assertEqual(steps["text-only"], EDITOR_STEP_SLIDES)
        self.assertIsNone(before_albums["picture-open"])
        self.assertIsNone(before_albums["image-open"])
        self.assertIsNotNone(before_albums["empty-album"])
        self.assertEqual(self._album_ids(), before_albums)
        self.assertEqual(self._research_link_count(), before_links)
        self.assertEqual(self._generation_numbers(), {1})

    def _insert_rows(self) -> None:
        """Add skeletons that pass and fail the album rule, all after step 3 exists."""

        picture_id: str = _uuid(1)
        color_id: str = _uuid(2)
        gradient_id: str = _uuid(3)
        image_id: str = _uuid(4)
        text_id: str = _uuid(5)
        album_id: str = _uuid(6)
        empty_album_id: str = _uuid(7)
        research_id: str = _uuid(8)

        self._insert_skeleton(picture_id, "Picture paper", "picture-paper", "picture")
        self._insert_skeleton(color_id, "Color paper", "color-paper", "color")
        self._insert_skeleton(gradient_id, "Gradient paper", "gradient-paper", "gradient")
        self._insert_skeleton(image_id, "Image paper", "image-paper", "color")
        self._insert_skeleton(text_id, "Text paper", "text-paper", "color")
        self._insert_image_element(image_id)
        self._insert_text_element(text_id)
        self._insert_album(album_id, "Harbor", "harbor-album")
        self._insert_album(empty_album_id, "Empty album", "empty-album")
        self._insert_carousel("picture-open", picture_id, None, EDITOR_STEP_SLIDES)
        self._insert_carousel("picture-basic", picture_id, None, EDITOR_STEP_BASIC)
        self._insert_carousel("color-open", color_id, None, EDITOR_STEP_SLIDES)
        self._insert_carousel("color-basic", color_id, None, EDITOR_STEP_BASIC)
        self._insert_carousel("gradient-open", gradient_id, None, EDITOR_STEP_SLIDES)
        self._insert_carousel("image-open", image_id, None, EDITOR_STEP_SLIDES)
        self._insert_carousel("image-album", image_id, album_id, EDITOR_STEP_SLIDES)
        self._insert_carousel("empty-album", picture_id, empty_album_id, EDITOR_STEP_SLIDES)
        self._insert_carousel("text-only", text_id, None, EDITOR_STEP_SLIDES)
        self._insert_research(research_id, "Plate notes", "plate-notes")
        self._attach_research("picture-open", research_id)

    def _insert_skeleton(
        self,
        skeleton_id: str,
        name: str,
        slug: str,
        background_kind: str,
    ) -> None:
        """Insert one skeleton. Spacing and status use the column defaults."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeletons (
                        id, name, slug, advertisement_type, background_kind
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        :name,
                        :slug,
                        'carousel',
                        CAST(:background_kind AS background_kind)
                    )
                    """
                ),
                {
                    "skeleton_id": skeleton_id,
                    "name": name,
                    "slug": slug,
                    "background_kind": background_kind,
                },
            )

    def _insert_image_element(self, skeleton_id: str) -> None:
        """Add one image element so a color background still needs an album."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeleton_elements (
                        skeleton_id, band, sort_order, content_kind, name, image_asset_ref
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        'middle'::skeleton_element_band,
                        0,
                        'image'::skeleton_element_content_kind,
                        'Photo',
                        'theme-defaults/photo.jpg'
                    )
                    """
                ),
                {"skeleton_id": skeleton_id},
            )

    def _insert_text_element(self, skeleton_id: str) -> None:
        """Add one text element. Text does not fail the album rule."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeleton_elements (
                        skeleton_id, band, sort_order, content_kind, name,
                        font_family, font_size, font_color, alignment
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        'top'::skeleton_element_band,
                        0,
                        'text'::skeleton_element_content_kind,
                        'Title',
                        'DejaVu Sans',
                        64,
                        '#112233',
                        'left'::skeleton_element_alignment
                    )
                    """
                ),
                {"skeleton_id": skeleton_id},
            )

    def _insert_album(self, album_id: str, name: str, slug: str) -> None:
        """Insert an album with no images."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO albums (id, name, slug)
                    VALUES (CAST(:album_id AS uuid), :name, :slug)
                    """
                ),
                {"album_id": album_id, "name": name, "slug": slug},
            )

    def _insert_carousel(
        self,
        slug: str,
        skeleton_id: str,
        album_id: str | None,
        editor_step: int,
    ) -> None:
        """Insert one carousel on a chosen step. Generation stays at the default."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        skeleton_id, name, slug, album_id, editor_step
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        :name,
                        :slug,
                        CAST(:album_id AS uuid),
                        :editor_step
                    )
                    """
                ),
                {
                    "skeleton_id": skeleton_id,
                    "name": slug,
                    "slug": slug,
                    "album_id": album_id,
                    "editor_step": editor_step,
                },
            )

    def _insert_research(self, research_id: str, title: str, slug: str) -> None:
        """Insert one research document. The body may be empty."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (CAST(:research_id AS uuid), :title, :slug, '')
                    """
                ),
                {"research_id": research_id, "title": title, "slug": slug},
            )

    def _attach_research(self, carousel_slug: str, research_id: str) -> None:
        """Link one research document. The album rule does not read it."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_research_items (
                        carousel_id, research_item_id, position
                    )
                    SELECT id, CAST(:research_id AS uuid), 0
                    FROM carousels
                    WHERE slug = :slug
                    """
                ),
                {"research_id": research_id, "slug": carousel_slug},
            )

    def _editor_steps(self) -> dict[str, int]:
        """Return editor_step keyed by carousel slug."""

        with self.database_engine.connect() as connection:
            steps: dict[str, int] = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    text("SELECT slug, editor_step FROM carousels"),
                ).fetchall()
            }

        return steps

    def _album_ids(self) -> dict[str, str | None]:
        """Return album id keyed by carousel slug."""

        with self.database_engine.connect() as connection:
            album_ids: dict[str, str | None] = {
                str(row[0]): None if row[1] is None else str(row[1])
                for row in connection.execute(
                    text("SELECT slug, album_id::text FROM carousels"),
                ).fetchall()
            }

        return album_ids

    def _generation_numbers(self) -> set[int]:
        """Return the distinct generation numbers. The revision does not change them."""

        with self.database_engine.connect() as connection:
            generations: set[int] = {
                int(row[0])
                for row in connection.execute(
                    text("SELECT DISTINCT generation_number FROM carousels"),
                ).fetchall()
            }

        return generations

    def _research_link_count(self) -> int:
        """Return how many research links exist."""

        with self.database_engine.connect() as connection:
            link_count: int = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM carousel_research_items"),
                ).scalar_one(),
            )

        return link_count

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


def _uuid(index: int) -> str:
    """Return a stable uuid for one fixture row."""

    return f"aaaaaaaa-aaaa-4aaa-8aaa-{index:012d}"
