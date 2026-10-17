"""Adding a skeleton text element fills empty slots on bound slides.

Removing the element drops those rows through ON DELETE CASCADE.
Draft copy lives on ``slide_element_texts.draft_value``, not a second table.
"""

import os
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")

from sqlalchemy import Select, create_engine, select, text
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.schemas import (
    CarouselCreateRequest,
    CarouselReadResponse,
    SkeletonCreateRequest,
    SkeletonElementCreateRequest,
    SkeletonElementPatchRequest,
    SkeletonElementReadResponse,
    SkeletonReadResponse,
    SlideElementTextWrite,
    SlideReadResponse,
    SlideWriteRequest,
)
from app.api.v1.carousel_writes import (
    create_carousel,
    create_slide,
    delete_carousel,
)
from app.api.v1.skeleton_elements import (
    create_skeleton_element,
    delete_skeleton_element,
    patch_skeleton_element,
)
from app.api.v1.skeletons import create_skeleton, delete_skeleton_by_id
from app.models.carousel import Slide, SlideElementText
from app.models.enums import (
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
    SlideTextStatus,
)
from app.models.skeleton_element import SkeletonElement
from app.carousels.slide_text_sync import sync_empty_texts_for_skeleton_element


CANDIDATE_DATABASE_URLS: tuple[str, ...] = (
    os.environ.get("TWERVA_TEST_DATABASE_URL", "").strip(),
    os.environ.get("DATABASE_URL", "").strip(),
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva_test",
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
)
SKELETON_ELEMENT_TEXT_FK: str = (
    "fk_slide_element_texts_skeleton_element_id_skeleton_elements"
)


def _connect_test_engine() -> Engine | None:
    """Return an engine for the first reachable candidate URL, if any."""

    for candidate_database_url in CANDIDATE_DATABASE_URLS:

        if candidate_database_url == "":
            continue

        normalized_database_url: str = candidate_database_url

        if normalized_database_url.startswith("postgresql://"):
            remainder: str = normalized_database_url[len("postgresql://"):]
            normalized_database_url = f"postgresql+psycopg://{remainder}"

        candidate_engine: Engine | None = None

        try:
            candidate_engine = create_engine(normalized_database_url)
            with candidate_engine.connect() as our_database_connection:
                our_database_connection.execute(text("SELECT 1"))
        except OperationalError:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        except Exception:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        else:

            return candidate_engine

    return None


TEST_ENGINE: Engine | None = _connect_test_engine()


def _text_element_request(
    text_source: SkeletonElementTextSource,
) -> SkeletonElementCreateRequest:
    """One clear text element on the top band."""

    text_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
        name=text_source.value,
        band=SkeletonElementBand.TOP,
        content_kind=SkeletonElementContentKind.TEXT,
        text_source=text_source,
        font_family="DejaVu Sans",
        font_size=28,
        font_color="#112233",
        alignment=SkeletonElementAlignment.LEFT,
    )

    return text_request


@unittest.skipIf(TEST_ENGINE is None, "Postgres is not reachable for slide text sync tests")
class SkeletonElementSlideTextSyncTests(unittest.TestCase):
    """Add fills empty slots. Delete cascades. Live slides stay live."""

    def setUp(self) -> None:
        """Two skeletons with slides, one of them already a draft."""

        if TEST_ENGINE is None:
            self.skipTest("Postgres is not reachable for slide text sync tests")

        self.SessionFactory: sessionmaker[Session] = sessionmaker(
            bind=TEST_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.our_database_session: Session = self.SessionFactory()
        self.run_suffix: str = uuid.uuid4().hex[:8]
        self.skeleton_ids: list[uuid.UUID] = []
        self.carousel_ids: list[uuid.UUID] = []
        paper: SkeletonReadResponse = create_skeleton(
            SkeletonCreateRequest(
                name=f"Paper {self.run_suffix}",
                elements=[_text_element_request(SkeletonElementTextSource.TITLE)],
            ),
            self.our_database_session,
            None,
        )
        other: SkeletonReadResponse = create_skeleton(
            SkeletonCreateRequest(
                name=f"Other {self.run_suffix}",
                elements=[_text_element_request(SkeletonElementTextSource.TITLE)],
            ),
            self.our_database_session,
            None,
        )
        blank: SkeletonReadResponse = create_skeleton(
            SkeletonCreateRequest(name=f"Blank {self.run_suffix}"),
            self.our_database_session,
            None,
        )
        self.paper_skeleton_id: uuid.UUID = paper.id
        self.other_skeleton_id: uuid.UUID = other.id
        self.blank_skeleton_id: uuid.UUID = blank.id
        self.paper_title_id: uuid.UUID = paper.elements[0].id
        self.other_title_id: uuid.UUID = other.elements[0].id
        self.skeleton_ids.extend([paper.id, other.id, blank.id])
        harbor_source: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name=f"Harbor {self.run_suffix}", skeleton_id=paper.id),
            self.our_database_session,
            None,
        )
        desert_source: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name=f"Desert {self.run_suffix}", skeleton_id=paper.id),
            self.our_database_session,
            None,
        )
        other_source: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name=f"Elsewhere {self.run_suffix}", skeleton_id=other.id),
            self.our_database_session,
            None,
        )
        blank_source: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name=f"Empty {self.run_suffix}", skeleton_id=blank.id),
            self.our_database_session,
            None,
        )
        self.carousel_ids.extend(
            [harbor_source.id, desert_source.id, other_source.id, blank_source.id],
        )
        harbor_slide: SlideReadResponse = create_slide(
            harbor_source.id,
            SlideWriteRequest(
                name="Harbor lamp",
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=self.paper_title_id,
                        value="Fog",
                    ),
                ],
            ),
            self.our_database_session,
            None,
        )
        desert_slide: SlideReadResponse = create_slide(
            desert_source.id,
            SlideWriteRequest(
                name="Desert lamp",
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=self.paper_title_id,
                        value="Dune",
                    ),
                ],
            ),
            self.our_database_session,
            None,
        )
        other_slide: SlideReadResponse = create_slide(
            other_source.id,
            SlideWriteRequest(
                name="Other lamp",
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=self.other_title_id,
                        value="Stay",
                    ),
                ],
            ),
            self.our_database_session,
            None,
        )
        blank_slide: SlideReadResponse = create_slide(
            blank_source.id,
            SlideWriteRequest(name="Blank lamp"),
            self.our_database_session,
            None,
        )
        self.harbor_slide_id: uuid.UUID = harbor_slide.id
        self.desert_slide_id: uuid.UUID = desert_slide.id
        self.other_slide_id: uuid.UUID = other_slide.id
        self.blank_slide_id: uuid.UUID = blank_slide.id
        self._mark_desert_as_draft()

    def tearDown(self) -> None:
        """Remove the carousels, then the skeletons."""

        if getattr(self, "our_database_session", None) is None:

            return

        try:
            self._delete_fixtures()
        finally:
            self.our_database_session.close()

    def test_adding_a_text_element_writes_empty_slots(self) -> None:
        """Every slide on the skeleton gets an empty row. Live slides stay live."""

        heading: SkeletonElementReadResponse = create_skeleton_element(
            self.paper_skeleton_id,
            _text_element_request(SkeletonElementTextSource.INTEREST_HEADING),
            self.our_database_session,
            None,
        )
        heading_rows: dict[uuid.UUID, SlideElementText] = self._rows_for_element(
            heading.id,
        )
        harbor_heading: SlideElementText = heading_rows[self.harbor_slide_id]
        desert_heading: SlideElementText = heading_rows[self.desert_slide_id]

        self.assertEqual(set(heading_rows), {self.harbor_slide_id, self.desert_slide_id})
        self.assertEqual(harbor_heading.value, "")
        self.assertIsNone(harbor_heading.draft_value)
        self.assertEqual(desert_heading.value, "")
        self.assertEqual(desert_heading.draft_value, "")
        self.assertEqual(self._status(self.harbor_slide_id), SlideTextStatus.LIVE)
        self.assertEqual(self._status(self.desert_slide_id), SlideTextStatus.DRAFT)
        self.assertEqual(self._value(self.harbor_slide_id, self.paper_title_id), "Fog")
        self.assertIsNone(self._draft(self.harbor_slide_id, self.paper_title_id))
        self.assertEqual(self._value(self.desert_slide_id, self.paper_title_id), "Dune")
        self.assertEqual(self._draft(self.desert_slide_id, self.paper_title_id), "Dry wind")
        self.assertNotIn(self.other_slide_id, heading_rows)
        self.assertEqual(self._value(self.other_slide_id, self.other_title_id), "Stay")
        self.assertEqual(self._rows_for_slide(self.blank_slide_id), {})
        self.assertEqual(self._image_count(self.harbor_slide_id), 0)

        stored_heading: SkeletonElement | None = self.our_database_session.get(
            SkeletonElement,
            heading.id,
        )
        self.assertIsNotNone(stored_heading)
        assert stored_heading is not None
        sync_empty_texts_for_skeleton_element(
            stored_heading,
            self.our_database_session,
        )
        self.our_database_session.commit()
        second_pass: dict[uuid.UUID, SlideElementText] = self._rows_for_element(
            heading.id,
        )

        self.assertEqual(set(second_pass), {self.harbor_slide_id, self.desert_slide_id})
        self.assertEqual(second_pass[self.harbor_slide_id].id, harbor_heading.id)

        blank_heading: SkeletonElementReadResponse = create_skeleton_element(
            self.blank_skeleton_id,
            _text_element_request(SkeletonElementTextSource.CANONICAL_URL),
            self.our_database_session,
            None,
        )
        blank_rows: dict[uuid.UUID, SlideElementText] = self._rows_for_element(
            blank_heading.id,
        )

        self.assertEqual(set(blank_rows), {self.blank_slide_id})
        self.assertEqual(blank_rows[self.blank_slide_id].value, "")
        self.assertIsNone(blank_rows[self.blank_slide_id].draft_value)
        self.assertEqual(self._status(self.blank_slide_id), SlideTextStatus.LIVE)

    def test_deleting_a_text_element_drops_its_rows(self) -> None:
        """CASCADE removes live and draft slots. The other element stays."""

        delete_action: str = self._skeleton_element_delete_action()
        heading: SkeletonElementReadResponse = create_skeleton_element(
            self.paper_skeleton_id,
            _text_element_request(SkeletonElementTextSource.OVERVIEW_BULLETS),
            self.our_database_session,
            None,
        )

        self.assertEqual(delete_action, "c")
        self.assertEqual(
            set(self._rows_for_element(heading.id)),
            {self.harbor_slide_id, self.desert_slide_id},
        )

        delete_skeleton_element(
            self.paper_skeleton_id,
            heading.id,
            self.our_database_session,
            None,
        )

        self.assertEqual(self._rows_for_element(heading.id), {})
        self.assertEqual(self._value(self.harbor_slide_id, self.paper_title_id), "Fog")
        self.assertEqual(self._value(self.desert_slide_id, self.paper_title_id), "Dune")
        self.assertEqual(self._draft(self.desert_slide_id, self.paper_title_id), "Dry wind")
        self.assertEqual(self._value(self.other_slide_id, self.other_title_id), "Stay")
        self.assertEqual(self._status(self.harbor_slide_id), SlideTextStatus.LIVE)
        self.assertEqual(self._status(self.desert_slide_id), SlideTextStatus.DRAFT)
        self.assertEqual(self._image_count(self.harbor_slide_id), 0)
        self.assertEqual(self._image_count(self.desert_slide_id), 0)

    def test_an_image_element_does_not_write_text(self) -> None:
        """A new image element leaves slide text and slide images unchanged."""

        before: dict[uuid.UUID, str] = {
            self.harbor_slide_id: self._value(self.harbor_slide_id, self.paper_title_id),
            self.desert_slide_id: self._value(self.desert_slide_id, self.paper_title_id),
        }
        image_element: SkeletonElementReadResponse = create_skeleton_element(
            self.paper_skeleton_id,
            SkeletonElementCreateRequest(
                name="Image",
                band=SkeletonElementBand.MIDDLE,
                content_kind=SkeletonElementContentKind.IMAGE,
                image_asset_ref="logos/mark.png",
            ),
            self.our_database_session,
            None,
        )

        self.assertEqual(self._rows_for_element(image_element.id), {})
        self.assertEqual(
            self._value(self.harbor_slide_id, self.paper_title_id),
            before[self.harbor_slide_id],
        )
        self.assertEqual(
            self._value(self.desert_slide_id, self.paper_title_id),
            before[self.desert_slide_id],
        )
        self.assertEqual(self._image_count(self.harbor_slide_id), 0)
        self.assertEqual(self._image_count(self.desert_slide_id), 0)

    def test_turning_an_image_element_into_text_writes_empty_slots(self) -> None:
        """A kind change that creates a text element fills the same empty slots."""

        image_element: SkeletonElementReadResponse = create_skeleton_element(
            self.paper_skeleton_id,
            SkeletonElementCreateRequest(
                name="Image",
                band=SkeletonElementBand.BOTTOM,
                content_kind=SkeletonElementContentKind.IMAGE,
                image_asset_ref="logos/mark.png",
            ),
            self.our_database_session,
            None,
        )
        text_element: SkeletonElementReadResponse = patch_skeleton_element(
            self.paper_skeleton_id,
            image_element.id,
            SkeletonElementPatchRequest(
                content_kind=SkeletonElementContentKind.TEXT,
                text_source=SkeletonElementTextSource.CANONICAL_URL,
                font_family="DejaVu Sans",
                font_size=20,
                font_color="#112233",
                alignment=SkeletonElementAlignment.LEFT,
                image_asset_ref=None,
            ),
            self.our_database_session,
            None,
        )
        text_rows: dict[uuid.UUID, SlideElementText] = self._rows_for_element(
            text_element.id,
        )

        self.assertEqual(text_element.content_kind, SkeletonElementContentKind.TEXT)
        self.assertEqual(set(text_rows), {self.harbor_slide_id, self.desert_slide_id})
        self.assertEqual(text_rows[self.harbor_slide_id].value, "")
        self.assertIsNone(text_rows[self.harbor_slide_id].draft_value)
        self.assertEqual(text_rows[self.desert_slide_id].value, "")
        self.assertEqual(text_rows[self.desert_slide_id].draft_value, "")
        self.assertEqual(self._status(self.harbor_slide_id), SlideTextStatus.LIVE)
        self.assertEqual(self._status(self.desert_slide_id), SlideTextStatus.DRAFT)
        self.assertEqual(self._image_count(self.harbor_slide_id), 0)

    def _mark_desert_as_draft(self) -> None:
        """Store a draft beside the desert slide's live title."""

        desert_slide: Slide | None = self.our_database_session.get(Slide, self.desert_slide_id)
        self.assertIsNotNone(desert_slide)
        assert desert_slide is not None
        desert_slide.text_status = SlideTextStatus.DRAFT

        for element_text in list(desert_slide.element_texts):
            element_text.draft_value = "Dry wind"

        self.our_database_session.commit()

    def _delete_fixtures(self) -> None:
        """Drop carousels before skeletons. Skeletons are still referenced until then."""

        self.our_database_session.rollback()

        for carousel_id in list(self.carousel_ids):
            delete_carousel(carousel_id, self.our_database_session, None)

        for skeleton_id in list(self.skeleton_ids):
            delete_skeleton_by_id(skeleton_id, self.our_database_session, None)

    def _rows_for_element(
        self,
        skeleton_element_id: uuid.UUID,
    ) -> dict[uuid.UUID, SlideElementText]:
        """Reload text rows for one skeleton element, keyed by slide."""

        self.our_database_session.expire_all()
        statement: Select[tuple[SlideElementText]] = select(SlideElementText).where(
            SlideElementText.skeleton_element_id == skeleton_element_id,
        )
        stored_rows: list[SlideElementText] = list(
            self.our_database_session.scalars(statement).all(),
        )
        rows_by_slide: dict[uuid.UUID, SlideElementText] = {
            stored_row.slide_id: stored_row for stored_row in stored_rows
        }

        return rows_by_slide

    def _rows_for_slide(self, slide_id: uuid.UUID) -> dict[uuid.UUID, SlideElementText]:
        """Reload one slide's text rows, keyed by skeleton element."""

        self.our_database_session.expire_all()
        statement: Select[tuple[SlideElementText]] = select(SlideElementText).where(
            SlideElementText.slide_id == slide_id,
        )
        stored_rows: list[SlideElementText] = list(
            self.our_database_session.scalars(statement).all(),
        )
        rows_by_element: dict[uuid.UUID, SlideElementText] = {
            stored_row.skeleton_element_id: stored_row for stored_row in stored_rows
        }

        return rows_by_element

    def _stored_text(
        self,
        slide_id: uuid.UUID,
        skeleton_element_id: uuid.UUID,
    ) -> SlideElementText:
        """Return the one row for this slide and element."""

        stored_text: SlideElementText | None = self._rows_for_slide(slide_id).get(
            skeleton_element_id,
        )
        self.assertIsNotNone(stored_text)
        assert stored_text is not None

        return stored_text

    def _value(self, slide_id: uuid.UUID, skeleton_element_id: uuid.UUID) -> str:
        """Return the live string for one slot."""

        stored_value: str = self._stored_text(slide_id, skeleton_element_id).value

        return stored_value

    def _draft(self, slide_id: uuid.UUID, skeleton_element_id: uuid.UUID) -> str | None:
        """Return the draft string for one slot, or null when there is none."""

        draft_value: str | None = self._stored_text(slide_id, skeleton_element_id).draft_value

        return draft_value

    def _status(self, slide_id: uuid.UUID) -> SlideTextStatus:
        """Reload the slide and return its text status."""

        self.our_database_session.expire_all()
        found_slide: Slide | None = self.our_database_session.get(Slide, slide_id)
        self.assertIsNotNone(found_slide)
        assert found_slide is not None
        text_status: SlideTextStatus = found_slide.text_status

        return text_status

    def _image_count(self, slide_id: uuid.UUID) -> int:
        """Return how many images this slide stores."""

        self.our_database_session.expire_all()
        found_slide: Slide | None = self.our_database_session.get(Slide, slide_id)
        self.assertIsNotNone(found_slide)
        assert found_slide is not None
        image_count: int = 0 if found_slide.album_image_id is None else 1

        return image_count

    def _skeleton_element_delete_action(self) -> str:
        """Return Postgres' ON DELETE action for the skeleton-element text key."""

        action_statement: TextClause = text(
            "SELECT confdeltype FROM pg_constraint WHERE conname = :constraint_name",
        )
        delete_action: str | None = self.our_database_session.execute(
            action_statement,
            {"constraint_name": SKELETON_ELEMENT_TEXT_FK},
        ).scalar_one()

        return str(delete_action)
