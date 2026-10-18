"""PATCH /api/v1/carousels/{id}/step stores an open step and refuses a locked one."""

import os
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.carousel_writes import (
    create_carousel,
    create_slide,
    patch_carousel,
    patch_carousel_step,
)
from app.api.v1.carousels import get_carousel
from app.api.v1.schemas import (
    CarouselCreateRequest,
    CarouselPatchRequest,
    CarouselReadResponse,
    CarouselStepPatchRequest,
    SlideWriteRequest,
)
from app.carousels.editing import BLANK_NAME_DETAIL
from app.carousels.slide_skeleton import (
    FINAL_LOCKED_DETAIL,
    INSTRUCTIONS_LOCKED_DETAIL,
    SLIDES_LOCKED_DETAIL,
    UNKNOWN_EDITOR_STEP_DETAIL,
    CarouselStepState,
    CarouselStepStates,
    accepted_editor_step,
)
from app.models.carousel import Carousel
from app.models.enums import (
    BackgroundKind,
    SkeletonElementBand,
    SkeletonElementContentKind,
)
from app.models.skeleton_element import SkeletonElement
from tests.test_carousel_writes import _MemoryCarouselSession


class AcceptedEditorStepTests(unittest.TestCase):
    """The stored steps are 0, 2, and 3. A locked step is refused."""

    def test_open_steps_are_returned(self) -> None:
        """Basic, Content, and an open Slides step may be stored."""

        states: CarouselStepStates = _states(
            content=CarouselStepState.AVAILABLE,
            slides=CarouselStepState.AVAILABLE,
        )

        self.assertEqual(accepted_editor_step(0, states), 0)
        self.assertEqual(accepted_editor_step(2, states), 2)
        self.assertEqual(accepted_editor_step(3, states), 3)

    def test_done_slides_may_be_stored(self) -> None:
        """A done step can still be opened."""

        states: CarouselStepStates = _states(
            content=CarouselStepState.DONE,
            slides=CarouselStepState.DONE,
        )

        self.assertEqual(accepted_editor_step(3, states), 3)

    def test_locked_steps_name_the_refusal(self) -> None:
        """Instructions, Final, and locked Slides each say why."""

        states: CarouselStepStates = _states(
            content=CarouselStepState.AVAILABLE,
            slides=CarouselStepState.LOCKED,
        )

        self.assertEqual(_refusal(1, states), INSTRUCTIONS_LOCKED_DETAIL)
        self.assertEqual(_refusal(4, states), FINAL_LOCKED_DETAIL)
        self.assertEqual(_refusal(3, states), SLIDES_LOCKED_DETAIL)

    def test_a_number_outside_the_stepper_is_refused(self) -> None:
        """5 and -1 are not steps, so they are not stored."""

        states: CarouselStepStates = _states(
            content=CarouselStepState.DONE,
            slides=CarouselStepState.DONE,
        )

        self.assertEqual(_refusal(5, states), UNKNOWN_EDITOR_STEP_DETAIL)
        self.assertEqual(_refusal(-1, states), UNKNOWN_EDITOR_STEP_DETAIL)


class CarouselEditorStepWriteTests(unittest.TestCase):
    """Admin step changes. A 400 leaves the stored step where it was."""

    def test_create_opens_on_basic_and_keeps_the_skeleton(self) -> None:
        """Create stores generation 1 and editor step 0.

        The skeleton is the one from create. A rename body that includes
        a skeleton id is rejected, including when the carousel has no
        slides. A renamed label is still there after a reload.
        """

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Harbor")
        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(created.generation_number, 1)
        self.assertEqual(created.editor_step, 0)
        self.assertEqual(created.skeleton_id, session.skeleton.id)
        self.assertEqual(created.slides, [])
        self.assertEqual(loaded.generation_number, 1)
        self.assertEqual(loaded.editor_step, 0)
        self.assertEqual(loaded.skeleton_id, session.skeleton.id)
        self.assertEqual(loaded.slides, [])

        with self.assertRaises(ValidationError):
            CarouselPatchRequest.model_validate({
                "name": "Harbor",
                "skeleton_id": str(uuid.uuid4()),
            })

        renamed: CarouselReadResponse = patch_carousel(
            created.id,
            CarouselPatchRequest(name="Outer harbor"),
            session,
            None,
        )
        reloaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(renamed.name, "Outer harbor")
        self.assertEqual(renamed.editor_step, 0)
        self.assertEqual(renamed.skeleton_id, session.skeleton.id)
        self.assertEqual(reloaded.name, "Outer harbor")
        self.assertEqual(reloaded.editor_step, 0)
        self.assertEqual(reloaded.skeleton_id, session.skeleton.id)
        self.assertEqual(reloaded.slides, [])

    def test_blank_name_or_missing_skeleton_does_not_create_a_row(self) -> None:
        """A blank name is 400. An unknown skeleton is 404. Neither writes."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()

        with self.assertRaises(HTTPException) as blank:
            create_carousel(
                CarouselCreateRequest(name="   ", skeleton_id=session.skeleton.id),
                session,
                None,
            )

        with self.assertRaises(HTTPException) as missing:
            create_carousel(
                CarouselCreateRequest(name="Harbor", skeleton_id=uuid.uuid4()),
                session,
                None,
            )

        self.assertEqual(blank.exception.status_code, 400)
        self.assertEqual(blank.exception.detail, BLANK_NAME_DETAIL)
        self.assertEqual(missing.exception.status_code, 404)
        self.assertEqual(session.carousels, [])
        self.assertEqual(session.commit_count, 0)

    def test_blank_rename_leaves_the_stored_label(self) -> None:
        """A blank name does not save. The label from create stays."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Harbor")
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as blank:
            patch_carousel(
                created.id,
                CarouselPatchRequest(name="   "),
                session,
                None,
            )

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(blank.exception.status_code, 400)
        self.assertEqual(blank.exception.detail, BLANK_NAME_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(loaded.name, "Harbor")
        self.assertEqual(loaded.editor_step, 0)
        self.assertEqual(loaded.skeleton_id, session.skeleton.id)

    def test_admin_stores_step_0_or_2_on_any_carousel(self) -> None:
        """Basic and Content can be stored while Slides is locked or done."""

        picture: _MemoryCarouselSession = _MemoryCarouselSession()
        picture.skeleton.background_kind = BackgroundKind.PICTURE
        picture.skeleton.elements = []
        locked: CarouselReadResponse = _create(picture, "Locked slides")
        moved_basic: CarouselReadResponse = _store_step(picture, locked.id, 0)
        moved_content: CarouselReadResponse = _store_step(picture, locked.id, 2)

        self.assertEqual(moved_basic.editor_step, 0)
        self.assertEqual(moved_basic.steps.slides, CarouselStepState.LOCKED)
        self.assertEqual(moved_content.editor_step, 2)
        self.assertEqual(moved_content.steps.slides, CarouselStepState.LOCKED)
        self.assertEqual(moved_content.skeleton_id, locked.skeleton_id)
        self.assertIsNone(moved_content.album_id)

        color: _MemoryCarouselSession = _MemoryCarouselSession()
        color.skeleton.background_kind = BackgroundKind.COLOR
        color.skeleton.elements = []
        open_slides: CarouselReadResponse = _create(color, "Open slides")
        _add_slide(color, open_slides.id, "One")
        _add_slide(color, open_slides.id, "Two")
        stored_basic: CarouselReadResponse = _store_step(color, open_slides.id, 0)
        stored_content: CarouselReadResponse = _store_step(color, open_slides.id, 2)

        self.assertEqual(stored_basic.steps.slides, CarouselStepState.DONE)
        self.assertEqual(stored_basic.editor_step, 0)
        self.assertEqual(stored_content.editor_step, 2)

    def test_step_3_is_stored_when_the_album_rule_passes(self) -> None:
        """Slides may be stored while it is available or done."""

        color: _MemoryCarouselSession = _MemoryCarouselSession()
        color.skeleton.background_kind = BackgroundKind.COLOR
        color.skeleton.elements = []
        created: CarouselReadResponse = _create(color, "Notes")
        _store_step(color, created.id, 0)
        available: CarouselReadResponse = _store_step(color, created.id, 3)

        self.assertEqual(available.editor_step, 3)
        self.assertEqual(available.steps.slides, CarouselStepState.AVAILABLE)
        self.assertIsNone(available.album_id)

        _add_slide(color, created.id, "One")
        _add_slide(color, created.id, "Two")
        done: CarouselReadResponse = _store_step(color, created.id, 3)

        self.assertEqual(done.editor_step, 3)
        self.assertEqual(done.steps.slides, CarouselStepState.DONE)

        picture: _MemoryCarouselSession = _MemoryCarouselSession()
        picture.skeleton.background_kind = BackgroundKind.PICTURE
        picture.skeleton.elements = []
        with_album: CarouselReadResponse = _create(picture, "With album")
        _attach_album(picture, with_album.id)
        stored: CarouselReadResponse = _store_step(picture, with_album.id, 3)

        self.assertEqual(stored.editor_step, 3)
        self.assertIsNotNone(stored.album_id)
        self.assertEqual(stored.steps.slides, CarouselStepState.AVAILABLE)

    def test_picture_carousel_without_an_album_keeps_its_step_when_slides_is_refused(
        self,
    ) -> None:
        """Step 3 is 400 while Slides is locked, and the previous step stays."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "No album")
        previous: CarouselReadResponse = _store_step(session, created.id, 2)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            _store_step(session, created.id, 3)

        loaded: CarouselReadResponse = get_carousel(created.id, session)
        stored: Carousel | None = session.get(Carousel, created.id)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, SLIDES_LOCKED_DETAIL)
        self.assertEqual(previous.editor_step, 2)
        self.assertEqual(loaded.editor_step, 2)
        self.assertEqual(session.commit_count, commits_before)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.editor_step, 2)
        self.assertEqual(loaded.steps.slides, CarouselStepState.LOCKED)
        self.assertIsNone(loaded.album_id)

    def test_image_element_without_an_album_refuses_slides(self) -> None:
        """An image element locks Slides the same way a picture background does."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = [_image_element(session.skeleton.id)]
        created: CarouselReadResponse = _create(session, "Needs a photo")
        _store_step(session, created.id, 0)

        with self.assertRaises(HTTPException) as raised:
            _store_step(session, created.id, 3)

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, SLIDES_LOCKED_DETAIL)
        self.assertEqual(loaded.editor_step, 0)

    def test_refusing_instructions_leaves_inspiration_and_rules(self) -> None:
        """Step 1 does not write. Inspiration and rules read back as stored."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Harbor notes")
        stored: Carousel | None = session.get(Carousel, created.id)

        self.assertIsNotNone(stored)
        assert stored is not None
        stored.inspiration = "Harbor fog"
        stored.rules = "Keep the caption short"
        before: CarouselReadResponse = get_carousel(created.id, session)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            _store_step(session, created.id, 1)

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, INSTRUCTIONS_LOCKED_DETAIL)
        self.assertEqual(before.inspiration, "Harbor fog")
        self.assertEqual(before.rules, "Keep the caption short")
        self.assertEqual(loaded.inspiration, before.inspiration)
        self.assertEqual(loaded.rules, before.rules)
        self.assertEqual(loaded.editor_step, created.editor_step)
        self.assertEqual(stored.inspiration, "Harbor fog")
        self.assertEqual(stored.rules, "Keep the caption short")
        self.assertEqual(session.commit_count, commits_before)

    def test_instructions_and_final_are_refused(self) -> None:
        """Steps 1 and 4 are 400. The stored step stays."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Closed steps")
        _store_step(session, created.id, 0)

        with self.assertRaises(HTTPException) as instructions:
            _store_step(session, created.id, 1)

        with self.assertRaises(HTTPException) as final:
            _store_step(session, created.id, 4)

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(instructions.exception.status_code, 400)
        self.assertEqual(instructions.exception.detail, INSTRUCTIONS_LOCKED_DETAIL)
        self.assertEqual(final.exception.status_code, 400)
        self.assertEqual(final.exception.detail, FINAL_LOCKED_DETAIL)
        self.assertEqual(loaded.editor_step, 0)

    def test_a_step_outside_the_stepper_leaves_the_stored_step(self) -> None:
        """A value other than 0 through 4 is 400 and writes nothing."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Out of range")
        _store_step(session, created.id, 2)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            _store_step(session, created.id, 5)

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, UNKNOWN_EDITOR_STEP_DETAIL)
        self.assertEqual(loaded.editor_step, 2)
        self.assertEqual(session.commit_count, commits_before)

    def test_missing_carousel_is_not_found(self) -> None:
        """An unknown id is 404 and does not commit."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        missing_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised:
            _store_step(session, missing_id, 0)

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(session.commit_count, 0)
        self.assertEqual(session.carousels, [])

    def test_rename_stays_a_rename(self) -> None:
        """The carousel PATCH accepts a name only and leaves the open step."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Harbor")
        _store_step(session, created.id, 0)
        renamed: CarouselReadResponse = patch_carousel(
            created.id,
            CarouselPatchRequest(name="Outer harbor"),
            session,
            None,
        )

        with self.assertRaises(ValidationError):
            CarouselPatchRequest.model_validate({
                "name": "Harbor",
                "editor_step": 2,
            })

        with self.assertRaises(ValidationError):
            CarouselPatchRequest.model_validate({
                "name": "Harbor",
                "skeleton_id": str(uuid.uuid4()),
            })

        with self.assertRaises(ValidationError):
            CarouselStepPatchRequest.model_validate({
                "editor_step": 0,
                "skeleton_id": str(session.skeleton.id),
            })

        self.assertEqual(renamed.name, "Outer harbor")
        self.assertEqual(renamed.slug, "harbor")
        self.assertEqual(renamed.editor_step, 0)
        self.assertEqual(renamed.skeleton_id, created.skeleton_id)


def _states(
    content: CarouselStepState,
    slides: CarouselStepState,
) -> CarouselStepStates:
    """Build the five states. Instructions and Final stay locked."""

    states: CarouselStepStates = CarouselStepStates(
        basic=CarouselStepState.DONE,
        instructions=CarouselStepState.LOCKED,
        content=content,
        slides=slides,
        final=CarouselStepState.LOCKED,
    )

    return states


def _refusal(editor_step: int, states: CarouselStepStates) -> str:
    """Return the refusal sentence for a step that must not be stored."""

    try:
        accepted_editor_step(editor_step, states)
    except ValueError as step_error:
        detail: str = str(step_error)

        return detail

    raise AssertionError(f"editor step {editor_step} was stored")


def _create(session: _MemoryCarouselSession, name: str) -> CarouselReadResponse:
    """Create one carousel on the session's skeleton."""

    created: CarouselReadResponse = create_carousel(
        CarouselCreateRequest(name=name, skeleton_id=session.skeleton.id),
        session,
        None,
    )

    return created


def _store_step(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    editor_step: int,
) -> CarouselReadResponse:
    """PATCH the open step."""

    stored: CarouselReadResponse = patch_carousel_step(
        carousel_id,
        CarouselStepPatchRequest(editor_step=editor_step),
        session,
        None,
    )

    return stored


def _add_slide(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    name: str,
) -> None:
    """Add a text-only slide. The skeleton must not require an image."""

    create_slide(
        carousel_id,
        SlideWriteRequest(name=name),
        session,
        None,
    )


def _attach_album(session: _MemoryCarouselSession, carousel_id: uuid.UUID) -> None:
    """Point the carousel at an album id. The album row is not required."""

    stored: Carousel | None = session.get(Carousel, carousel_id)

    assert stored is not None

    stored.album_id = uuid.uuid4()


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


if __name__ == "__main__":
    unittest.main()
