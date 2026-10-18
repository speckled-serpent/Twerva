"""Attach, reorder, and remove research on a carousel."""

import os
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.carousel_writes import (
    ALREADY_ATTACHED_RESEARCH_DETAIL,
    DUPLICATE_RESEARCH_DETAIL,
    RESEARCH_NOT_ATTACHED_DETAIL,
    delete_carousel_research,
    post_carousel_research,
    put_carousel_research,
)
from app.api.v1.carousels import get_carousel
from app.api.v1.research import create_research, delete_research, get_research
from app.api.v1.schemas import (
    CarouselReadResponse,
    CarouselResearchAttachRequest,
    CarouselResearchOrderRequest,
    ResearchCreateRequest,
    ResearchReadResponse,
)
from app.carousels.slide_skeleton import SLIDES_LOCKED_DETAIL, CarouselStepState
from app.models.carousel import Carousel
from app.models.enums import BackgroundKind
from app.models.research_item import ResearchItem
from tests.test_carousel_editor_step import _create, _store_step
from tests.test_carousel_writes import _MemoryCarouselSession


class CarouselResearchLinkTests(unittest.TestCase):
    """Research is an ordered list. It does not gate a step."""

    def test_two_research_items_round_trip_in_stored_order(self) -> None:
        """Append stores the next position. The detail returns that order."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Reading")
        first: ResearchReadResponse = _document(session, "First note")
        second: ResearchReadResponse = _document(session, "Later note")

        attached: CarouselReadResponse = _append(session, created.id, first.id)
        both: CarouselReadResponse = _append(session, created.id, second.id)
        loaded: CarouselReadResponse = get_carousel(created.id, session)
        stored: Carousel | None = session.get(Carousel, created.id)

        self.assertEqual([item.id for item in attached.research], [first.id])
        self.assertEqual(attached.research[0].position, 0)
        self.assertEqual(attached.research[0].title, first.title)
        self.assertEqual(attached.research[0].slug, first.slug)
        self.assertEqual(
            [item.id for item in both.research],
            [first.id, second.id],
        )
        self.assertEqual([item.position for item in both.research], [0, 1])
        self.assertEqual(both.research[1].title, "Later note")
        self.assertEqual(both.research[1].slug, second.slug)
        self.assertEqual(
            [(item.id, item.position) for item in loaded.research],
            [(item.id, item.position) for item in both.research],
        )
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertNotEqual(loaded.research[0].id, stored.research_links[0].id)
        self.assertEqual(stored.research_links[0].research_item_id, first.id)
        self.assertEqual(stored.research_links[1].position, 1)
        self.assertNotIn("research_id", set(Carousel.__table__.columns.keys()))
        self.assertEqual(both.editor_step, created.editor_step)
        self.assertEqual(both.generation_number, created.generation_number)
        self.assertEqual(both.album_id, created.album_id)
        self.assertEqual(both.steps, created.steps)
        self.assertEqual(loaded.steps.content, CarouselStepState.DONE)
        self.assertEqual(loaded.steps.slides, CarouselStepState.AVAILABLE)

    def test_put_replaces_the_order_and_an_empty_list_clears_it(self) -> None:
        """The submitted ids become the list. A missing id is detached."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Reading")
        first: ResearchReadResponse = _document(session, "First note")
        second: ResearchReadResponse = _document(session, "Later note")
        third: ResearchReadResponse = _document(session, "Third note")
        _append(session, created.id, first.id)
        _append(session, created.id, second.id)

        reversed_order: CarouselReadResponse = _reorder(
            session,
            created.id,
            [second.id, first.id],
        )
        replaced: CarouselReadResponse = _reorder(
            session,
            created.id,
            [third.id, second.id],
        )
        kept_first: ResearchItem | None = session.get(ResearchItem, first.id)
        cleared: CarouselReadResponse = _reorder(session, created.id, [])
        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(
            [item.id for item in reversed_order.research],
            [second.id, first.id],
        )
        self.assertEqual([item.position for item in reversed_order.research], [0, 1])
        self.assertEqual(
            [item.id for item in replaced.research],
            [third.id, second.id],
        )
        self.assertEqual([item.position for item in replaced.research], [0, 1])
        self.assertIsNotNone(kept_first)
        self.assertEqual(get_research(first.id, session).title, "First note")
        self.assertEqual(cleared.research, [])
        self.assertEqual(loaded.research, [])
        self.assertEqual(cleared.steps, created.steps)
        self.assertEqual(len(session.research_items), 3)

    def test_duplicate_id_is_400_and_writes_nothing(self) -> None:
        """The same id twice, and appending an attached id, leave the order."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Reading")
        first: ResearchReadResponse = _document(session, "First note")
        second: ResearchReadResponse = _document(session, "Later note")
        _append(session, created.id, first.id)
        _append(session, created.id, second.id)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as duplicate:
            _reorder(session, created.id, [second.id, second.id])

        with self.assertRaises(HTTPException) as attached_again:
            _append(session, created.id, first.id)

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(duplicate.exception.status_code, 400)
        self.assertEqual(duplicate.exception.detail, DUPLICATE_RESEARCH_DETAIL)
        self.assertEqual(attached_again.exception.status_code, 400)
        self.assertEqual(attached_again.exception.detail, ALREADY_ATTACHED_RESEARCH_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(
            [item.id for item in loaded.research],
            [first.id, second.id],
        )
        self.assertEqual([item.position for item in loaded.research], [0, 1])

    def test_unknown_research_is_404_and_writes_nothing(self) -> None:
        """A missing document does not change the stored list."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Reading")
        first: ResearchReadResponse = _document(session, "First note")
        _append(session, created.id, first.id)
        missing_id: uuid.UUID = uuid.uuid4()
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as appended:
            _append(session, created.id, missing_id)

        with self.assertRaises(HTTPException) as reordered:
            _reorder(session, created.id, [first.id, missing_id])

        with self.assertRaises(HTTPException) as removed:
            _remove(session, created.id, missing_id)

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(appended.exception.status_code, 404)
        self.assertIn(str(missing_id), str(appended.exception.detail))
        self.assertEqual(reordered.exception.status_code, 404)
        self.assertIn(str(missing_id), str(reordered.exception.detail))
        self.assertEqual(removed.exception.status_code, 404)
        self.assertIn(str(missing_id), str(removed.exception.detail))
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual([item.id for item in loaded.research], [first.id])

    def test_remove_link_closes_the_gap_and_leaves_the_document(self) -> None:
        """Deleting a link keeps the research row and renumbers the rest."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Reading")
        first: ResearchReadResponse = _document(session, "First note")
        middle: ResearchReadResponse = _document(session, "Middle note")
        last: ResearchReadResponse = _document(session, "Last note")
        _append(session, created.id, first.id)
        _append(session, created.id, middle.id)
        _append(session, created.id, last.id)

        removed: CarouselReadResponse = _remove(session, created.id, middle.id)
        loaded: CarouselReadResponse = get_carousel(created.id, session)
        appended: CarouselReadResponse = _append(session, created.id, middle.id)
        detached_again: CarouselReadResponse = _remove(session, created.id, middle.id)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as missing_link:
            _remove(session, created.id, middle.id)

        still_there: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(
            [item.id for item in removed.research],
            [first.id, last.id],
        )
        self.assertEqual([item.position for item in removed.research], [0, 1])
        self.assertEqual(get_research(middle.id, session).id, middle.id)
        self.assertEqual(
            [(item.id, item.position) for item in loaded.research],
            [(first.id, 0), (last.id, 1)],
        )
        self.assertEqual(
            [item.id for item in appended.research],
            [first.id, last.id, middle.id],
        )
        self.assertEqual([item.position for item in appended.research], [0, 1, 2])
        self.assertEqual(
            [item.id for item in detached_again.research],
            [first.id, last.id],
        )
        self.assertEqual(missing_link.exception.status_code, 404)
        self.assertEqual(missing_link.exception.detail, RESEARCH_NOT_ATTACHED_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(
            [item.id for item in still_there.research],
            [first.id, last.id],
        )

    def test_deleting_a_research_item_drops_its_link_and_leaves_the_carousel(self) -> None:
        """The document delete removes that link. The carousel and the other link stay."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Reading")
        first: ResearchReadResponse = _document(session, "First note")
        second: ResearchReadResponse = _document(session, "Later note")
        _append(session, created.id, first.id)
        _append(session, created.id, second.id)

        delete_research(first.id, session, None)
        loaded: CarouselReadResponse = get_carousel(created.id, session)
        stored: Carousel | None = session.get(Carousel, created.id)

        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.name, "Reading")
        self.assertEqual(loaded.id, created.id)
        self.assertEqual([item.id for item in loaded.research], [second.id])
        self.assertEqual(loaded.research[0].position, 0)
        self.assertEqual(loaded.research[0].title, "Later note")
        self.assertEqual(get_research(second.id, session).slug, second.slug)
        self.assertEqual(loaded.steps, created.steps)

        with self.assertRaises(HTTPException) as deleted:
            get_research(first.id, session)

        self.assertEqual(deleted.exception.status_code, 404)
        self.assertNotIn("research_id", set(Carousel.__table__.columns.keys()))

    def test_two_carousels_can_share_a_document_and_lose_only_that_link(self) -> None:
        """Deleting one shared document drops it from each carousel."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        first_carousel: CarouselReadResponse = _create(session, "Reading")
        second_carousel: CarouselReadResponse = _create(session, "Harbor")
        shared: ResearchReadResponse = _document(session, "Shared note")
        only_first: ResearchReadResponse = _document(session, "First only")
        only_second: ResearchReadResponse = _document(session, "Second only")
        _append(session, first_carousel.id, shared.id)
        _append(session, first_carousel.id, only_first.id)
        _append(session, second_carousel.id, only_second.id)
        _append(session, second_carousel.id, shared.id)

        delete_research(shared.id, session, None)
        loaded_first: CarouselReadResponse = get_carousel(first_carousel.id, session)
        loaded_second: CarouselReadResponse = get_carousel(second_carousel.id, session)

        self.assertEqual([item.id for item in loaded_first.research], [only_first.id])
        self.assertEqual(loaded_first.research[0].position, 0)
        self.assertEqual([item.id for item in loaded_second.research], [only_second.id])
        self.assertEqual(loaded_second.research[0].position, 0)
        self.assertEqual(get_research(only_first.id, session).id, only_first.id)
        self.assertEqual(get_research(only_second.id, session).id, only_second.id)

    def test_research_does_not_change_step_state(self) -> None:
        """A picture carousel with no album stays locked on Slides."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Plates")
        notes: ResearchReadResponse = _document(session, "Plate notes")

        attached: CarouselReadResponse = _append(session, created.id, notes.id)

        with self.assertRaises(HTTPException) as refused:
            _store_step(session, created.id, 3)

        stayed: CarouselReadResponse = get_carousel(created.id, session)
        cleared: CarouselReadResponse = _reorder(session, created.id, [])

        self.assertEqual(created.steps.content, CarouselStepState.AVAILABLE)
        self.assertEqual(created.steps.slides, CarouselStepState.LOCKED)
        self.assertEqual(attached.steps.basic, CarouselStepState.DONE)
        self.assertEqual(attached.steps.instructions, CarouselStepState.LOCKED)
        self.assertEqual(attached.steps.content, CarouselStepState.AVAILABLE)
        self.assertEqual(attached.steps.slides, CarouselStepState.LOCKED)
        self.assertEqual(attached.steps.final, CarouselStepState.LOCKED)
        self.assertEqual(attached.editor_step, created.editor_step)
        self.assertIsNone(attached.album_id)
        self.assertEqual(len(attached.research), 1)
        self.assertEqual(refused.exception.status_code, 400)
        self.assertEqual(refused.exception.detail, SLIDES_LOCKED_DETAIL)
        self.assertEqual(stayed.editor_step, created.editor_step)
        self.assertEqual(stayed.steps.slides, CarouselStepState.LOCKED)
        self.assertEqual(len(stayed.research), 1)
        self.assertEqual(cleared.research, [])
        self.assertEqual(cleared.steps.slides, CarouselStepState.LOCKED)

    def test_missing_carousel_is_not_found(self) -> None:
        """An unknown carousel is 404 and does not write a link."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        notes: ResearchReadResponse = _document(session, "First note")
        missing_id: uuid.UUID = uuid.uuid4()
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as appended:
            _append(session, missing_id, notes.id)

        with self.assertRaises(HTTPException) as reordered:
            _reorder(session, missing_id, [notes.id])

        with self.assertRaises(HTTPException) as removed:
            _remove(session, missing_id, notes.id)

        self.assertEqual(appended.exception.status_code, 404)
        self.assertEqual(reordered.exception.status_code, 404)
        self.assertEqual(removed.exception.status_code, 404)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(session.carousels, [])

    def test_bodies_reject_extra_fields_and_a_missing_order(self) -> None:
        """Attach takes one id. Reorder takes the id list and nothing else."""

        research_item_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(ValidationError):
            CarouselResearchAttachRequest.model_validate({
                "research_item_id": str(research_item_id),
                "position": 0,
            })

        with self.assertRaises(ValidationError):
            CarouselResearchOrderRequest.model_validate({
                "research_item_ids": [str(research_item_id)],
                "research_item_id": str(research_item_id),
            })

        with self.assertRaises(ValidationError):
            CarouselResearchOrderRequest.model_validate({})

        empty_order: CarouselResearchOrderRequest = CarouselResearchOrderRequest(
            research_item_ids=[],
        )

        self.assertEqual(empty_order.research_item_ids, [])


def _document(session: _MemoryCarouselSession, title: str) -> ResearchReadResponse:
    """Create one research document in the library."""

    created: ResearchReadResponse = create_research(
        ResearchCreateRequest(title=title),
        session,
        None,
    )

    return created


def _append(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    research_item_id: uuid.UUID,
) -> CarouselReadResponse:
    """POST one research document onto the carousel."""

    attached: CarouselReadResponse = post_carousel_research(
        carousel_id,
        CarouselResearchAttachRequest(research_item_id=research_item_id),
        session,
        None,
    )

    return attached


def _reorder(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    research_item_ids: list[uuid.UUID],
) -> CarouselReadResponse:
    """PUT the research order."""

    reordered: CarouselReadResponse = put_carousel_research(
        carousel_id,
        CarouselResearchOrderRequest(research_item_ids=research_item_ids),
        session,
        None,
    )

    return reordered


def _remove(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    research_item_id: uuid.UUID,
) -> CarouselReadResponse:
    """DELETE one research link."""

    removed: CarouselReadResponse = delete_carousel_research(
        carousel_id,
        research_item_id,
        session,
        None,
    )

    return removed


if __name__ == "__main__":
    unittest.main()
