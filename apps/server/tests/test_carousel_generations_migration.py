"""Backfill one generation snapshot and hang existing assemblies on it."""

import os
import tempfile
import unittest
import uuid
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.carousels.default_carousel import (
    DEFAULT_ALBUM_SKELETON_ID,
    DEFAULT_ALBUM_SLUG,
)
from app.carousels.generations import ensure_current_generation
from app.models.carousel import Carousel
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
PREVIOUS_REVISION: str = "carousel_final_assembly"
GENERATIONS_REVISION: str = "carousel_generations"
SKELETON_ID: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb31"
ELEMENT_ID: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeee31"
CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaad01"
OTHER_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaad02"
SLIDE_ID: str = "dddddddd-dddd-4ddd-8ddd-dddddddddd31"
OTHER_SLIDE_ID: str = "dddddddd-dddd-4ddd-8ddd-dddddddddd32"
RESEARCH_ID: str = "cccccccc-cccc-4ccc-8ccc-cccccccccc31"
ASSEMBLY_ID: str = "ffffffff-ffff-4fff-8fff-ffffffffff31"
FRAME_ID: str = "ffffffff-ffff-4fff-8fff-ffffffffff32"
LATE_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaad03"
CAROUSEL_SLUG: str = "generation-probe"
OTHER_SLUG: str = "generation-other"
LATE_SLUG: str = "generation-late"
ASSET_REF: str = "assembled/probe/kept-frame.png"
INSTRUCTION_BODY: str = "Keep the harbor."
RESEARCH_TITLE: str = "Tides"
RESEARCH_BODY: str = "The water is cold."
LIVE_VALUE: str = "Reviewed line"
DRAFT_VALUE: str = "Unreviewed line"

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
class CarouselGenerationsMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again. Generation 1 is backfilled."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_gen_{uuid.uuid4().hex[:10]}"
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

    def test_upgrade_downgrade_upgrade_backfills_generation_one(self) -> None:
        """Default and a typed carousel keep their rows, and the snapshot matches."""

        self._upgrade(PREVIOUS_REVISION)
        before_default: list[SlideSnapshot] = self._slides_for_slug(DEFAULT_ALBUM_SLUG)
        before_generation: int = self._generation_number(DEFAULT_ALBUM_SLUG)
        before_artifacts: int = self._row_count("artifacts")
        before_campaign_carousels: int = self._row_count("campaign_carousels")
        self._insert_probe()

        self.assertEqual(len(before_default), 6)
        self.assertEqual(before_generation, 1)

        self._upgrade(GENERATIONS_REVISION)
        self._assert_working_rows_unchanged(before_default, before_generation)
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)
        self._assert_default_snapshot()
        self._assert_probe_snapshot()
        self._assert_assembly_kept_its_frame()
        self._assert_same_generation_number_is_unique()
        self._assert_deleting_the_carousel_removes_the_snapshot()

        self._downgrade(PREVIOUS_REVISION)
        self.assertIsNone(self._regclass("carousel_generations"))
        self.assertIsNone(self._regclass("carousel_generation_instructions"))
        self.assertIsNone(self._regclass("carousel_generation_research"))
        self.assertIsNone(self._regclass("carousel_generation_images"))
        self.assertIsNone(self._regclass("carousel_generation_slides"))
        self.assertIsNone(self._regclass("carousel_generation_slide_texts"))
        self.assertIsNone(self._regclass("carousel_generation_slide_exclusions"))
        self.assertNotIn("generation_id", self._column_names("carousel_assemblies"))
        self._assert_working_rows_unchanged(before_default, before_generation)
        self.assertEqual(self._frame_asset_ref(FRAME_ID), ASSET_REF)
        self.assertEqual(self._generation_number(CAROUSEL_SLUG), 1)
        self.assertEqual(self._row_count("artifacts"), before_artifacts)

        self._upgrade(GENERATIONS_REVISION)
        self._assert_default_snapshot()
        self._assert_probe_snapshot()
        self._assert_assembly_kept_its_frame()
        self._assert_working_rows_unchanged(before_default, before_generation)
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)

    def test_a_carousel_created_after_upgrade_gets_a_header_only(self) -> None:
        """Assembly after the backfill hangs on a new header and writes no files."""

        self._upgrade(GENERATIONS_REVISION)
        before_artifacts: int = self._row_count("artifacts")
        before_images: int = self._row_count("album_images")
        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name

        try:
            self._insert_late_carousel()

            with Session(self.database_engine) as session:
                carousel: Carousel | None = session.get(Carousel, uuid.UUID(LATE_CAROUSEL_ID))

                self.assertIsNotNone(carousel)
                assert carousel is not None
                ensured = ensure_current_generation(carousel, session)
                session.commit()
                generation_id: uuid.UUID = ensured.id

            self._insert_late_assembly(str(generation_id))
            self.assertEqual(self._generation_count_for_slug(LATE_SLUG), 1)
            self.assertIsNone(self._snapshot_album_id(LATE_SLUG))
            self.assertEqual(self._child_count(LATE_SLUG, "carousel_generation_slides"), 0)
            self.assertEqual(
                self._child_count(LATE_SLUG, "carousel_generation_instructions"),
                0,
            )
            self.assertEqual(self._child_count(LATE_SLUG, "carousel_generation_research"), 0)
            self.assertEqual(self._child_count(LATE_SLUG, "carousel_generation_images"), 0)
            self.assertEqual(self._assembly_generation_id(LATE_CAROUSEL_ID), str(generation_id))
            self.assertEqual(self._row_count("artifacts"), before_artifacts)
            self.assertEqual(self._row_count("album_images"), before_images)
            self.assertEqual(list(Path(storage.name).rglob("*")), [])
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

    def _assert_working_rows_unchanged(
        self,
        before_default: list[SlideSnapshot],
        before_generation: int,
    ) -> None:
        """Default's slides and every carousel's generation number stay put."""

        self.assertEqual(self._slides_for_slug(DEFAULT_ALBUM_SLUG), before_default)
        self.assertEqual(self._generation_number(DEFAULT_ALBUM_SLUG), before_generation)
        self.assertEqual(self._generation_number(DEFAULT_ALBUM_SLUG), 1)
        self.assertEqual(self._generation_number(CAROUSEL_SLUG), 1)

    def _assert_default_snapshot(self) -> None:
        """Default is generation 1, with its album and six slides, and no documents."""

        self.assertEqual(self._generation_count_for_slug(DEFAULT_ALBUM_SLUG), 1)
        self.assertEqual(self._snapshot_generation_number(DEFAULT_ALBUM_SLUG), 1)
        self.assertEqual(
            self._snapshot_album_id(DEFAULT_ALBUM_SLUG),
            self._album_id(DEFAULT_ALBUM_SLUG),
        )
        self.assertEqual(self._child_count(DEFAULT_ALBUM_SLUG, "carousel_generation_slides"), 6)
        self.assertEqual(
            self._child_count(DEFAULT_ALBUM_SLUG, "carousel_generation_instructions"),
            0,
        )
        self.assertEqual(self._child_count(DEFAULT_ALBUM_SLUG, "carousel_generation_research"), 0)
        self.assertEqual(
            self._snapshot_image_ids(DEFAULT_ALBUM_SLUG),
            self._album_image_ids(DEFAULT_ALBUM_SLUG),
        )
        self.assertEqual(
            self._snapshot_source_slide_ids(DEFAULT_ALBUM_SLUG),
            [slide_id for slide_id, _status, _image_id in self._slides_for_slug(DEFAULT_ALBUM_SLUG)],
        )

    def _assert_probe_snapshot(self) -> None:
        """The typed carousel copies instructions, research, texts, and exclusions."""

        self.assertIsNone(self._snapshot_album_id(CAROUSEL_SLUG))
        self.assertEqual(self._child_count(CAROUSEL_SLUG, "carousel_generation_images"), 0)
        self.assertEqual(
            self._instruction_bodies(CAROUSEL_SLUG),
            ["", INSTRUCTION_BODY],
        )
        research_rows: list[tuple[str, str, str]] = self._research_rows(CAROUSEL_SLUG)

        self.assertEqual(len(research_rows), 1)
        self.assertEqual(research_rows[0][0], RESEARCH_ID)
        self.assertEqual(research_rows[0][1], RESEARCH_TITLE)
        self.assertEqual(research_rows[0][2], RESEARCH_BODY)
        self.assertEqual(
            self._snapshot_slides(CAROUSEL_SLUG),
            [
                (SLIDE_ID, "Quay", "live", None),
                (OTHER_SLIDE_ID, "Draft quay", "draft", None),
            ],
        )
        self.assertEqual(
            self._snapshot_text(CAROUSEL_SLUG, SLIDE_ID),
            (ELEMENT_ID, LIVE_VALUE, DRAFT_VALUE),
        )
        self.assertEqual(self._exclusion_count(CAROUSEL_SLUG), 2)

    def _assert_assembly_kept_its_frame(self) -> None:
        """The assembly id and PNG path stay. The new column points at generation 1."""

        self.assertEqual(self._frame_asset_ref(FRAME_ID), ASSET_REF)
        self.assertEqual(self._assembly_id_for_slug(CAROUSEL_SLUG), ASSEMBLY_ID)
        self.assertEqual(
            self._assembly_generation_id(CAROUSEL_ID),
            self._snapshot_id(CAROUSEL_SLUG),
        )
        self.assertEqual(self._assembly_generation_number(CAROUSEL_ID), 1)

    def _assert_same_generation_number_is_unique(self) -> None:
        """A second header for the same carousel and number is refused."""

        with self.assertRaises(IntegrityError) as duplicate_error:
            self._insert_generation(CAROUSEL_ID, 1, None)

        with self.assertRaises(IntegrityError) as generation_error:
            self._insert_generation(OTHER_CAROUSEL_ID, 0, None)

        self.assertIn(
            "uq_carousel_generations_carousel_id_generation_number",
            str(duplicate_error.exception),
        )
        self.assertIn(
            "ck_carousel_generations_generation_number",
            str(generation_error.exception),
        )
        self._insert_generation(CAROUSEL_ID, 2, None)
        self.assertEqual(self._generation_count_for_slug(CAROUSEL_SLUG), 2)

    def _assert_deleting_the_carousel_removes_the_snapshot(self) -> None:
        """Deleting the carousel removes its snapshot and an assembly that hangs on it."""

        self._insert_late_assembly_for_carousel(
            OTHER_CAROUSEL_ID,
            self._snapshot_id(OTHER_SLUG),
        )
        self._delete_carousel(OTHER_CAROUSEL_ID)

        self.assertEqual(self._generation_count_for_slug(OTHER_SLUG), 0)
        self.assertIsNone(self._assembly_id_for_slug(OTHER_SLUG))
        self.assertEqual(self._generation_count_for_slug(CAROUSEL_SLUG), 2)

    def _insert_probe(self) -> None:
        """Store a null-album carousel, its documents, and one assembly frame."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeletons (
                        id, name, slug, advertisement_type, background_kind
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        'Generation paper',
                        'generation-paper',
                        'carousel',
                        'color'::background_kind
                    )
                    """
                ),
                {"skeleton_id": SKELETON_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO skeleton_elements (
                        id,
                        skeleton_id,
                        band,
                        sort_order,
                        content_kind,
                        name,
                        font_family,
                        font_size,
                        font_color,
                        alignment
                    )
                    VALUES (
                        CAST(:element_id AS uuid),
                        CAST(:skeleton_id AS uuid),
                        'middle'::skeleton_element_band,
                        0,
                        'text'::skeleton_element_content_kind,
                        'Claim',
                        'Georgia',
                        48,
                        '#111111',
                        'left'::skeleton_element_alignment
                    )
                    """
                ),
                {"element_id": ELEMENT_ID, "skeleton_id": SKELETON_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, editor_step, generation_number
                    )
                    VALUES
                        (
                            CAST(:carousel_id AS uuid),
                            CAST(:skeleton_id AS uuid),
                            'Generation probe',
                            :carousel_slug,
                            3,
                            1
                        ),
                        (
                            CAST(:other_id AS uuid),
                            CAST(:skeleton_id AS uuid),
                            'Generation other',
                            :other_slug,
                            0,
                            1
                        )
                    """
                ),
                {
                    "carousel_id": CAROUSEL_ID,
                    "other_id": OTHER_CAROUSEL_ID,
                    "skeleton_id": SKELETON_ID,
                    "carousel_slug": CAROUSEL_SLUG,
                    "other_slug": OTHER_SLUG,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_instructions (carousel_id, position, body)
                    VALUES
                        (CAST(:carousel_id AS uuid), 0, ''),
                        (CAST(:carousel_id AS uuid), 1, :body)
                    """
                ),
                {"carousel_id": CAROUSEL_ID, "body": INSTRUCTION_BODY},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (
                        CAST(:research_id AS uuid),
                        :title,
                        'tides',
                        :body
                    )
                    """
                ),
                {
                    "research_id": RESEARCH_ID,
                    "title": RESEARCH_TITLE,
                    "body": RESEARCH_BODY,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_research_items (
                        carousel_id, research_item_id, position
                    )
                    VALUES (CAST(:carousel_id AS uuid), CAST(:research_id AS uuid), 0)
                    """
                ),
                {"carousel_id": CAROUSEL_ID, "research_id": RESEARCH_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slides (
                        id, carousel_id, position, name, text_status
                    )
                    VALUES
                        (
                            CAST(:slide_id AS uuid),
                            CAST(:carousel_id AS uuid),
                            0,
                            'Quay',
                            'live'
                        ),
                        (
                            CAST(:other_slide_id AS uuid),
                            CAST(:carousel_id AS uuid),
                            1,
                            'Draft quay',
                            'draft'
                        )
                    """
                ),
                {
                    "slide_id": SLIDE_ID,
                    "other_slide_id": OTHER_SLIDE_ID,
                    "carousel_id": CAROUSEL_ID,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slide_element_texts (
                        id, slide_id, skeleton_element_id, value, draft_value
                    )
                    VALUES (
                        gen_random_uuid(),
                        CAST(:slide_id AS uuid),
                        CAST(:element_id AS uuid),
                        :value,
                        :draft_value
                    )
                    """
                ),
                {
                    "slide_id": SLIDE_ID,
                    "element_id": ELEMENT_ID,
                    "value": LIVE_VALUE,
                    "draft_value": DRAFT_VALUE,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slide_exclusions (id, slide_id, excluded_slide_id)
                    VALUES
                        (
                            gen_random_uuid(),
                            CAST(:slide_id AS uuid),
                            CAST(:other_slide_id AS uuid)
                        ),
                        (
                            gen_random_uuid(),
                            CAST(:other_slide_id AS uuid),
                            CAST(:slide_id AS uuid)
                        )
                    """
                ),
                {"slide_id": SLIDE_ID, "other_slide_id": OTHER_SLIDE_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_assemblies (
                        id, carousel_id, generation_number, slide_count
                    )
                    VALUES (
                        CAST(:assembly_id AS uuid),
                        CAST(:carousel_id AS uuid),
                        1,
                        5
                    )
                    """
                ),
                {"assembly_id": ASSEMBLY_ID, "carousel_id": CAROUSEL_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO assembled_carousels (
                        id, assembly_id, position, status, caption
                    )
                    VALUES (
                        CAST(:assembled_id AS uuid),
                        CAST(:assembly_id AS uuid),
                        0,
                        'draft',
                        'Generation probe'
                    )
                    """
                ),
                {
                    "assembled_id": "ffffffff-ffff-4fff-8fff-ffffffffff33",
                    "assembly_id": ASSEMBLY_ID,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO assembled_carousel_frames (
                        id,
                        assembled_carousel_id,
                        position,
                        asset_ref,
                        blocked
                    )
                    VALUES (
                        CAST(:frame_id AS uuid),
                        CAST(:assembled_id AS uuid),
                        0,
                        :asset_ref,
                        false
                    )
                    """
                ),
                {
                    "frame_id": FRAME_ID,
                    "assembled_id": "ffffffff-ffff-4fff-8fff-ffffffffff33",
                    "asset_ref": ASSET_REF,
                },
            )

    def _insert_late_carousel(self) -> None:
        """Insert a carousel the backfill never saw."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, editor_step, generation_number
                    )
                    VALUES (
                        CAST(:carousel_id AS uuid),
                        CAST(:skeleton_id AS uuid),
                        'After upgrade',
                        :slug,
                        0,
                        1
                    )
                    """
                ),
                {
                    "carousel_id": LATE_CAROUSEL_ID,
                    "skeleton_id": str(DEFAULT_ALBUM_SKELETON_ID),
                    "slug": LATE_SLUG,
                },
            )

    def _insert_late_assembly(self, generation_id: str) -> None:
        """Hang one assembly on a header created after the upgrade."""

        self._insert_late_assembly_for_carousel(LATE_CAROUSEL_ID, generation_id)

    def _insert_late_assembly_for_carousel(self, carousel_id: str, generation_id: str) -> None:
        """Hang one assembly on an existing snapshot header."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_assemblies (
                        carousel_id, generation_number, slide_count, generation_id
                    )
                    VALUES (
                        CAST(:carousel_id AS uuid),
                        1,
                        5,
                        CAST(:generation_id AS uuid)
                    )
                    """
                ),
                {"carousel_id": carousel_id, "generation_id": generation_id},
            )

    def _insert_generation(
        self,
        carousel_id: str,
        generation_number: int,
        album_id: str | None,
    ) -> None:
        """Insert one snapshot header. The caller expects success or a constraint error."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_generations (
                        carousel_id, generation_number, album_id
                    )
                    VALUES (
                        CAST(:carousel_id AS uuid),
                        :generation_number,
                        CAST(:album_id AS uuid)
                    )
                    """
                ),
                {
                    "carousel_id": carousel_id,
                    "generation_number": generation_number,
                    "album_id": album_id,
                },
            )

    def _delete_carousel(self, carousel_id: str) -> None:
        """Delete one carousel. Cascades remove its snapshot and assembly."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM carousels WHERE id = CAST(:carousel_id AS uuid)"),
                {"carousel_id": carousel_id},
            )

    def _slides_for_slug(self, slug: str) -> list[SlideSnapshot]:
        """Return working slide id, status, and image id in position order."""

        with self.database_engine.connect() as connection:
            slides: list[SlideSnapshot] = [
                (str(row[0]), str(row[1]), None if row[2] is None else str(row[2]))
                for row in connection.execute(
                    text(
                        """
                        SELECT slide.id::text, slide.text_status::text, slide.album_image_id::text
                        FROM slides AS slide
                        JOIN carousels AS carousel ON carousel.id = slide.carousel_id
                        WHERE carousel.slug = :slug
                        ORDER BY slide.position, slide.id
                        """
                    ),
                    {"slug": slug},
                ).fetchall()
            ]

        return slides

    def _generation_number(self, slug: str) -> int:
        """Return ``carousels.generation_number`` for one slug."""

        with self.database_engine.connect() as connection:
            generation_number: int = int(
                connection.execute(
                    text(
                        """
                        SELECT generation_number
                        FROM carousels
                        WHERE slug = :slug
                        """
                    ),
                    {"slug": slug},
                ).scalar_one(),
            )

        return generation_number

    def _album_id(self, slug: str) -> str | None:
        """Return the working album id for one carousel slug."""

        with self.database_engine.connect() as connection:
            album_id: object | None = connection.execute(
                text("SELECT album_id::text FROM carousels WHERE slug = :slug"),
                {"slug": slug},
            ).scalar_one()

        if album_id is None:

            return None

        return str(album_id)

    def _snapshot_album_id(self, slug: str) -> str | None:
        """Return the backfilled album id. Generation 2 is ignored when present."""

        with self.database_engine.connect() as connection:
            album_id: object | None = connection.execute(
                text(
                    """
                    SELECT generation.album_id::text
                    FROM carousel_generations AS generation
                    JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                    WHERE carousel.slug = :slug
                      AND generation.generation_number = carousel.generation_number
                    """
                ),
                {"slug": slug},
            ).scalar_one()

        if album_id is None:

            return None

        return str(album_id)

    def _snapshot_generation_number(self, slug: str) -> int:
        """Return the snapshot number that matches the carousel's current number."""

        with self.database_engine.connect() as connection:
            generation_number: int = int(
                connection.execute(
                    text(
                        """
                        SELECT generation.generation_number
                        FROM carousel_generations AS generation
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        """
                    ),
                    {"slug": slug},
                ).scalar_one(),
            )

        return generation_number

    def _snapshot_id(self, slug: str) -> str:
        """Return the current snapshot id for one carousel slug."""

        with self.database_engine.connect() as connection:
            generation_id: str = str(
                connection.execute(
                    text(
                        """
                        SELECT generation.id::text
                        FROM carousel_generations AS generation
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        """
                    ),
                    {"slug": slug},
                ).scalar_one(),
            )

        return generation_id

    def _generation_count_for_slug(self, slug: str) -> int:
        """Return how many snapshot headers one carousel has."""

        with self.database_engine.connect() as connection:
            generation_count: int = int(
                connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM carousel_generations AS generation
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                        """
                    ),
                    {"slug": slug},
                ).scalar_one(),
            )

        return generation_count

    def _child_count(self, slug: str, table_name: str) -> int:
        """Return how many child rows the current snapshot has in one table."""

        with self.database_engine.connect() as connection:
            child_count: int = int(
                connection.execute(
                    text(
                        f"""
                        SELECT count(*)
                        FROM {table_name} AS child
                        JOIN carousel_generations AS generation
                          ON generation.id = child.generation_id
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        """
                    ),
                    {"slug": slug},
                ).scalar_one(),
            )

        return child_count

    def _snapshot_image_ids(self, slug: str) -> list[str]:
        """Return copied image ids in position order."""

        with self.database_engine.connect() as connection:
            image_ids: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT image.album_image_id::text
                        FROM carousel_generation_images AS image
                        JOIN carousel_generations AS generation
                          ON generation.id = image.generation_id
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        ORDER BY image.position
                        """
                    ),
                    {"slug": slug},
                ).fetchall()
            ]

        return image_ids

    def _album_image_ids(self, slug: str) -> list[str]:
        """Return the working album's image ids in position order."""

        with self.database_engine.connect() as connection:
            image_ids: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT image.id::text
                        FROM album_images AS image
                        JOIN carousels AS carousel ON carousel.album_id = image.album_id
                        WHERE carousel.slug = :slug
                        ORDER BY image.position
                        """
                    ),
                    {"slug": slug},
                ).fetchall()
            ]

        return image_ids

    def _snapshot_source_slide_ids(self, slug: str) -> list[str]:
        """Return copied source slide ids in position order."""

        with self.database_engine.connect() as connection:
            slide_ids: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT generation_slide.source_slide_id::text
                        FROM carousel_generation_slides AS generation_slide
                        JOIN carousel_generations AS generation
                          ON generation.id = generation_slide.generation_id
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        ORDER BY generation_slide.position
                        """
                    ),
                    {"slug": slug},
                ).fetchall()
            ]

        return slide_ids

    def _instruction_bodies(self, slug: str) -> list[str]:
        """Return copied instruction bodies in position order."""

        with self.database_engine.connect() as connection:
            bodies: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT instruction.body
                        FROM carousel_generation_instructions AS instruction
                        JOIN carousel_generations AS generation
                          ON generation.id = instruction.generation_id
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        ORDER BY instruction.position
                        """
                    ),
                    {"slug": slug},
                ).fetchall()
            ]

        return bodies

    def _research_rows(self, slug: str) -> list[tuple[str, str, str]]:
        """Return copied research id, title, and body in position order."""

        with self.database_engine.connect() as connection:
            rows: list[tuple[str, str, str]] = [
                (str(row[0]), str(row[1]), str(row[2]))
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            research.research_item_id::text,
                            research.title,
                            research.body
                        FROM carousel_generation_research AS research
                        JOIN carousel_generations AS generation
                          ON generation.id = research.generation_id
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        ORDER BY research.position
                        """
                    ),
                    {"slug": slug},
                ).fetchall()
            ]

        return rows

    def _snapshot_slides(self, slug: str) -> list[tuple[str, str, str, str | None]]:
        """Return source id, name, status, and image id for copied slides."""

        with self.database_engine.connect() as connection:
            slides: list[tuple[str, str, str, str | None]] = [
                (
                    str(row[0]),
                    str(row[1]),
                    str(row[2]),
                    None if row[3] is None else str(row[3]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            generation_slide.source_slide_id::text,
                            generation_slide.name,
                            generation_slide.text_status::text,
                            generation_slide.album_image_id::text
                        FROM carousel_generation_slides AS generation_slide
                        JOIN carousel_generations AS generation
                          ON generation.id = generation_slide.generation_id
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        ORDER BY generation_slide.position
                        """
                    ),
                    {"slug": slug},
                ).fetchall()
            ]

        return slides

    def _snapshot_text(self, slug: str, source_slide_id: str) -> tuple[str, str, str | None]:
        """Return the copied element id, value, and draft for one source slide."""

        with self.database_engine.connect() as connection:
            row: tuple[object, object, object | None] = connection.execute(
                text(
                    """
                    SELECT
                        element_text.skeleton_element_id::text,
                        element_text.value,
                        element_text.draft_value
                    FROM carousel_generation_slide_texts AS element_text
                    JOIN carousel_generation_slides AS generation_slide
                      ON generation_slide.id = element_text.generation_slide_id
                    JOIN carousel_generations AS generation
                      ON generation.id = generation_slide.generation_id
                    JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                    WHERE carousel.slug = :slug
                      AND generation_slide.source_slide_id = CAST(:slide_id AS uuid)
                    """
                ),
                {"slug": slug, "slide_id": source_slide_id},
            ).one()

        draft_value: str | None = None if row[2] is None else str(row[2])
        copied_text: tuple[str, str, str | None] = (str(row[0]), str(row[1]), draft_value)

        return copied_text

    def _exclusion_count(self, slug: str) -> int:
        """Return how many copied exclusion rows the current snapshot has."""

        with self.database_engine.connect() as connection:
            exclusion_count: int = int(
                connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM carousel_generation_slide_exclusions AS exclusion
                        JOIN carousel_generation_slides AS generation_slide
                          ON generation_slide.id = exclusion.generation_slide_id
                        JOIN carousel_generations AS generation
                          ON generation.id = generation_slide.generation_id
                        JOIN carousels AS carousel ON carousel.id = generation.carousel_id
                        WHERE carousel.slug = :slug
                          AND generation.generation_number = carousel.generation_number
                        """
                    ),
                    {"slug": slug},
                ).scalar_one(),
            )

        return exclusion_count

    def _frame_asset_ref(self, frame_id: str) -> str:
        """Return the stored PNG path for one frame."""

        with self.database_engine.connect() as connection:
            asset_ref: str = str(
                connection.execute(
                    text(
                        """
                        SELECT asset_ref
                        FROM assembled_carousel_frames
                        WHERE id = CAST(:frame_id AS uuid)
                        """
                    ),
                    {"frame_id": frame_id},
                ).scalar_one(),
            )

        return asset_ref

    def _assembly_id_for_slug(self, slug: str) -> str | None:
        """Return one assembly id for a carousel, or None when it has none."""

        with self.database_engine.connect() as connection:
            assembly_id: object | None = connection.execute(
                text(
                    """
                    SELECT assembly.id::text
                    FROM carousel_assemblies AS assembly
                    JOIN carousels AS carousel ON carousel.id = assembly.carousel_id
                    WHERE carousel.slug = :slug
                    """
                ),
                {"slug": slug},
            ).scalar_one_or_none()

        if assembly_id is None:

            return None

        return str(assembly_id)

    def _assembly_generation_id(self, carousel_id: str) -> str:
        """Return the snapshot id stored on one carousel's assembly."""

        with self.database_engine.connect() as connection:
            generation_id: str = str(
                connection.execute(
                    text(
                        """
                        SELECT generation_id::text
                        FROM carousel_assemblies
                        WHERE carousel_id = CAST(:carousel_id AS uuid)
                        """
                    ),
                    {"carousel_id": carousel_id},
                ).scalar_one(),
            )

        return generation_id

    def _assembly_generation_number(self, carousel_id: str) -> int:
        """Return the generation number stored on one carousel's assembly."""

        with self.database_engine.connect() as connection:
            generation_number: int = int(
                connection.execute(
                    text(
                        """
                        SELECT generation_number
                        FROM carousel_assemblies
                        WHERE carousel_id = CAST(:carousel_id AS uuid)
                        """
                    ),
                    {"carousel_id": carousel_id},
                ).scalar_one(),
            )

        return generation_number

    def _row_count(self, table_name: str) -> int:
        """Return how many rows one table holds."""

        with self.database_engine.connect() as connection:
            row_count: int = int(
                connection.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one(),
            )

        return row_count

    def _column_names(self, table_name: str) -> set[str]:
        """Return the column names on one table."""

        with self.database_engine.connect() as connection:
            names: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                        """
                    ),
                    {"table_name": table_name},
                ).fetchall()
            }

        return names

    def _regclass(self, table_name: str) -> str | None:
        """Return the table name, or None when the relation is gone."""

        with self.database_engine.connect() as connection:
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


if __name__ == "__main__":
    unittest.main()
