"""Derived carousel step state, and the GET responses that return it."""

import os
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")

from app.api.v1.carousels import get_carousel
from app.api.v1.carousel_writes import create_carousel, create_slide
from app.api.v1.schemas import (
    CarouselCreateRequest,
    CarouselReadResponse,
    SlideWriteRequest,
)
from app.carousels.slide_skeleton import (
    CarouselStepState,
    CarouselStepStates,
    carousel_step_states,
)
from app.models.carousel import Carousel, CarouselResearchItem
from app.models.enums import (
    AdvertisementType,
    BackgroundKind,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonStatus,
    SlideTextStatus,
)
from app.models.research_item import ResearchItem
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement
from tests.test_carousel_writes import _MemoryCarouselSession


class CarouselStepStateHelperTests(unittest.TestCase):
    """The album rule and the two-slide done mark, without the database."""

    def test_picture_skeleton_without_an_album_locks_slides(self) -> None:
        """A picture background with a null album leaves Slides locked."""

        skeleton: Skeleton = _skeleton(BackgroundKind.PICTURE)
        states: CarouselStepStates = carousel_step_states(skeleton, None, 0)

        self._assert_closed_steps(states)
        self.assertEqual(states.content, CarouselStepState.AVAILABLE)
        self.assertEqual(states.slides, CarouselStepState.LOCKED)

    def test_existing_slides_stay_locked_until_the_album_rule_passes(self) -> None:
        """Slide count does not open Slides while the album is missing."""

        skeleton: Skeleton = _skeleton(BackgroundKind.PICTURE)
        states: CarouselStepStates = carousel_step_states(skeleton, None, 6)

        self.assertEqual(states.content, CarouselStepState.AVAILABLE)
        self.assertEqual(states.slides, CarouselStepState.LOCKED)

    def test_color_skeleton_opens_slides_before_any_slide_exists(self) -> None:
        """A color skeleton with a null album and no slides is available."""

        skeleton: Skeleton = _skeleton(BackgroundKind.COLOR)
        states: CarouselStepStates = carousel_step_states(skeleton, None, 0)

        self._assert_closed_steps(states)
        self.assertEqual(states.content, CarouselStepState.DONE)
        self.assertEqual(states.slides, CarouselStepState.AVAILABLE)

    def test_color_skeleton_is_done_once_it_has_two_slides(self) -> None:
        """One slide stays available. Two slides mark Slides done."""

        skeleton: Skeleton = _skeleton(BackgroundKind.COLOR)
        one_slide: CarouselStepStates = carousel_step_states(skeleton, None, 1)
        two_slides: CarouselStepStates = carousel_step_states(skeleton, None, 2)

        self.assertEqual(one_slide.slides, CarouselStepState.AVAILABLE)
        self.assertEqual(two_slides.content, CarouselStepState.DONE)
        self.assertEqual(two_slides.slides, CarouselStepState.DONE)

    def test_gradient_without_an_image_element_needs_no_album(self) -> None:
        """A gradient skeleton passes the album rule immediately."""

        skeleton: Skeleton = _skeleton(BackgroundKind.GRADIENT)
        states: CarouselStepStates = carousel_step_states(skeleton, None, 0)

        self.assertEqual(states.content, CarouselStepState.DONE)
        self.assertEqual(states.slides, CarouselStepState.AVAILABLE)

    def test_image_element_requires_an_album_on_a_color_background(self) -> None:
        """An image element needs an album even when the background is color."""

        skeleton: Skeleton = _skeleton(BackgroundKind.COLOR)
        skeleton.elements = [_image_element(skeleton.id)]
        states: CarouselStepStates = carousel_step_states(skeleton, None, 3)

        self.assertEqual(states.content, CarouselStepState.AVAILABLE)
        self.assertEqual(states.slides, CarouselStepState.LOCKED)

    def test_attached_album_with_no_slides_opens_slides(self) -> None:
        """An album id passes the rule before the album has any images."""

        skeleton: Skeleton = _skeleton(BackgroundKind.PICTURE)
        album_id: uuid.UUID = uuid.uuid4()
        states: CarouselStepStates = carousel_step_states(skeleton, album_id, 0)

        self.assertEqual(states.content, CarouselStepState.DONE)
        self.assertEqual(states.slides, CarouselStepState.AVAILABLE)

    def test_attached_album_is_done_at_two_slides(self) -> None:
        """A picture skeleton with an album is done once it has two slides."""

        skeleton: Skeleton = _skeleton(BackgroundKind.PICTURE)
        states: CarouselStepStates = carousel_step_states(skeleton, uuid.uuid4(), 2)

        self.assertEqual(states.content, CarouselStepState.DONE)
        self.assertEqual(states.slides, CarouselStepState.DONE)

    def _assert_closed_steps(self, states: CarouselStepStates) -> None:
        """Basic is done. Instructions and Final stay locked."""

        self.assertEqual(states.basic, CarouselStepState.DONE)
        self.assertEqual(states.instructions, CarouselStepState.LOCKED)
        self.assertEqual(states.final, CarouselStepState.LOCKED)


class CarouselStepReadTests(unittest.TestCase):
    """GET detail returns generation, the open step, research, and steps."""

    def test_picture_skeleton_with_null_album_locks_slides(self) -> None:
        """A picture skeleton with no album reads content available and slides locked."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Harbor")
        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertIsNone(loaded.album_id)
        self.assertEqual(loaded.generation_number, 1)
        self.assertEqual(loaded.editor_step, 3)
        self.assertEqual(loaded.research, [])
        self.assertEqual(loaded.steps.basic, CarouselStepState.DONE)
        self.assertEqual(loaded.steps.instructions, CarouselStepState.LOCKED)
        self.assertEqual(loaded.steps.content, CarouselStepState.AVAILABLE)
        self.assertEqual(loaded.steps.slides, CarouselStepState.LOCKED)
        self.assertEqual(loaded.steps.final, CarouselStepState.LOCKED)

    def test_color_skeleton_with_null_album_opens_then_finishes_slides(self) -> None:
        """No slides reads available. The same carousel reads done at two slides."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Notes")
        empty: CarouselReadResponse = get_carousel(created.id, session)

        self.assertIsNone(empty.album_id)
        self.assertEqual(empty.steps.content, CarouselStepState.DONE)
        self.assertEqual(empty.steps.slides, CarouselStepState.AVAILABLE)

        create_slide(created.id, SlideWriteRequest(name="One"), session, None)
        one_slide: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(len(one_slide.slides), 1)
        self.assertEqual(one_slide.steps.slides, CarouselStepState.AVAILABLE)

        create_slide(created.id, SlideWriteRequest(name="Two"), session, None)
        two_slides: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(len(two_slides.slides), 2)
        self.assertEqual(two_slides.steps.content, CarouselStepState.DONE)
        self.assertEqual(two_slides.steps.slides, CarouselStepState.DONE)

    def test_draft_slides_count_toward_the_done_mark(self) -> None:
        """Slides is done at two slides, including drafts that are not live."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Drafts")
        create_slide(created.id, SlideWriteRequest(name="One"), session, None)
        create_slide(created.id, SlideWriteRequest(name="Two"), session, None)
        stored: Carousel | None = session.get(Carousel, created.id)

        assert stored is not None

        for slide in list(stored.slides):
            slide.text_status = SlideTextStatus.DRAFT

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(loaded.live_slide_count, 0)
        self.assertEqual(loaded.steps.slides, CarouselStepState.DONE)

    def test_stored_open_step_is_independent_of_derived_state(self) -> None:
        """editor_step is the stored number. steps is computed beside it."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Stored")
        stored: Carousel | None = session.get(Carousel, created.id)

        assert stored is not None

        stored.generation_number = 2
        stored.editor_step = 0
        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(loaded.generation_number, 2)
        self.assertEqual(loaded.editor_step, 0)
        self.assertEqual(loaded.steps.slides, CarouselStepState.AVAILABLE)

    def test_picture_album_with_no_images_opens_slides(self) -> None:
        """Setting album_id passes the rule. The read does not count images."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Album")
        stored: Carousel | None = session.get(Carousel, created.id)
        album_id: uuid.UUID = uuid.uuid4()

        assert stored is not None

        stored.album_id = album_id
        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(loaded.album_id, album_id)
        self.assertEqual(loaded.slides, [])
        self.assertEqual(loaded.steps.content, CarouselStepState.DONE)
        self.assertEqual(loaded.steps.slides, CarouselStepState.AVAILABLE)

    def test_research_is_the_item_id_in_position_order(self) -> None:
        """Research returns each attached item, ordered by position."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Reading")
        stored: Carousel | None = session.get(Carousel, created.id)
        later: ResearchItem = _research("Later note", "later-note")
        first: ResearchItem = _research("First note", "first-note")

        assert stored is not None

        stored.research_links = [
            _research_link(stored, later, 1),
            _research_link(stored, first, 0),
        ]
        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(
            [item.position for item in loaded.research],
            [0, 1],
        )
        self.assertEqual(loaded.research[0].id, first.id)
        self.assertEqual(loaded.research[0].title, "First note")
        self.assertEqual(loaded.research[0].slug, "first-note")
        self.assertEqual(loaded.research[1].id, later.id)
        self.assertEqual(loaded.research[1].slug, "later-note")
        self.assertNotEqual(loaded.research[0].id, stored.research_links[0].id)


def _create(session: _MemoryCarouselSession, name: str) -> CarouselReadResponse:
    """Create one carousel on the session's skeleton."""

    created: CarouselReadResponse = create_carousel(
        CarouselCreateRequest(name=name, skeleton_id=session.skeleton.id),
        session,
        None,
    )

    return created


def _skeleton(background_kind: BackgroundKind) -> Skeleton:
    """A skeleton with no elements and the given background."""

    skeleton: Skeleton = Skeleton(
        id=uuid.uuid4(),
        name="Frame",
        slug=f"frame-{uuid.uuid4().hex[:8]}",
        advertisement_type=AdvertisementType.CAROUSEL,
        status=SkeletonStatus.DRAFT,
        background_kind=background_kind,
    )
    skeleton.elements = []

    return skeleton


def _image_element(skeleton_id: uuid.UUID) -> SkeletonElement:
    """One image element. Its path is not opened."""

    element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=skeleton_id,
        band=SkeletonElementBand.MIDDLE,
        sort_order=0,
        content_kind=SkeletonElementContentKind.IMAGE,
        name="Photo",
        image_asset_ref="theme-defaults/ocean-waves.jpg",
    )

    return element


def _research(title: str, slug: str) -> ResearchItem:
    """One research document. The body is unused by the carousel read."""

    item: ResearchItem = ResearchItem(
        id=uuid.uuid4(),
        title=title,
        slug=slug,
        body="A note.",
    )

    return item


def _research_link(
    carousel: Carousel,
    item: ResearchItem,
    position: int,
) -> CarouselResearchItem:
    """Attach one research item at a position. The link id is not the item id."""

    link: CarouselResearchItem = CarouselResearchItem(
        id=uuid.uuid4(),
        carousel_id=carousel.id,
        research_item_id=item.id,
        position=position,
    )
    link.research_item = item

    return link


if __name__ == "__main__":
    unittest.main()
