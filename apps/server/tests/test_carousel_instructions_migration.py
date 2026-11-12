"""Copy inspiration and rules into instruction documents, then drop the copy."""

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
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.carousel_text import generate_slide_text, generate_source_slide
from app.api.v1.schemas import SlideReadResponse
from app.carousels.default_carousel import DEFAULT_ALBUM_SLUG
from app.models.carousel import INSTRUCTION_BODY_MAX_CHARACTERS
from app.models.enums import SlideTextStatus
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
CONTENT_REVISION: str = "carousel_editor_step_content"
INSTRUCTIONS_REVISION: str = "carousel_instructions"
DROP_GUIDANCE_REVISION: str = "carousel_instructions_drop_guidance"
EDITOR_STEP_INSTRUCTIONS_REVISION: str = "carousel_editor_step_instructions"
SKELETON_ID: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb01"
ALBUM_ID: str = "cccccccc-cccc-4ccc-8ccc-cccccccccc01"
BOTH_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01"
RULES_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02"
BLANK_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa03"
SPACE_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa04"
CASCADE_CAROUSEL_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa05"
SLIDE_ID: str = "dddddddd-dddd-4ddd-8ddd-dddddddddd01"
RESEARCH_ID: str = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeee01"
BOTH_SLUG: str = "both-guidance"
RULES_SLUG: str = "rules-only"
BLANK_SLUG: str = "blank-guidance"
SPACE_SLUG: str = "space-guidance"
BOTH_INSPIRATION: str = "A lamp on the quay"
BOTH_RULES: str = "Keep the tide in the caption"
RULES_INSPIRATION: str = ""
RULES_RULES: str = "Name the quay"
SPACE_INSPIRATION: str = "   "
SPACE_RULES: str = "  "
BOTH_EDITOR_STEP: int = 0
RULES_EDITOR_STEP: int = 2
BLANK_EDITOR_STEP: int = 3
SPACE_EDITOR_STEP: int = 0
BOTH_GENERATION: int = 4
SLIDE_NAME: str = "Quay"
TEXT_ELEMENT_NAME: str = "Title"

CarouselSnapshot = tuple[str, str, str | None, int, int]
SlideSnapshot = tuple[str, str, int, str, str | None]
ResearchSnapshot = tuple[str, str, int]
InstructionSnapshot = tuple[int, str]


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


def _copied_instruction_body(inspiration: str, rules: str) -> str:
    """Return the document upgrade stores for two column values.

    Args:
        inspiration: The stored inspiration, including a blank string.
        rules: The stored rules, including a blank string.

    Returns:
        The heading template, ending with a newline.
    """

    body: str = (
        "## Inspiration\n"
        "\n"
        f"{inspiration}\n"
        "\n"
        "## Rules\n"
        "\n"
        f"{rules}\n"
    )

    return body


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for migration tests")
class CarouselInstructionsMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again while guidance rows already exist."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_instr_{uuid.uuid4().hex[:10]}"
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

    def test_upgrade_downgrade_upgrade_copies_guidance_into_one_document(self) -> None:
        """One document per carousel that has text. Blank guidance stays a column."""

        self._upgrade(CONTENT_REVISION)
        self._insert_existing_rows()
        before_carousels: dict[str, CarouselSnapshot] = self._carousel_rows()
        before_slides: list[SlideSnapshot] = self._slide_rows()
        before_research: list[ResearchSnapshot] = self._research_rows()
        before_editor_check: str = self._editor_step_check()

        self._upgrade(INSTRUCTIONS_REVISION)
        self._assert_copied_documents(before_carousels, before_slides, before_research)
        self.assertEqual(self._editor_step_check(), before_editor_check)
        self._assert_rejected_editor_step()

        self._downgrade(CONTENT_REVISION)
        self._assert_downgraded(before_carousels, before_slides, before_research)

        self._upgrade(INSTRUCTIONS_REVISION)
        self._assert_copied_documents(before_carousels, before_slides, before_research)
        self._assert_table_checks()
        self._assert_cascade_drops_the_document()
        self._assert_generate_still_reads_the_columns()

    def test_dropping_guidance_keeps_the_copied_documents(self) -> None:
        """Upgrade from the copy keeps documents. Downgrade restores empty columns."""

        self._upgrade(CONTENT_REVISION)
        self._insert_existing_rows()
        self._upgrade(INSTRUCTIONS_REVISION)
        documents_after_copy: dict[str, list[InstructionSnapshot]] = self._instruction_rows()
        identity_after_copy: dict[str, tuple[str | None, int, int]] = (
            self._carousel_identity_rows()
        )

        self._upgrade(DROP_GUIDANCE_REVISION)

        self.assertNotIn("inspiration", self._carousel_column_names())
        self.assertNotIn("rules", self._carousel_column_names())
        self.assertEqual(self._instruction_rows(), documents_after_copy)
        self.assertNotIn(DEFAULT_ALBUM_SLUG, self._instruction_rows())
        self.assertEqual(self._carousel_identity_rows(), identity_after_copy)
        self.assertIsNotNone(self._regclass("carousel_instructions"))
        self._assert_generate_drafts_from_the_copied_document()
        self.assertEqual(self._instruction_rows(), documents_after_copy)

        self._downgrade(EDITOR_STEP_INSTRUCTIONS_REVISION)

        self.assertEqual(self._instruction_rows(), documents_after_copy)
        self.assertNotIn(DEFAULT_ALBUM_SLUG, self._instruction_rows())
        self.assertEqual(self._carousel_identity_rows(), identity_after_copy)
        self._assert_restored_guidance_columns_are_empty()

    def _assert_copied_documents(
        self,
        before_carousels: dict[str, CarouselSnapshot],
        before_slides: list[SlideSnapshot],
        before_research: list[ResearchSnapshot],
    ) -> None:
        """Copied bodies match the template. Everything else is unchanged."""

        documents: dict[str, list[InstructionSnapshot]] = self._instruction_rows()
        both_body: str = _copied_instruction_body(BOTH_INSPIRATION, BOTH_RULES)
        rules_body: str = _copied_instruction_body(RULES_INSPIRATION, RULES_RULES)

        self.assertEqual(self._carousel_rows(), before_carousels)
        self.assertEqual(self._slide_rows(), before_slides)
        self.assertEqual(self._research_rows(), before_research)
        self.assertEqual(before_carousels[DEFAULT_ALBUM_SLUG][0], "")
        self.assertEqual(before_carousels[DEFAULT_ALBUM_SLUG][1], "")
        self.assertEqual(before_carousels[BOTH_SLUG][0], BOTH_INSPIRATION)
        self.assertEqual(before_carousels[BOTH_SLUG][1], BOTH_RULES)
        self.assertEqual(before_carousels[BOTH_SLUG][2], ALBUM_ID)
        self.assertEqual(before_carousels[BOTH_SLUG][3], BOTH_EDITOR_STEP)
        self.assertEqual(before_carousels[BOTH_SLUG][4], BOTH_GENERATION)
        self.assertEqual(before_carousels[RULES_SLUG][0], "")
        self.assertEqual(before_carousels[RULES_SLUG][1], RULES_RULES)
        self.assertEqual(before_carousels[BLANK_SLUG][0], "")
        self.assertEqual(before_carousels[BLANK_SLUG][1], "")
        self.assertEqual(before_carousels[SPACE_SLUG][0], SPACE_INSPIRATION)
        self.assertEqual(before_carousels[SPACE_SLUG][1], SPACE_RULES)
        self.assertEqual(documents[BOTH_SLUG], [(0, both_body)])
        self.assertEqual(documents[RULES_SLUG], [(0, rules_body)])
        self.assertNotIn(DEFAULT_ALBUM_SLUG, documents)
        self.assertNotIn(BLANK_SLUG, documents)
        self.assertNotIn(SPACE_SLUG, documents)
        self.assertEqual(set(documents), {BOTH_SLUG, RULES_SLUG})
        self.assertTrue(both_body.endswith("\n"))
        self.assertTrue(rules_body.startswith("## Inspiration\n\n\n\n## Rules\n\n"))
        self.assertIn("inspiration", self._carousel_column_names())
        self.assertIn("rules", self._carousel_column_names())
        self.assertEqual(
            self._instruction_column_names(),
            ["id", "carousel_id", "position", "body", "created_at", "updated_at"],
        )

    def _assert_downgraded(
        self,
        before_carousels: dict[str, CarouselSnapshot],
        before_slides: list[SlideSnapshot],
        before_research: list[ResearchSnapshot],
    ) -> None:
        """The document table is gone. Guidance, steps, albums, and slides stay."""

        self.assertIsNone(self._regclass("carousel_instructions"))
        self.assertEqual(self._carousel_rows(), before_carousels)
        self.assertEqual(self._slide_rows(), before_slides)
        self.assertEqual(self._research_rows(), before_research)
        self.assertIn("inspiration", self._carousel_column_names())
        self.assertIn("rules", self._carousel_column_names())
        self.assertIsNotNone(self._regclass("carousels"))
        self.assertIsNotNone(self._regclass("slides"))
        self.assertIsNotNone(self._regclass("carousel_research_items"))

    def _assert_table_checks(self) -> None:
        """Position, body length, and the pair of columns are enforced."""

        check_names: set[str] = self._check_names("carousel_instructions")
        at_limit: str = "a" * INSTRUCTION_BODY_MAX_CHARACTERS
        over_limit: str = "b" * (INSTRUCTION_BODY_MAX_CHARACTERS + 1)

        self.assertIn("ck_carousel_instructions_position", check_names)
        self.assertIn("ck_carousel_instructions_body", check_names)
        self.assertNotIn(
            "ck_carousel_instructions_ck_carousel_instructions_position",
            check_names,
        )
        self.assertNotIn(
            "ck_carousel_instructions_ck_carousel_instructions_body",
            check_names,
        )
        self.assertEqual(self._delete_actions(), {"carousel_id": "c"})
        self.assertIn("''", self._column_default("body"))

        with self.assertRaises(IntegrityError):
            self._insert_instruction(BLANK_CAROUSEL_ID, -1, "nope")

        with self.assertRaises(IntegrityError):
            self._insert_instruction(BOTH_CAROUSEL_ID, 0, "second")

        with self.assertRaises(IntegrityError):
            self._insert_instruction(BLANK_CAROUSEL_ID, 0, over_limit)

        self._insert_instruction(BLANK_CAROUSEL_ID, 0, at_limit)
        self.assertEqual(
            self._instruction_rows()[BLANK_SLUG],
            [(0, at_limit)],
        )
        self._delete_instructions(BLANK_CAROUSEL_ID)
        self.assertNotIn(BLANK_SLUG, self._instruction_rows())

    def _assert_rejected_editor_step(self) -> None:
        """Step 1 is still refused. The stored step stays."""

        with self.assertRaises(IntegrityError):
            self._set_editor_step(BOTH_CAROUSEL_ID, 1)

        stored_step: int = self._carousel_rows()[BOTH_SLUG][3]

        self.assertEqual(stored_step, BOTH_EDITOR_STEP)

    def _assert_cascade_drops_the_document(self) -> None:
        """Deleting a carousel drops its document and leaves the other rows."""

        self._insert_carousel(
            CASCADE_CAROUSEL_ID,
            "cascade-guidance",
            "",
            "",
            None,
            3,
            1,
        )
        self._insert_instruction(CASCADE_CAROUSEL_ID, 0, "Temporary")

        with self.database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM carousels WHERE id = CAST(:carousel_id AS uuid)"),
                {"carousel_id": CASCADE_CAROUSEL_ID},
            )

        documents: dict[str, list[InstructionSnapshot]] = self._instruction_rows()

        self.assertNotIn("cascade-guidance", documents)
        self.assertIn(BOTH_SLUG, documents)
        self.assertIn(RULES_SLUG, documents)
        self.assertIn(BOTH_CAROUSEL_ID, self._carousel_ids())

    def _assert_generate_still_reads_the_columns(self) -> None:
        """Generate drafts from the copied document. The columns still read back."""

        previous_provider: str | None = os.environ.get("TEXT_GENERATION_PROVIDER")
        os.environ["TEXT_GENERATION_PROVIDER"] = "fake"
        clear_settings_cache()
        session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.database_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        session: Session = session_factory()
        copied_body: str = _copied_instruction_body(BOTH_INSPIRATION, BOTH_RULES).strip()
        expected_draft: str = f"{TEXT_ELEMENT_NAME}. {copied_body}"
        expected_name: str = " ".join(copied_body.split())[:200]
        documents_before: dict[str, list[InstructionSnapshot]] = self._instruction_rows()

        try:
            created: SlideReadResponse = generate_source_slide(
                uuid.UUID(BOTH_CAROUSEL_ID),
                session,
                None,
            )
            drafted: SlideReadResponse = generate_slide_text(
                uuid.UUID(BOTH_CAROUSEL_ID),
                uuid.UUID(SLIDE_ID),
                session,
                None,
            )
        finally:
            session.close()

            if previous_provider is None:
                os.environ.pop("TEXT_GENERATION_PROVIDER", None)
            else:
                os.environ["TEXT_GENERATION_PROVIDER"] = previous_provider

            clear_settings_cache()

        guidance: CarouselSnapshot = self._carousel_rows()[BOTH_SLUG]

        self.assertEqual(created.name, expected_name)
        self.assertEqual(created.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(created.texts[0].value, "")
        self.assertEqual(created.draft_texts[0].value, expected_draft)
        self.assertIn("## Inspiration", created.draft_texts[0].value)
        self.assertIn(BOTH_INSPIRATION, created.draft_texts[0].value)
        self.assertIn(BOTH_RULES, created.draft_texts[0].value)
        self.assertEqual(drafted.name, SLIDE_NAME)
        self.assertEqual(drafted.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(drafted.texts[0].value, "")
        self.assertEqual(drafted.draft_texts[0].value, expected_draft)
        self.assertIn("## Inspiration", drafted.draft_texts[0].value)
        self.assertEqual(guidance[0], BOTH_INSPIRATION)
        self.assertEqual(guidance[1], BOTH_RULES)
        self.assertEqual(self._instruction_rows(), documents_before)

    def _assert_generate_drafts_from_the_copied_document(self) -> None:
        """Generate text after the drop still drafts from the copied body."""

        previous_provider: str | None = os.environ.get("TEXT_GENERATION_PROVIDER")
        os.environ["TEXT_GENERATION_PROVIDER"] = "fake"
        clear_settings_cache()
        session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.database_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        session: Session = session_factory()
        copied_body: str = _copied_instruction_body(BOTH_INSPIRATION, BOTH_RULES).strip()
        expected_draft: str = f"{TEXT_ELEMENT_NAME}. {copied_body}"

        try:
            drafted: SlideReadResponse = generate_slide_text(
                uuid.UUID(BOTH_CAROUSEL_ID),
                uuid.UUID(SLIDE_ID),
                session,
                None,
            )
        finally:
            session.close()

            if previous_provider is None:
                os.environ.pop("TEXT_GENERATION_PROVIDER", None)
            else:
                os.environ["TEXT_GENERATION_PROVIDER"] = previous_provider

            clear_settings_cache()

        self.assertEqual(drafted.name, SLIDE_NAME)
        self.assertEqual(drafted.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(drafted.texts[0].value, "")
        self.assertEqual(drafted.draft_texts[0].value, expected_draft)
        self.assertIn(BOTH_INSPIRATION, drafted.draft_texts[0].value)
        self.assertIn(BOTH_RULES, drafted.draft_texts[0].value)

    def _assert_restored_guidance_columns_are_empty(self) -> None:
        """Downgrade adds both columns back empty, not null, default blank."""

        self.assertIn("inspiration", self._carousel_column_names())
        self.assertIn("rules", self._carousel_column_names())
        restored: dict[str, tuple[str, str]] = self._guidance_column_values()

        for slug, column_values in restored.items():
            self.assertEqual(column_values, ("", ""), slug)

        inspiration_default: tuple[str, str] = self._carousel_column_default("inspiration")
        rules_default: tuple[str, str] = self._carousel_column_default("rules")

        self.assertEqual(inspiration_default[0], "NO")
        self.assertEqual(rules_default[0], "NO")
        self.assertIn("''", inspiration_default[1])
        self.assertIn("''", rules_default[1])

    def _insert_existing_rows(self) -> None:
        """Add guidance that should copy, guidance that should not, and a slide."""

        self._insert_skeleton()
        self._insert_text_element()
        self._insert_album()
        self._insert_carousel(
            BOTH_CAROUSEL_ID,
            BOTH_SLUG,
            BOTH_INSPIRATION,
            BOTH_RULES,
            ALBUM_ID,
            BOTH_EDITOR_STEP,
            BOTH_GENERATION,
        )
        self._insert_carousel(
            RULES_CAROUSEL_ID,
            RULES_SLUG,
            RULES_INSPIRATION,
            RULES_RULES,
            None,
            RULES_EDITOR_STEP,
            1,
        )
        self._insert_carousel(
            BLANK_CAROUSEL_ID,
            BLANK_SLUG,
            "",
            "",
            None,
            BLANK_EDITOR_STEP,
            1,
        )
        self._insert_carousel(
            SPACE_CAROUSEL_ID,
            SPACE_SLUG,
            SPACE_INSPIRATION,
            SPACE_RULES,
            None,
            SPACE_EDITOR_STEP,
            1,
        )
        self._insert_slide()
        self._insert_research()
        self._attach_research()

    def _insert_skeleton(self) -> None:
        """Insert one color skeleton. The album rule does not read it again."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skeletons (
                        id, name, slug, advertisement_type, background_kind
                    )
                    VALUES (
                        CAST(:skeleton_id AS uuid),
                        'Instruction paper',
                        'instruction-paper',
                        'carousel',
                        'color'::background_kind
                    )
                    """
                ),
                {"skeleton_id": SKELETON_ID},
            )

    def _insert_text_element(self) -> None:
        """Add the text element Generate drafts."""

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
                        :name,
                        'DejaVu Sans',
                        64,
                        '#112233',
                        'left'::skeleton_element_alignment
                    )
                    """
                ),
                {"skeleton_id": SKELETON_ID, "name": TEXT_ELEMENT_NAME},
            )

    def _insert_album(self) -> None:
        """Insert an album so the copied carousel keeps its pointer."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO albums (id, name, slug)
                    VALUES (CAST(:album_id AS uuid), 'Harbor', 'harbor-album')
                    """
                ),
                {"album_id": ALBUM_ID},
            )

    def _insert_carousel(
        self,
        carousel_id: str,
        slug: str,
        inspiration: str,
        rules: str,
        album_id: str | None,
        editor_step: int,
        generation_number: int,
    ) -> None:
        """Insert one carousel on the instruction skeleton."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        id, skeleton_id, name, slug, inspiration, rules,
                        album_id, editor_step, generation_number
                    )
                    VALUES (
                        CAST(:carousel_id AS uuid),
                        CAST(:skeleton_id AS uuid),
                        :name,
                        :slug,
                        :inspiration,
                        :rules,
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
                    "inspiration": inspiration,
                    "rules": rules,
                    "album_id": album_id,
                    "editor_step": editor_step,
                    "generation_number": generation_number,
                },
            )

    def _insert_slide(self) -> None:
        """Insert the slide Generate text drafts. The live text stays empty."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO slides (id, carousel_id, position, name, text_status)
                    VALUES (
                        CAST(:slide_id AS uuid),
                        CAST(:carousel_id AS uuid),
                        0,
                        :name,
                        'live'
                    )
                    """
                ),
                {
                    "slide_id": SLIDE_ID,
                    "carousel_id": BOTH_CAROUSEL_ID,
                    "name": SLIDE_NAME,
                },
            )

    def _insert_research(self) -> None:
        """Insert one research document. The copy revision does not read it."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_items (id, title, slug, body)
                    VALUES (
                        CAST(:research_id AS uuid),
                        'Harbor notes',
                        'harbor-notes',
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
                    "carousel_id": BOTH_CAROUSEL_ID,
                    "research_id": RESEARCH_ID,
                },
            )

    def _insert_instruction(self, carousel_id: str, position: int, body: str) -> None:
        """Insert one document. The caller expects success or a constraint error."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_instructions (carousel_id, position, body)
                    VALUES (CAST(:carousel_id AS uuid), :position, :body)
                    """
                ),
                {
                    "carousel_id": carousel_id,
                    "position": position,
                    "body": body,
                },
            )

    def _delete_instructions(self, carousel_id: str) -> None:
        """Remove documents inserted by a constraint check."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DELETE FROM carousel_instructions
                    WHERE carousel_id = CAST(:carousel_id AS uuid)
                    """
                ),
                {"carousel_id": carousel_id},
            )

    def _set_editor_step(self, carousel_id: str, editor_step: int) -> None:
        """Store one editor step. A refused value rolls the transaction back."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE carousels
                    SET editor_step = :editor_step
                    WHERE id = CAST(:carousel_id AS uuid)
                    """
                ),
                {"carousel_id": carousel_id, "editor_step": editor_step},
            )

    def _carousel_rows(self) -> dict[str, CarouselSnapshot]:
        """Return inspiration, rules, album, step, and generation by slug."""

        with self.database_engine.connect() as connection:
            rows: dict[str, CarouselSnapshot] = {
                str(row[0]): (
                    str(row[1]),
                    str(row[2]),
                    None if row[3] is None else str(row[3]),
                    int(row[4]),
                    int(row[5]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            slug,
                            inspiration,
                            rules,
                            album_id::text,
                            editor_step,
                            generation_number
                        FROM carousels
                        """
                    ),
                ).fetchall()
            }

        return rows

    def _carousel_ids(self) -> set[str]:
        """Return carousel ids still stored."""

        with self.database_engine.connect() as connection:
            carousel_ids: set[str] = {
                str(row[0])
                for row in connection.execute(text("SELECT id::text FROM carousels")).fetchall()
            }

        return carousel_ids

    def _slide_rows(self) -> list[SlideSnapshot]:
        """Return slide identity, position, name, and image pointer."""

        with self.database_engine.connect() as connection:
            slides: list[SlideSnapshot] = [
                (
                    str(row[0]),
                    str(row[1]),
                    int(row[2]),
                    str(row[3]),
                    None if row[4] is None else str(row[4]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT
                            id::text,
                            carousel_id::text,
                            position,
                            name,
                            album_image_id::text
                        FROM slides
                        ORDER BY carousel_id, position, id
                        """
                    ),
                ).fetchall()
            ]

        return slides

    def _research_rows(self) -> list[ResearchSnapshot]:
        """Return research links in carousel and position order."""

        with self.database_engine.connect() as connection:
            links: list[ResearchSnapshot] = [
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

    def _instruction_rows(self) -> dict[str, list[InstructionSnapshot]]:
        """Return documents in position order, keyed by carousel slug."""

        documents: dict[str, list[InstructionSnapshot]] = {}

        with self.database_engine.connect() as connection:
            fetched: list[tuple[object, ...]] = list(
                connection.execute(
                    text(
                        """
                        SELECT carousel.slug, instruction.position, instruction.body
                        FROM carousel_instructions AS instruction
                        JOIN carousels AS carousel ON carousel.id = instruction.carousel_id
                        ORDER BY carousel.slug, instruction.position
                        """
                    ),
                ).fetchall(),
            )

        for slug, position, body in fetched:
            slug_text: str = str(slug)
            current: list[InstructionSnapshot] = documents.get(slug_text, [])
            current.append((int(position), str(body)))
            documents[slug_text] = current

        return documents

    def _carousel_identity_rows(self) -> dict[str, tuple[str | None, int, int]]:
        """Return album, editor step, and generation by slug."""

        with self.database_engine.connect() as connection:
            rows: dict[str, tuple[str | None, int, int]] = {
                str(row[0]): (
                    None if row[1] is None else str(row[1]),
                    int(row[2]),
                    int(row[3]),
                )
                for row in connection.execute(
                    text(
                        """
                        SELECT slug, album_id::text, editor_step, generation_number
                        FROM carousels
                        """
                    ),
                ).fetchall()
            }

        return rows

    def _guidance_column_values(self) -> dict[str, tuple[str, str]]:
        """Return inspiration and rules by slug. The columns must exist."""

        with self.database_engine.connect() as connection:
            values: dict[str, tuple[str, str]] = {
                str(row[0]): (str(row[1]), str(row[2]))
                for row in connection.execute(
                    text("SELECT slug, inspiration, rules FROM carousels"),
                ).fetchall()
            }

        return values

    def _carousel_column_default(self, column_name: str) -> tuple[str, str]:
        """Return nullability and the server default for one carousel column."""

        with self.database_engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'carousels'
                      AND column_name = :column_name
                    """
                ),
                {"column_name": column_name},
            ).one()

        is_nullable: str = str(row[0])
        column_default: str = "" if row[1] is None else str(row[1])

        return is_nullable, column_default

    def _carousel_column_names(self) -> set[str]:
        """Return column names on ``carousels``."""

        with self.database_engine.connect() as connection:
            names: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'carousels'
                        """
                    ),
                ).fetchall()
            }

        return names

    def _instruction_column_names(self) -> list[str]:
        """Return ``carousel_instructions`` columns in table order."""

        with self.database_engine.connect() as connection:
            names: list[str] = [
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'carousel_instructions'
                        ORDER BY ordinal_position
                        """
                    ),
                ).fetchall()
            ]

        return names

    def _column_default(self, column_name: str) -> str:
        """Return the server default expression for one document column."""

        with self.database_engine.connect() as connection:
            column_default: str = str(
                connection.execute(
                    text(
                        """
                        SELECT column_default
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'carousel_instructions'
                          AND column_name = :column_name
                        """
                    ),
                    {"column_name": column_name},
                ).scalar_one(),
            )

        return column_default

    def _editor_step_check(self) -> str:
        """Return the ``editor_step`` check definition. This revision leaves it."""

        with self.database_engine.connect() as connection:
            definition: str = str(
                connection.execute(
                    text(
                        """
                        SELECT pg_get_constraintdef(pg_constraint.oid)
                        FROM pg_constraint
                        JOIN pg_class ON pg_class.oid = pg_constraint.conrelid
                        WHERE pg_class.relname = 'carousels'
                          AND pg_constraint.conname = 'ck_carousels_editor_step'
                        """
                    ),
                ).scalar_one(),
            )

        return definition

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

    def _delete_actions(self) -> dict[str, str]:
        """Return Postgres ON DELETE actions for the document table."""

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
                        WHERE pg_class.relname = 'carousel_instructions'
                          AND pg_constraint.contype = 'f'
                        """
                    ),
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
