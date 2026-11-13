"""Add Final assembly tables without rewriting slides that already exist."""

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

from app.carousels.default_carousel import DEFAULT_ALBUM_SLUG
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
PREVIOUS_REVISION: str = "slide_draft_batches"
ASSEMBLY_REVISION: str = "carousel_final_assembly"
SKELETON_ID: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb21"
CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaac01"
OTHER_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaac02"
SLIDE_ID: str = "dddddddd-dddd-4ddd-8ddd-dddddddddd21"
IMAGE_ID: str = "cccccccc-cccc-4ccc-8ccc-cccccccccc21"
CAROUSEL_SLUG: str = "final-probe"
OTHER_SLUG: str = "final-other"
PROBE_GENERATION: int = 1
SECOND_GENERATION: int = 2
ASSEMBLY_UNIQUE: str = "uq_carousel_assemblies_carousel_id_generation_number"

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
class CarouselFinalAssemblyMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again. Default gains no assembly row."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_final_{uuid.uuid4().hex[:10]}"
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

    def test_upgrade_downgrade_upgrade_leaves_existing_rows(self) -> None:
        """Default stays six live slides at generation 1, with no assembly row."""

        self._upgrade(PREVIOUS_REVISION)
        before_default: list[SlideSnapshot] = self._slides_for_slug(DEFAULT_ALBUM_SLUG)
        before_generation: int = self._generation_number(DEFAULT_ALBUM_SLUG)
        before_artifacts: int = self._row_count("artifacts")
        before_campaign_carousels: int = self._row_count("campaign_carousels")

        self.assertEqual(len(before_default), 6)
        self.assertEqual(before_generation, 1)

        for _slide_id, text_status, album_image_id in before_default:
            self.assertEqual(text_status, "live")
            self.assertIsNotNone(album_image_id)

        self._upgrade(ASSEMBLY_REVISION)
        self._assert_default_unchanged(before_default, before_generation)
        self.assertEqual(self._row_count("carousel_assemblies"), 0)
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)
        self.assertIsNotNone(self._regclass("artifacts"))
        self.assertIsNotNone(self._regclass("campaign_carousels"))
        self._assert_editor_step_still_rejects_final()
        self._assert_table_shape()
        self._assert_one_assembly_per_generation()
        self._assert_a_blocked_frame_can_be_stored()
        self._assert_deleting_a_source_clears_the_pointer()
        self._assert_default_unchanged(before_default, before_generation)

        self._downgrade(PREVIOUS_REVISION)
        self.assertIsNone(self._regclass("carousel_assemblies"))
        self.assertIsNone(self._regclass("assembled_carousels"))
        self.assertIsNone(self._regclass("assembled_carousel_frames"))
        self._assert_default_unchanged(
            before_default,
            before_generation,
            assembly_table=False,
        )
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)
        self.assertIsNotNone(self._regclass("slides"))

        self._upgrade(ASSEMBLY_REVISION)
        self.assertEqual(self._row_count("carousel_assemblies"), 0)
        self._assert_default_unchanged(before_default, before_generation)
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)

    def _assert_default_unchanged(
        self,
        before_default: list[SlideSnapshot],
        before_generation: int,
        assembly_table: bool = True,
    ) -> None:
        """Default's six live slides and generation number are the ones from before."""

        slides: list[SlideSnapshot] = self._slides_for_slug(DEFAULT_ALBUM_SLUG)

        self.assertEqual(slides, before_default)
        self.assertEqual(len(slides), 6)
        self.assertEqual(self._generation_number(DEFAULT_ALBUM_SLUG), before_generation)
        self.assertEqual(self._generation_number(DEFAULT_ALBUM_SLUG), 1)

        if assembly_table:
            self.assertEqual(self._assembly_count_for_slug(DEFAULT_ALBUM_SLUG), 0)

    def _assert_editor_step_still_rejects_final(self) -> None:
        """Step 4 is still outside ``ck_carousels_editor_step``."""

        with self.assertRaises(IntegrityError) as step_error:
            self._set_editor_step(DEFAULT_ALBUM_SLUG, 4)

        self.assertIn("ck_carousels_editor_step", str(step_error.exception))
        self.assertEqual(self._editor_step(DEFAULT_ALBUM_SLUG), 3)

    def _assert_table_shape(self) -> None:
        """Columns, checks, and delete actions match the revision."""

        assembly_checks: set[str] = self._check_names("carousel_assemblies")
        carousel_checks: set[str] = self._check_names("assembled_carousels")
        frame_checks: set[str] = self._check_names("assembled_carousel_frames")
        assembly_actions: dict[str, str] = self._delete_actions("carousel_assemblies")
        carousel_actions: dict[str, str] = self._delete_actions("assembled_carousels")
        frame_actions: dict[str, str] = self._delete_actions("assembled_carousel_frames")

        self.assertEqual(
            self._column_names_in_order("carousel_assemblies"),
            [
                "id",
                "carousel_id",
                "generation_number",
                "slide_count",
                "created_at",
                "updated_at",
            ],
        )
        self.assertEqual(
            self._column_names_in_order("assembled_carousels"),
            [
                "id",
                "assembly_id",
                "position",
                "status",
                "caption",
                "cta_url",
                "created_at",
                "updated_at",
            ],
        )
        self.assertNotIn("hashtags", self._column_names("assembled_carousels"))
        self.assertEqual(
            self._column_names_in_order("assembled_carousel_frames"),
            [
                "id",
                "assembled_carousel_id",
                "position",
                "slide_id",
                "album_image_id",
                "asset_ref",
                "blocked",
                "block_reason",
                "block_detail",
                "created_at",
                "updated_at",
            ],
        )
        self.assertIn("ck_carousel_assemblies_generation_number", assembly_checks)
        self.assertIn("ck_carousel_assemblies_slide_count", assembly_checks)
        self.assertIn("ck_assembled_carousels_status", carousel_checks)
        self.assertIn("ck_assembled_carousels_position", carousel_checks)
        self.assertIn("ck_assembled_carousel_frames_block_reason", frame_checks)
        self.assertIn("ck_assembled_carousel_frames_position", frame_checks)
        self.assertNotIn("ck_carousel_assemblies_ck_carousel_assemblies_slide_count", assembly_checks)
        self.assertEqual(assembly_actions["carousel_id"], "c")
        self.assertEqual(carousel_actions["assembly_id"], "c")
        self.assertEqual(frame_actions["assembled_carousel_id"], "c")
        self.assertEqual(frame_actions["slide_id"], "n")
        self.assertEqual(frame_actions["album_image_id"], "n")
        self.assertEqual(self._column_nullable("assembled_carousel_frames", "slide_id"), "YES")
        self.assertEqual(self._column_nullable("assembled_carousel_frames", "blocked"), "NO")
        self.assertEqual(self._column_nullable("assembled_carousels", "caption"), "YES")
        self.assertEqual(self._column_nullable("assembled_carousels", "cta_url"), "YES")

    def _assert_one_assembly_per_generation(self) -> None:
        """The same carousel and generation cannot hold two assembly rows."""

        self._insert_probe_carousel()
        assembly_id: str = self._insert_assembly(CAROUSEL_ID, PROBE_GENERATION, 5)
        second_generation_id: str = self._insert_assembly(
            CAROUSEL_ID,
            SECOND_GENERATION,
            8,
        )
        other_id: str = self._insert_assembly(OTHER_CAROUSEL_ID, PROBE_GENERATION, 6)

        with self.assertRaises(IntegrityError) as duplicate_error:
            self._insert_assembly(CAROUSEL_ID, PROBE_GENERATION, 5)

        with self.assertRaises(IntegrityError) as count_error:
            self._insert_assembly(OTHER_CAROUSEL_ID, SECOND_GENERATION, 0)

        with self.assertRaises(IntegrityError) as generation_error:
            self._insert_assembly(OTHER_CAROUSEL_ID, 0, 1)

        self.assertIn(ASSEMBLY_UNIQUE, str(duplicate_error.exception))
        self.assertIn("ck_carousel_assemblies_slide_count", str(count_error.exception))
        self.assertIn("ck_carousel_assemblies_generation_number", str(generation_error.exception))
        self.assertEqual(self._row_count("carousel_assemblies"), 3)
        self.assertIn(assembly_id, self._assembly_ids())
        self.assertIn(second_generation_id, self._assembly_ids())
        self.assertIn(other_id, self._assembly_ids())
        self.assembly_id: str = assembly_id

    def _assert_a_blocked_frame_can_be_stored(self) -> None:
        """A missing file is a blocked frame row, not a refused insert."""

        assembled_id: str = self._insert_assembled_carousel(
            self.assembly_id,
            0,
            "draft",
            "Harbor",
            None,
        )

        with self.assertRaises(IntegrityError) as status_error:
            self._insert_assembled_carousel(self.assembly_id, 1, "live", None, None)

        with self.assertRaises(IntegrityError) as position_error:
            self._insert_assembled_carousel(self.assembly_id, -1, "draft", None, None)

        frame_id: str = self._insert_frame(
            assembled_id,
            0,
            None,
            None,
            "assembled/probe/frame.png",
            True,
            "missing_asset",
            "The picture file is missing.",
        )
        stored: tuple[bool, str | None, str | None, str | None, str | None] = (
            self._frame_row(frame_id)
        )

        self.assertIn("ck_assembled_carousels_status", str(status_error.exception))
        self.assertIn("ck_assembled_carousels_position", str(position_error.exception))
        self.assertEqual(stored[0], True)
        self.assertEqual(stored[1], "missing_asset")
        self.assertEqual(stored[2], "The picture file is missing.")
        self.assertIsNone(stored[3])
        self.assertIsNone(stored[4])
        self.assertEqual(self._assembled_caption(assembled_id), "Harbor")
        self.assertIsNone(self._assembled_cta_url(assembled_id))
        self.assembled_id: str = assembled_id
        self.frame_id: str = frame_id

    def _assert_deleting_a_source_clears_the_pointer(self) -> None:
        """Deleting the slide or the album image leaves the frame and clears that id."""

        image_id: str = self._insert_album_image()

        self._point_frame(self.frame_id, SLIDE_ID, image_id)
        self._delete_slide(SLIDE_ID)
        after_slide: tuple[bool, str | None, str | None, str | None, str | None] = (
            self._frame_row(self.frame_id)
        )

        self.assertIsNone(after_slide[3])
        self.assertEqual(after_slide[4], image_id)
        self.assertEqual(after_slide[1], "missing_asset")
        self.assertNotIn(SLIDE_ID, self._slide_ids())

        self._delete_album_image(image_id)
        after_image: tuple[bool, str | None, str | None, str | None, str | None] = (
            self._frame_row(self.frame_id)
        )

        self.assertIsNone(after_image[4])
        self.assertEqual(after_image[0], True)
        self.assertIn(self.frame_id, self._frame_ids())

        self._delete_carousel(CAROUSEL_ID)

        self.assertNotIn(self.assembly_id, self._assembly_ids())
        self.assertNotIn(self.frame_id, self._frame_ids())
        self.assertIn(OTHER_CAROUSEL_ID, self._carousel_ids_with_assemblies())

    def _insert_probe_carousel(self) -> None:
        """Insert a color skeleton and two carousels the assembly rows can point at."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeletons (
                        id, name, slug, advertisement_type, background_kind
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        'Final paper',
                        'final-paper',
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
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, editor_step, generation_number
                    )
                    VALUES
                        (
                            CAST(:carousel_id AS uuid),
                            CAST(:skeleton_id AS uuid),
                            'Final probe',
                            :carousel_slug,
                            3,
                            :generation_number
                        ),
                        (
                            CAST(:other_id AS uuid),
                            CAST(:skeleton_id AS uuid),
                            'Final other',
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
                    "generation_number": PROBE_GENERATION,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO slides (
                        id, carousel_id, position, name, text_status
                    )
                    VALUES (
                        CAST(:slide_id AS uuid),
                        CAST(:carousel_id AS uuid),
                        0,
                        'Quay',
                        'live'
                    )
                    """
                ),
                {"slide_id": SLIDE_ID, "carousel_id": CAROUSEL_ID},
            )

    def _insert_assembly(
        self,
        carousel_id: str,
        generation_number: int,
        slide_count: int,
    ) -> str:
        """Insert one assembly. The caller expects success or a constraint error."""

        with self.database_engine.begin() as connection:
            assembly_id: str = str(
                connection.execute(
                    text(
                        """
                        INSERT INTO carousel_assemblies (
                            carousel_id, generation_number, slide_count
                        )
                        VALUES (
                            CAST(:carousel_id AS uuid),
                            :generation_number,
                            :slide_count
                        )
                        RETURNING id::text
                        """
                    ),
                    {
                        "carousel_id": carousel_id,
                        "generation_number": generation_number,
                        "slide_count": slide_count,
                    },
                ).scalar_one(),
            )

        return assembly_id

    def _insert_assembled_carousel(
        self,
        assembly_id: str,
        position: int,
        status: str,
        caption: str | None,
        cta_url: str | None,
    ) -> str:
        """Insert one reviewed carousel."""

        with self.database_engine.begin() as connection:
            assembled_id: str = str(
                connection.execute(
                    text(
                        """
                        INSERT INTO assembled_carousels (
                            assembly_id, position, status, caption, cta_url
                        )
                        VALUES (
                            CAST(:assembly_id AS uuid),
                            :position,
                            :status,
                            :caption,
                            :cta_url
                        )
                        RETURNING id::text
                        """
                    ),
                    {
                        "assembly_id": assembly_id,
                        "position": position,
                        "status": status,
                        "caption": caption,
                        "cta_url": cta_url,
                    },
                ).scalar_one(),
            )

        return assembled_id

    def _insert_frame(
        self,
        assembled_id: str,
        position: int,
        slide_id: str | None,
        album_image_id: str | None,
        asset_ref: str,
        blocked: bool,
        block_reason: str | None,
        block_detail: str | None,
    ) -> str:
        """Insert one frame. Pointers may be null."""

        with self.database_engine.begin() as connection:
            frame_id: str = str(
                connection.execute(
                    text(
                        """
                        INSERT INTO assembled_carousel_frames (
                            assembled_carousel_id,
                            position,
                            slide_id,
                            album_image_id,
                            asset_ref,
                            blocked,
                            block_reason,
                            block_detail
                        )
                        VALUES (
                            CAST(:assembled_id AS uuid),
                            :position,
                            CAST(:slide_id AS uuid),
                            CAST(:album_image_id AS uuid),
                            :asset_ref,
                            :blocked,
                            :block_reason,
                            :block_detail
                        )
                        RETURNING id::text
                        """
                    ),
                    {
                        "assembled_id": assembled_id,
                        "position": position,
                        "slide_id": slide_id,
                        "album_image_id": album_image_id,
                        "asset_ref": asset_ref,
                        "blocked": blocked,
                        "block_reason": block_reason,
                        "block_detail": block_detail,
                    },
                ).scalar_one(),
            )

        return frame_id

    def _insert_album_image(self) -> str:
        """Insert one album image the frame can point at, then lose."""

        album_id: str = self._default_album_id()

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO album_images (
                        id,
                        album_id,
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
                        CAST(:album_id AS uuid),
                        99,
                        'albums/final-probe.png',
                        'png'::slide_image_media_type,
                        10,
                        1,
                        1,
                        'cc0'::slide_image_license,
                        'probe',
                        '',
                        'upload'::slide_image_intake
                    )
                    """
                ),
                {"image_id": IMAGE_ID, "album_id": album_id},
            )

        return IMAGE_ID

    def _point_frame(self, frame_id: str, slide_id: str, album_image_id: str) -> None:
        """Set both source pointers on one frame."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE assembled_carousel_frames
                    SET slide_id = CAST(:slide_id AS uuid),
                        album_image_id = CAST(:album_image_id AS uuid)
                    WHERE id = CAST(:frame_id AS uuid)
                    """
                ),
                {
                    "frame_id": frame_id,
                    "slide_id": slide_id,
                    "album_image_id": album_image_id,
                },
            )

    def _delete_slide(self, slide_id: str) -> None:
        """Delete one slide. A frame that pointed at it stays."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM slides WHERE id = CAST(:slide_id AS uuid)"),
                {"slide_id": slide_id},
            )

    def _delete_album_image(self, image_id: str) -> None:
        """Delete one album image. A frame that pointed at it stays."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM album_images WHERE id = CAST(:image_id AS uuid)"),
                {"image_id": image_id},
            )

    def _delete_carousel(self, carousel_id: str) -> None:
        """Delete one carousel. Its assembly goes with it."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM carousels WHERE id = CAST(:carousel_id AS uuid)"),
                {"carousel_id": carousel_id},
            )

    def _set_editor_step(self, slug: str, editor_step: int) -> None:
        """Write an editor step. Step 4 must fail the existing check."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE carousels
                    SET editor_step = :editor_step
                    WHERE slug = :slug
                    """
                ),
                {"slug": slug, "editor_step": editor_step},
            )

    def _slides_for_slug(self, slug: str) -> list[SlideSnapshot]:
        """Return id, text status, and album image for one carousel."""

        with self.database_engine.connect() as connection:
            slides: list[SlideSnapshot] = [
                (
                    str(row[0]),
                    str(row[1]),
                    None if row[2] is None else str(row[2]),
                )
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
        """Return the stored generation for one carousel slug."""

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

    def _editor_step(self, slug: str) -> int:
        """Return the stored editor step for one carousel slug."""

        with self.database_engine.connect() as connection:
            editor_step: int = int(
                connection.execute(
                    text("SELECT editor_step FROM carousels WHERE slug = :slug"),
                    {"slug": slug},
                ).scalar_one(),
            )

        return editor_step

    def _assembly_count_for_slug(self, slug: str) -> int:
        """Return how many assembly rows belong to one carousel slug."""

        with self.database_engine.connect() as connection:
            assembly_count: int = int(
                connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM carousel_assemblies AS assembly
                        JOIN carousels AS carousel ON carousel.id = assembly.carousel_id
                        WHERE carousel.slug = :slug
                        """
                    ),
                    {"slug": slug},
                ).scalar_one(),
            )

        return assembly_count

    def _row_count(self, table_name: str) -> int:
        """Return the number of rows in one public table."""

        with self.database_engine.connect() as connection:
            row_count: int = int(
                connection.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one(),
            )

        return row_count

    def _frame_row(
        self,
        frame_id: str,
    ) -> tuple[bool, str | None, str | None, str | None, str | None]:
        """Return blocked, reason, detail, slide id, and album image id."""

        with self.database_engine.connect() as connection:
            row: tuple[object, ...] = connection.execute(
                text(
                    """
                    SELECT
                        blocked,
                        block_reason,
                        block_detail,
                        slide_id::text,
                        album_image_id::text
                    FROM assembled_carousel_frames
                    WHERE id = CAST(:frame_id AS uuid)
                    """
                ),
                {"frame_id": frame_id},
            ).one()

        stored: tuple[bool, str | None, str | None, str | None, str | None] = (
            bool(row[0]),
            None if row[1] is None else str(row[1]),
            None if row[2] is None else str(row[2]),
            None if row[3] is None else str(row[3]),
            None if row[4] is None else str(row[4]),
        )

        return stored

    def _assembled_caption(self, assembled_id: str) -> str | None:
        """Return the caption stored on one assembled carousel."""

        with self.database_engine.connect() as connection:
            caption: str | None = connection.execute(
                text(
                    """
                    SELECT caption
                    FROM assembled_carousels
                    WHERE id = CAST(:assembled_id AS uuid)
                    """
                ),
                {"assembled_id": assembled_id},
            ).scalar_one()

        return caption

    def _assembled_cta_url(self, assembled_id: str) -> str | None:
        """Return the link stored on one assembled carousel."""

        with self.database_engine.connect() as connection:
            cta_url: str | None = connection.execute(
                text(
                    """
                    SELECT cta_url
                    FROM assembled_carousels
                    WHERE id = CAST(:assembled_id AS uuid)
                    """
                ),
                {"assembled_id": assembled_id},
            ).scalar_one()

        return cta_url

    def _assembly_ids(self) -> set[str]:
        """Return every assembly id."""

        with self.database_engine.connect() as connection:
            assembly_ids: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text("SELECT id::text FROM carousel_assemblies"),
                ).fetchall()
            }

        return assembly_ids

    def _frame_ids(self) -> set[str]:
        """Return every frame id."""

        with self.database_engine.connect() as connection:
            frame_ids: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text("SELECT id::text FROM assembled_carousel_frames"),
                ).fetchall()
            }

        return frame_ids

    def _slide_ids(self) -> set[str]:
        """Return every slide id."""

        with self.database_engine.connect() as connection:
            slide_ids: set[str] = {
                str(row[0])
                for row in connection.execute(text("SELECT id::text FROM slides")).fetchall()
            }

        return slide_ids

    def _carousel_ids_with_assemblies(self) -> set[str]:
        """Return carousel ids that still have an assembly row."""

        with self.database_engine.connect() as connection:
            carousel_ids: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text("SELECT carousel_id::text FROM carousel_assemblies"),
                ).fetchall()
            }

        return carousel_ids

    def _default_album_id(self) -> str:
        """Return the Default album id seeded by the earlier revisions."""

        with self.database_engine.connect() as connection:
            album_id: str = str(
                connection.execute(
                    text("SELECT id::text FROM albums WHERE slug = :slug"),
                    {"slug": DEFAULT_ALBUM_SLUG},
                ).scalar_one(),
            )

        return album_id

    def _column_names(self, table_name: str) -> set[str]:
        """Return column names on one table."""

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

    def _column_names_in_order(self, table_name: str) -> list[str]:
        """Return column names in table order."""

        with self.database_engine.connect() as connection:
            names: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                        ORDER BY ordinal_position
                        """
                    ),
                    {"table_name": table_name},
                ).fetchall()
            ]

        return names

    def _column_nullable(self, table_name: str, column_name: str) -> str:
        """Return YES or NO for one column."""

        with self.database_engine.connect() as connection:
            nullable: str = str(
                connection.execute(
                    text(
                        """
                        SELECT is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                          AND column_name = :column_name
                        """
                    ),
                    {"table_name": table_name, "column_name": column_name},
                ).scalar_one(),
            )

        return nullable

    def _check_names(self, table_name: str) -> set[str]:
        """Return check-constraint names on one table."""

        with self.database_engine.connect() as connection:
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

    def _delete_actions(self, table_name: str) -> dict[str, str]:
        """Return Postgres ON DELETE actions for one table's foreign keys."""

        with self.database_engine.connect() as connection:
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
                        WHERE pg_class.relname = :table_name
                          AND pg_constraint.contype = 'f'
                        """
                    ),
                    {"table_name": table_name},
                ).fetchall()
            }

        return actions

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
