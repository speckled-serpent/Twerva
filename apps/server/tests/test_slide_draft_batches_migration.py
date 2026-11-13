"""Add slide draft batches without changing slides that already exist."""

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
PREVIOUS_REVISION: str = "carousel_instructions_drop_guidance"
BATCH_REVISION: str = "slide_draft_batches"
SKELETON_ID: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb11"
ELEMENT_ID: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb12"
DRAFT_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaab01"
OTHER_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaab02"
CASCADE_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaab03"
SLIDE_ID: str = "dddddddd-dddd-4ddd-8ddd-dddddddddd11"
TEXT_ID: str = "dddddddd-dddd-4ddd-8ddd-dddddddddd12"
RESEARCH_ID: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeee11"
DRAFT_SLUG: str = "draft-already"
OTHER_SLUG: str = "other-pending"
CASCADE_SLUG: str = "cascade-batch"
DRAFT_VALUE: str = "Keep the quay"
LIVE_VALUE: str = ""
DRAFT_GENERATION: int = 7
DRAFT_EDITOR_STEP: int = 2
PENDING_INDEX: str = "uq_slide_draft_batches_one_pending_carousel"

SlideSnapshot = tuple[str, str, int, str, str, str | None]
TextSnapshot = tuple[str, str, str, str | None]
IdentitySnapshot = tuple[str | None, int]


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
class SlideDraftBatchesMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again while a draft slide already exists."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_batch_{uuid.uuid4().hex[:10]}"
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

    def test_upgrade_downgrade_upgrade_keeps_existing_slides(self) -> None:
        """A draft slide stays a draft. Default stays six live slides and no batch."""

        self._upgrade(PREVIOUS_REVISION)
        album_image_id: str = self._first_default_album_image_id()
        self._insert_existing_rows(album_image_id)
        before_slides: list[SlideSnapshot] = self._slide_rows()
        before_texts: list[TextSnapshot] = self._text_rows()
        before_identity: dict[str, IdentitySnapshot] = self._identity_rows()
        before_research: list[tuple[str, str, int]] = self._research_rows()
        before_instructions: list[tuple[str, int, str]] = self._instruction_rows()
        before_text_status_default: str = self._column_default("slides", "text_status")

        self._assert_default_before_upgrade()
        self.assertIn("live", before_text_status_default)
        self.assertEqual(before_identity[DRAFT_SLUG], (self._default_album_id(), DRAFT_GENERATION))

        self._upgrade(BATCH_REVISION)
        self._assert_existing_rows(
            before_slides,
            before_texts,
            before_identity,
            before_research,
            before_instructions,
        )
        self._assert_default_after_upgrade()
        self.assertEqual(self._batch_rows(), [])
        self.assertIn("live", self._column_default("slides", "text_status"))
        self._assert_table_shape()
        self._assert_one_pending_batch()
        self._assert_deleting_a_batch_keeps_the_slide()
        self._assert_existing_rows(
            before_slides,
            before_texts,
            before_identity,
            before_research,
            before_instructions,
        )

        self._downgrade(PREVIOUS_REVISION)
        self._assert_downgraded(
            before_slides,
            before_texts,
            before_identity,
            before_research,
            before_instructions,
        )

        self._upgrade(BATCH_REVISION)
        self._assert_existing_rows(
            before_slides,
            before_texts,
            before_identity,
            before_research,
            before_instructions,
        )
        self._assert_default_after_upgrade()
        self.assertEqual(self._batch_rows(), [])

    def _assert_default_before_upgrade(self) -> None:
        """Default already has six live slides before this revision."""

        slides: list[tuple[str, str, str | None]] = self._slides_for_slug(DEFAULT_ALBUM_SLUG)

        self.assertEqual(len(slides), 6)

        for _slide_id, text_status, album_image_id in slides:
            self.assertEqual(text_status, "live")
            self.assertIsNotNone(album_image_id)

    def _assert_default_after_upgrade(self) -> None:
        """Default still has six live slides, each with a null batch pointer."""

        slides: list[tuple[str, str, str | None, str | None]] = self._slides_with_batch(
            DEFAULT_ALBUM_SLUG,
        )

        self.assertEqual(len(slides), 6)

        for _slide_id, text_status, album_image_id, draft_batch_id in slides:
            self.assertEqual(text_status, "live")
            self.assertIsNotNone(album_image_id)
            self.assertIsNone(draft_batch_id)

        self.assertNotIn(DEFAULT_ALBUM_SLUG, {row[0] for row in self._batch_rows()})

    def _assert_existing_rows(
        self,
        before_slides: list[SlideSnapshot],
        before_texts: list[TextSnapshot],
        before_identity: dict[str, IdentitySnapshot],
        before_research: list[tuple[str, str, int]],
        before_instructions: list[tuple[str, int, str]],
    ) -> None:
        """The revision does not rewrite slides, albums, research, or instructions."""

        draft_slide: SlideSnapshot = next(
            row for row in self._slide_rows() if row[0] == SLIDE_ID
        )
        draft_text: TextSnapshot = next(
            row for row in self._text_rows() if row[0] == SLIDE_ID
        )
        pointers: dict[str, str | None] = self._draft_batch_pointers()

        self.assertEqual(self._slide_rows(), before_slides)
        self.assertEqual(self._text_rows(), before_texts)
        self.assertEqual(self._identity_rows(), before_identity)
        self.assertEqual(self._research_rows(), before_research)
        self.assertEqual(self._instruction_rows(), before_instructions)
        self.assertEqual(draft_slide[4], "draft")
        self.assertEqual(draft_text[2], LIVE_VALUE)
        self.assertEqual(draft_text[3], DRAFT_VALUE)
        self.assertIsNone(pointers[SLIDE_ID])
        self.assertEqual(before_identity[DRAFT_SLUG][1], DRAFT_GENERATION)
        self.assertIsNotNone(self._regclass("albums"))
        self.assertIsNotNone(self._regclass("carousel_research_items"))
        self.assertIsNotNone(self._regclass("carousel_instructions"))
        self.assertIsNotNone(self._regclass("slides"))

    def _assert_downgraded(
        self,
        before_slides: list[SlideSnapshot],
        before_texts: list[TextSnapshot],
        before_identity: dict[str, IdentitySnapshot],
        before_research: list[tuple[str, str, int]],
        before_instructions: list[tuple[str, int, str]],
    ) -> None:
        """The pointer and the table are gone. Slides and the other libraries stay."""

        self.assertIsNone(self._regclass("slide_draft_batches"))
        self.assertNotIn("draft_batch_id", self._column_names("slides"))
        self.assertEqual(self._slide_rows(), before_slides)
        self.assertEqual(self._text_rows(), before_texts)
        self.assertEqual(self._identity_rows(), before_identity)
        self.assertEqual(self._research_rows(), before_research)
        self.assertEqual(self._instruction_rows(), before_instructions)
        self.assertIn("live", self._column_default("slides", "text_status"))
        self.assertIn("draft_value", self._column_names("slide_element_texts"))
        self.assertIsNotNone(self._regclass("albums"))
        self.assertIsNotNone(self._regclass("carousel_research_items"))
        self.assertIsNotNone(self._regclass("carousel_instructions"))
        self.assertIsNotNone(self._regclass("slides"))
        self.assertIsNotNone(self._regclass("campaign_carousels"))

    def _assert_table_shape(self) -> None:
        """The batch table, the pointer, and the partial index match the revision."""

        check_names: set[str] = self._check_names("slide_draft_batches")
        batch_actions: dict[str, str] = self._delete_actions("slide_draft_batches")
        slide_actions: dict[str, str] = self._delete_actions("slides")
        draft_batch_default: str | None = self._column_default_or_none("slides", "draft_batch_id")

        self.assertEqual(
            self._column_names_in_order("slide_draft_batches"),
            ["id", "carousel_id", "status", "slide_count", "created_at", "updated_at"],
        )
        self.assertIn("draft_batch_id", self._column_names("slides"))
        self.assertIsNone(draft_batch_default)
        self.assertEqual(self._column_nullable("slides", "draft_batch_id"), "YES")
        self.assertIn("ck_slide_draft_batches_status", check_names)
        self.assertIn("ck_slide_draft_batches_slide_count", check_names)
        self.assertNotIn("ck_slide_draft_batches_ck_slide_draft_batches_status", check_names)
        self.assertNotIn(
            "ck_slide_draft_batches_ck_slide_draft_batches_slide_count",
            check_names,
        )
        self.assertEqual(batch_actions["carousel_id"], "c")
        self.assertEqual(slide_actions["draft_batch_id"], "n")
        self.assertIn(PENDING_INDEX, self._index_names("slide_draft_batches"))
        self.assertIn("ix_slides_draft_batch_id", self._index_names("slides"))
        self.assertIn("UNIQUE", self._index_definition(PENDING_INDEX).upper())
        self.assertIn("status = 'pending'", self._index_definition(PENDING_INDEX))

    def _assert_one_pending_batch(self) -> None:
        """One carousel holds one pending row. An accepted row can sit beside it."""

        accepted_id: str = self._insert_batch(DRAFT_CAROUSEL_ID, "accepted", 5)
        second_accepted_id: str = self._insert_batch(DRAFT_CAROUSEL_ID, "accepted", 8)
        pending_id: str = self._insert_batch(DRAFT_CAROUSEL_ID, "pending", 6)
        other_pending_id: str = self._insert_batch(OTHER_CAROUSEL_ID, "pending", 1)

        with self.assertRaises(IntegrityError) as pending_error:
            self._insert_batch(DRAFT_CAROUSEL_ID, "pending", 6)

        with self.assertRaises(IntegrityError) as count_error:
            self._insert_batch(DRAFT_CAROUSEL_ID, "discarded", 0)

        with self.assertRaises(IntegrityError) as status_error:
            self._insert_batch(DRAFT_CAROUSEL_ID, "live", 1)

        stored_statuses: set[str] = {
            row[1]
            for row in self._batch_rows()
            if row[0] == DRAFT_SLUG
        }

        self.assertIn(PENDING_INDEX, str(pending_error.exception))
        self.assertIn("ck_slide_draft_batches_slide_count", str(count_error.exception))
        self.assertIn("ck_slide_draft_batches_status", str(status_error.exception))
        self.assertEqual(stored_statuses, {"accepted", "pending"})
        self.assertEqual(
            {row[2] for row in self._batch_rows() if row[3] == accepted_id},
            {5},
        )
        self.assertIn(second_accepted_id, {row[3] for row in self._batch_rows()})
        self.assertIn(pending_id, {row[3] for row in self._batch_rows()})
        self.assertIn(other_pending_id, {row[3] for row in self._batch_rows()})
        self.pending_id: str = pending_id

    def _assert_deleting_a_batch_keeps_the_slide(self) -> None:
        """Deleting the batch clears the pointer and leaves the slide and its draft."""

        self._point_slide_at_batch(SLIDE_ID, self.pending_id)
        self._delete_batch(self.pending_id)
        draft_slide: SlideSnapshot = next(
            row for row in self._slide_rows() if row[0] == SLIDE_ID
        )
        draft_text: TextSnapshot = next(
            row for row in self._text_rows() if row[0] == SLIDE_ID
        )

        self.assertEqual(draft_slide[4], "draft")
        self.assertIsNotNone(draft_slide[5])
        self.assertEqual(draft_text[3], DRAFT_VALUE)
        self.assertIsNone(self._draft_batch_pointers()[SLIDE_ID])
        self.assertNotIn(self.pending_id, {row[3] for row in self._batch_rows()})
        self.assertIn(SLIDE_ID, {row[0] for row in self._slide_rows()})
        self._assert_cascade_drops_the_batch()

    def _assert_cascade_drops_the_batch(self) -> None:
        """Deleting a carousel drops its batch and leaves the other carousel's rows."""

        self._insert_carousel(CASCADE_CAROUSEL_ID, CASCADE_SLUG, None, 3, 1)
        cascade_batch_id: str = self._insert_batch(CASCADE_CAROUSEL_ID, "pending", 5)

        with self.database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM carousels WHERE id = CAST(:carousel_id AS uuid)"),
                {"carousel_id": CASCADE_CAROUSEL_ID},
            )

        batch_ids: set[str] = {row[3] for row in self._batch_rows()}

        self.assertNotIn(cascade_batch_id, batch_ids)
        self.assertIn(DRAFT_SLUG, {row[0] for row in self._batch_rows()})
        self.assertIn(SLIDE_ID, {row[0] for row in self._slide_rows()})

    def _insert_existing_rows(self, album_image_id: str) -> None:
        """Add a draft slide, research, and an instruction before the revision."""

        default_album_id: str = self._default_album_id()

        self._insert_skeleton()
        self._insert_text_element()
        self._insert_carousel(
            DRAFT_CAROUSEL_ID,
            DRAFT_SLUG,
            default_album_id,
            DRAFT_EDITOR_STEP,
            DRAFT_GENERATION,
        )
        self._insert_carousel(
            OTHER_CAROUSEL_ID,
            OTHER_SLUG,
            None,
            0,
            1,
        )
        self._insert_slide(album_image_id)
        self._insert_element_text()
        self._insert_research()
        self._attach_research()
        self._insert_instruction()

    def _insert_skeleton(self) -> None:
        """Insert one color skeleton for the pre-existing draft carousel."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeletons (
                        id, name, slug, advertisement_type, background_kind
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        'Batch paper',
                        'batch-paper',
                        'carousel',
                        'color'::background_kind
                    )
                    """
                ),
                {"skeleton_id": SKELETON_ID},
            )

    def _insert_text_element(self) -> None:
        """Add the text element whose draft value must survive the revision."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeleton_elements (
                        id, skeleton_id, band, sort_order, content_kind, name,
                        font_family, font_size, font_color, alignment
                    )
                    VALUES (
                        CAST(:element_id AS uuid),
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
                {"element_id": ELEMENT_ID, "skeleton_id": SKELETON_ID},
            )

    def _insert_carousel(
        self,
        carousel_id: str,
        slug: str,
        album_id: str | None,
        editor_step: int,
        generation_number: int,
    ) -> None:
        """Insert one carousel on the batch skeleton."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, album_id,
                        editor_step, generation_number
                    )
                    VALUES (
                        CAST(:carousel_id AS uuid),
                        CAST(:skeleton_id AS uuid),
                        :name,
                        :slug,
                        CAST(:album_id AS uuid),
                        :editor_step,
                        :generation_number
                    )
                    """
                ),
                {
                    "carousel_id": carousel_id,
                    "skeleton_id": SKELETON_ID,
                    "name": slug,
                    "slug": slug,
                    "album_id": album_id,
                    "editor_step": editor_step,
                    "generation_number": generation_number,
                },
            )

    def _insert_slide(self, album_image_id: str) -> None:
        """Insert a draft slide that already points at an album image."""

        with self.database_engine.begin() as connection:
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
                        'Quay',
                        'draft',
                        CAST(:album_image_id AS uuid)
                    )
                    """
                ),
                {
                    "slide_id": SLIDE_ID,
                    "carousel_id": DRAFT_CAROUSEL_ID,
                    "album_image_id": album_image_id,
                },
            )

    def _insert_element_text(self) -> None:
        """Store a live value and a draft value on the pre-existing slide."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO slide_element_texts (
                        id, slide_id, skeleton_element_id, value, draft_value
                    )
                    VALUES (
                        CAST(:text_id AS uuid),
                        CAST(:slide_id AS uuid),
                        CAST(:element_id AS uuid),
                        :value,
                        :draft_value
                    )
                    """
                ),
                {
                    "text_id": TEXT_ID,
                    "slide_id": SLIDE_ID,
                    "element_id": ELEMENT_ID,
                    "value": LIVE_VALUE,
                    "draft_value": DRAFT_VALUE,
                },
            )

    def _insert_research(self) -> None:
        """Insert one research document. This revision does not read it."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (
                        CAST(:research_id AS uuid),
                        'Harbor notes',
                        'harbor-batch-notes',
                        'The tide is out.'
                    )
                    """
                ),
                {"research_id": RESEARCH_ID},
            )

    def _attach_research(self) -> None:
        """Link the research document. The link stays through both directions."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_research_items (
                        carousel_id, research_item_id, position
                    )
                    VALUES (
                        CAST(:carousel_id AS uuid),
                        CAST(:research_id AS uuid),
                        0
                    )
                    """
                ),
                {
                    "carousel_id": DRAFT_CAROUSEL_ID,
                    "research_id": RESEARCH_ID,
                },
            )

    def _insert_instruction(self) -> None:
        """Store one instruction document. This revision does not read it."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_instructions (carousel_id, position, body)
                    VALUES (CAST(:carousel_id AS uuid), 0, 'Name the quay.')
                    """
                ),
                {"carousel_id": DRAFT_CAROUSEL_ID},
            )

    def _insert_batch(self, carousel_id: str, status: str, slide_count: int) -> str:
        """Insert one batch row. The caller expects success or a constraint error."""

        with self.database_engine.begin() as connection:
            batch_id: str = str(
                connection.execute(
                    text(
                        """
                        INSERT INTO slide_draft_batches (carousel_id, status, slide_count)
                        VALUES (CAST(:carousel_id AS uuid), :status, :slide_count)
                        RETURNING id::text
                        """
                    ),
                    {
                        "carousel_id": carousel_id,
                        "status": status,
                        "slide_count": slide_count,
                    },
                ).scalar_one(),
            )

        return batch_id

    def _point_slide_at_batch(self, slide_id: str, batch_id: str) -> None:
        """Set the slide pointer. Deleting the batch must clear it again."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE slides
                    SET draft_batch_id = CAST(:batch_id AS uuid)
                    WHERE id = CAST(:slide_id AS uuid)
                    """
                ),
                {"slide_id": slide_id, "batch_id": batch_id},
            )

    def _delete_batch(self, batch_id: str) -> None:
        """Delete one batch. Slides that pointed at it stay."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM slide_draft_batches WHERE id = CAST(:batch_id AS uuid)"),
                {"batch_id": batch_id},
            )

    def _slide_rows(self) -> list[SlideSnapshot]:
        """Return slide identity, status, and image pointer. The batch pointer is separate."""

        with self.database_engine.connect() as connection:
            slides: list[SlideSnapshot] = [
                (
                    str(row[0]),
                    str(row[1]),
                    int(row[2]),
                    str(row[3]),
                    str(row[4]),
                    None if row[5] is None else str(row[5]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            id::text,
                            carousel_id::text,
                            position,
                            name,
                            text_status::text,
                            album_image_id::text
                        FROM slides
                        ORDER BY id
                        """
                    ),
                ).fetchall()
            ]

        return slides

    def _text_rows(self) -> list[TextSnapshot]:
        """Return live text and draft text for every element row."""

        with self.database_engine.connect() as connection:
            texts: list[TextSnapshot] = [
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
                            slide_id::text,
                            skeleton_element_id::text,
                            value,
                            draft_value
                        FROM slide_element_texts
                        ORDER BY slide_id, skeleton_element_id
                        """
                    ),
                ).fetchall()
            ]

        return texts

    def _identity_rows(self) -> dict[str, IdentitySnapshot]:
        """Return album and generation by carousel slug."""

        with self.database_engine.connect() as connection:
            rows: dict[str, IdentitySnapshot] = {
                str(row[0]): (
                    None if row[1] is None else str(row[1]),
                    int(row[2]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT slug, album_id::text, generation_number
                        FROM carousels
                        """
                    ),
                ).fetchall()
            }

        return rows

    def _research_rows(self) -> list[tuple[str, str, int]]:
        """Return research links in carousel and position order."""

        with self.database_engine.connect() as connection:
            links: list[tuple[str, str, int]] = [
                (str(row[0]), str(row[1]), int(row[2]))
                for row in connection.execute(
                    text(
                        """
                        SELECT carousel_id::text, research_item_id::text, position
                        FROM carousel_research_items
                        ORDER BY carousel_id, position
                        """
                    ),
                ).fetchall()
            ]

        return links

    def _instruction_rows(self) -> list[tuple[str, int, str]]:
        """Return instruction documents in carousel and position order."""

        with self.database_engine.connect() as connection:
            documents: list[tuple[str, int, str]] = [
                (str(row[0]), int(row[1]), str(row[2]))
                for row in connection.execute(
                    text(
                        """
                        SELECT carousel_id::text, position, body
                        FROM carousel_instructions
                        ORDER BY carousel_id, position
                        """
                    ),
                ).fetchall()
            ]

        return documents

    def _batch_rows(self) -> list[tuple[str, str, int, str]]:
        """Return slug, status, slide count, and id for every batch."""

        with self.database_engine.connect() as connection:
            batches: list[tuple[str, str, int, str]] = [
                (str(row[0]), str(row[1]), int(row[2]), str(row[3]))
                for row in connection.execute(
                    text(
                        """
                        SELECT carousel.slug, batch.status, batch.slide_count, batch.id::text
                        FROM slide_draft_batches AS batch
                        JOIN carousels AS carousel ON carousel.id = batch.carousel_id
                        ORDER BY carousel.slug, batch.status, batch.slide_count, batch.id
                        """
                    ),
                ).fetchall()
            ]

        return batches

    def _slides_for_slug(self, slug: str) -> list[tuple[str, str, str | None]]:
        """Return id, text status, and album image for one carousel."""

        with self.database_engine.connect() as connection:
            slides: list[tuple[str, str, str | None]] = [
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

    def _slides_with_batch(self, slug: str) -> list[tuple[str, str, str | None, str | None]]:
        """Return id, text status, album image, and batch pointer for one carousel."""

        with self.database_engine.connect() as connection:
            slides: list[tuple[str, str, str | None, str | None]] = [
                (
                    str(row[0]),
                    str(row[1]),
                    None if row[2] is None else str(row[2]),
                    None if row[3] is None else str(row[3]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            slide.id::text,
                            slide.text_status::text,
                            slide.album_image_id::text,
                            slide.draft_batch_id::text
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

    def _draft_batch_pointers(self) -> dict[str, str | None]:
        """Return draft_batch_id by slide id."""

        with self.database_engine.connect() as connection:
            pointers: dict[str, str | None] = {
                str(row[0]): None if row[1] is None else str(row[1])
                for row in connection.execute(
                    text("SELECT id::text, draft_batch_id::text FROM slides"),
                ).fetchall()
            }

        return pointers

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

    def _first_default_album_image_id(self) -> str:
        """Return one packaged photo so the draft slide can keep a real pointer."""

        with self.database_engine.connect() as connection:
            image_id: str = str(
                connection.execute(
                    text(
                        """
                        SELECT image.id::text
                        FROM album_images AS image
                        JOIN albums AS album ON album.id = image.album_id
                        WHERE album.slug = :slug
                        ORDER BY image.position
                        LIMIT 1
                        """
                    ),
                    {"slug": DEFAULT_ALBUM_SLUG},
                ).scalar_one(),
            )

        return image_id

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

    def _column_default(self, table_name: str, column_name: str) -> str:
        """Return the server default expression. The column must have one."""

        column_default: str | None = self._column_default_or_none(table_name, column_name)

        self.assertIsNotNone(column_default)

        return str(column_default)

    def _column_default_or_none(self, table_name: str, column_name: str) -> str | None:
        """Return the server default expression, or None when the column has none."""

        with self.database_engine.connect() as connection:
            column_default: object = connection.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                      AND column_name = :column_name
                    """
                ),
                {"table_name": table_name, "column_name": column_name},
            ).scalar_one()

        if column_default is None:

            return None

        return str(column_default)

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

    def _index_names(self, table_name: str) -> set[str]:
        """Return index names on one table."""

        with self.database_engine.connect() as connection:
            names: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                          AND tablename = :table_name
                        """
                    ),
                    {"table_name": table_name},
                ).fetchall()
            }

        return names

    def _index_definition(self, index_name: str) -> str:
        """Return the CREATE INDEX statement for one index."""

        with self.database_engine.connect() as connection:
            definition: str = str(
                connection.execute(
                    text(
                        """
                        SELECT indexdef
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                          AND indexname = :index_name
                        """
                    ),
                    {"index_name": index_name},
                ).scalar_one(),
            )

        return definition

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
