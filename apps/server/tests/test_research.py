"""Research create, edit, and delete. There is no file upload.

Carousels attach research through ``carousel_research_items``. The
carousel has no ``research_id`` column.
"""

import importlib
import os
import unittest
import uuid
from datetime import datetime, timezone

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.api.v1.research import (
    BODY_NOT_TEXT_DETAIL,
    BODY_TOO_LONG_DETAIL,
    TITLE_REQUIRED_DETAIL,
    create_research,
    delete_research,
    get_research,
    list_research,
    patch_research,
)
from app.api.v1.schemas import (
    ResearchCreateRequest,
    ResearchListItemResponse,
    ResearchPatchRequest,
    ResearchReadResponse,
)
from app.models.carousel import Carousel, CarouselResearchItem
from app.models.research_item import (
    RESEARCH_BODY_MAX_CHARACTERS,
    ResearchItem,
)


class _ScalarResult:
    """Stand-in for ``session.scalars(...).all()``."""

    def __init__(self, rows: list[object]) -> None:
        self._rows: list[object] = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _MemoryResearchSession:
    """Enough of a session to create a document and read it back."""

    def __init__(self) -> None:
        self.items: list[ResearchItem] = []
        self.commit_count: int = 0

    def add(self, row: object) -> None:
        if isinstance(row, ResearchItem) and row not in self.items:
            self.items.append(row)

    def delete(self, row: object) -> None:
        if isinstance(row, ResearchItem):
            self.items = [
                research_item
                for research_item in self.items
                if research_item.id != row.id
            ]

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        return

    def refresh(self, row: object) -> None:
        persisted_at: datetime = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

        if getattr(row, "created_at", None) is None:
            setattr(row, "created_at", persisted_at)

        if hasattr(row, "updated_at"):
            setattr(row, "updated_at", persisted_at)

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        if model is ResearchItem:
            for research_item in self.items:
                if research_item.id == row_id:
                    return research_item

        return None

    def scalars(self, statement: object) -> _ScalarResult:
        sql: str = str(statement)

        if "carousel_research_items" in sql:

            return _ScalarResult([])

        if "research_items.slug" in sql and "research_items.title" not in sql:
            return _ScalarResult([research_item.slug for research_item in self.items])

        if "research_items" in sql:
            return _ScalarResult(list(self.items))

        return _ScalarResult([])


class ResearchWriteTests(unittest.TestCase):
    """Title, body, slug, and the rule that this is not a file upload."""

    def test_create_lists_and_renames_without_changing_the_slug(self) -> None:
        """A second document with the same title gets a suffixed slug."""

        session: _MemoryResearchSession = _MemoryResearchSession()
        first: ResearchReadResponse = create_research(
            ResearchCreateRequest(title="Harbor"),
            session,
            None,
        )
        second: ResearchReadResponse = create_research(
            ResearchCreateRequest(title="Harbor"),
            session,
            None,
        )
        renamed: ResearchReadResponse = patch_research(
            first.id,
            ResearchPatchRequest(title="Outer harbor", body="One lamp.\nTwo notes."),
            session,
            None,
        )
        listed: list[ResearchListItemResponse] = list_research(session)

        self.assertEqual(first.slug, "harbor")
        self.assertEqual(first.body, "")
        self.assertEqual(first.word_count, 0)
        self.assertEqual(first.character_count, 0)
        self.assertEqual(second.slug, "harbor-2")
        self.assertEqual(renamed.title, "Outer harbor")
        self.assertEqual(renamed.slug, "harbor")
        self.assertEqual(renamed.body, "One lamp.\nTwo notes.")
        self.assertEqual(renamed.word_count, 4)
        self.assertEqual(renamed.character_count, len("One lamp.\nTwo notes."))
        self.assertEqual(len(listed), 2)
        self.assertEqual({item.word_count for item in listed}, {0, 4})

    def test_blank_title_is_rejected(self) -> None:
        """A blank title does not create a row."""

        session: _MemoryResearchSession = _MemoryResearchSession()

        with self.assertRaises(HTTPException) as raised:
            create_research(ResearchCreateRequest(title="  "), session, None)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, TITLE_REQUIRED_DETAIL)
        self.assertEqual(session.items, [])

    def test_accented_title_and_empty_slug_fallback(self) -> None:
        """Accents fold into the slug. A title with no letters uses research."""

        session: _MemoryResearchSession = _MemoryResearchSession()
        accented: ResearchReadResponse = create_research(
            ResearchCreateRequest(title="Café Notes"),
            session,
            None,
        )
        fallback: ResearchReadResponse = create_research(
            ResearchCreateRequest(title="!!!"),
            session,
            None,
        )

        self.assertEqual(accented.slug, "cafe-notes")
        self.assertEqual(fallback.slug, "research")

    def test_empty_body_is_allowed_and_a_null_byte_is_rejected(self) -> None:
        """The editor can open on an empty body. A null byte is not text."""

        session: _MemoryResearchSession = _MemoryResearchSession()
        created: ResearchReadResponse = create_research(
            ResearchCreateRequest(title="Notes"),
            session,
            None,
        )
        cleared: ResearchReadResponse = patch_research(
            created.id,
            ResearchPatchRequest(title="Notes", body="  a  "),
            session,
            None,
        )

        self.assertEqual(cleared.word_count, 1)
        self.assertEqual(cleared.character_count, 5)

        with self.assertRaises(HTTPException) as raised:
            patch_research(
                created.id,
                ResearchPatchRequest(title="Notes", body="hello\x00"),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, BODY_NOT_TEXT_DETAIL)
        stored: ResearchItem | None = session.get(ResearchItem, created.id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.body, "  a  ")

    def test_body_at_the_limit_is_kept_and_one_past_it_is_rejected(self) -> None:
        """The size limit is one million characters."""

        session: _MemoryResearchSession = _MemoryResearchSession()
        created: ResearchReadResponse = create_research(
            ResearchCreateRequest(title="Long"),
            session,
            None,
        )
        at_limit: str = "a" * RESEARCH_BODY_MAX_CHARACTERS
        saved: ResearchReadResponse = patch_research(
            created.id,
            ResearchPatchRequest(title="Long", body=at_limit),
            session,
            None,
        )

        self.assertEqual(saved.character_count, RESEARCH_BODY_MAX_CHARACTERS)
        self.assertEqual(saved.word_count, 1)

        with self.assertRaises(HTTPException) as raised:
            patch_research(
                created.id,
                ResearchPatchRequest(title="Long", body=at_limit + "b"),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, BODY_TOO_LONG_DETAIL)

    def test_missing_document_is_404_and_delete_removes_it(self) -> None:
        """Delete removes the row. A missing id is 404."""

        session: _MemoryResearchSession = _MemoryResearchSession()
        created: ResearchReadResponse = create_research(
            ResearchCreateRequest(title="Gone"),
            session,
            None,
        )
        missing_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as missing:
            get_research(missing_id, session)

        self.assertEqual(missing.exception.status_code, 404)
        delete_research(created.id, session, None)
        self.assertEqual(session.items, [])

        with self.assertRaises(HTTPException) as deleted:
            get_research(created.id, session)

        self.assertEqual(deleted.exception.status_code, 404)

    def test_carousel_has_no_research_link_and_upload_helpers_are_gone(self) -> None:
        """There is no ``research_id`` column. Research uses the join table."""

        self.assertNotIn("research_id", set(Carousel.__table__.columns.keys()))
        self.assertEqual(CarouselResearchItem.__tablename__, "carousel_research_items")
        self.assertNotIn("research_id", set(CarouselResearchItem.__table__.columns.keys()))
        unique_pairs: list[tuple[str, ...]] = [
            tuple(column.name for column in constraint.columns)
            for constraint in CarouselResearchItem.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        ]

        self.assertIn(("carousel_id", "research_item_id"), unique_pairs)
        self.assertIn(("carousel_id", "position"), unique_pairs)
        check_names: set[str | None] = {
            constraint.name
            for constraint in ResearchItem.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }

        self.assertIn("ck_research_items_title", check_names)
        self.assertIn("ck_research_items_body", check_names)
        self.assertNotIn("ck_research_items_ck_research_items_title", check_names)

        for module_name in (
            "app.carousels.resource_files",
            "app.carousels.resource_store",
            "app.carousels.resource_markdown",
        ):
            with self.assertRaises(ModuleNotFoundError):
                importlib.import_module(module_name)


if __name__ == "__main__":
    unittest.main()
