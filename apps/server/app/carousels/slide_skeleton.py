"""How a slide follows its carousel's skeleton.

An image is required when the skeleton has a picture background or an
image element. Text is one value per text element. The same picture
rule decides whether Content is done and whether Slides is open.
A requested editor step is refused when that step is locked.
This module does not render or write files.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from app.models.enums import BackgroundKind, SkeletonElementContentKind
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement
from app.skeletons.elements import ordered_skeleton_elements


IMAGE_REQUIRED_DETAIL: str = "This skeleton needs an image on the slide."
IMAGE_NOT_USED_DETAIL: str = "This skeleton does not use a slide image."
UNKNOWN_TEXT_ELEMENT_DETAIL: str = "That text does not belong to this skeleton."
DUPLICATE_TEXT_ELEMENT_DETAIL: str = "Each skeleton text element is stored once."
CAROUSEL_SLIDES_DONE_COUNT: int = 2
EDITOR_STEP_BASIC: int = 0
EDITOR_STEP_INSTRUCTIONS: int = 1
EDITOR_STEP_CONTENT: int = 2
EDITOR_STEP_SLIDES: int = 3
EDITOR_STEP_FINAL: int = 4
STORED_EDITOR_STEPS: frozenset[int] = frozenset({
    EDITOR_STEP_BASIC,
    EDITOR_STEP_CONTENT,
    EDITOR_STEP_SLIDES,
})
UNKNOWN_EDITOR_STEP_DETAIL: str = "editor_step must be 0, 2, or 3."
INSTRUCTIONS_LOCKED_DETAIL: str = "Instructions is locked."
SLIDES_LOCKED_DETAIL: str = "Attach an album on Content first."
FINAL_LOCKED_DETAIL: str = "Final is locked."
LOCKED_EDITOR_STEP_DETAIL: str = "That step is locked."
_LOCKED_DETAIL_BY_STEP: dict[int, str] = {
    EDITOR_STEP_INSTRUCTIONS: INSTRUCTIONS_LOCKED_DETAIL,
    EDITOR_STEP_SLIDES: SLIDES_LOCKED_DETAIL,
    EDITOR_STEP_FINAL: FINAL_LOCKED_DETAIL,
}


class CarouselStepState(enum.StrEnum):
    """One derived step on the carousel stepper.

    ``locked`` cannot be opened. ``available`` can be opened and is not
    finished. ``done`` can be opened and the step's rule is met.
    """

    LOCKED = "locked"
    AVAILABLE = "available"
    DONE = "done"


@dataclass(frozen=True)
class SlideSkeletonFill:
    """Text and the one image used to draw a slide on its skeleton.

    ``slide_image_relative_path`` is null when the slide has no image yet.
    When this fill is used, picture backgrounds and image elements use
    that path instead of the skeleton's stored file.
    """

    text_by_element_id: dict[uuid.UUID, str]
    slide_image_relative_path: str | None


@dataclass(frozen=True)
class CarouselStepStates:
    """The five stepper states for one carousel. None of these are stored.

    ``basic`` is done once the carousel exists. ``instructions`` and
    ``final`` stay locked until later phases. ``content`` and ``slides``
    follow the album rule and the slide count.
    """

    basic: CarouselStepState
    instructions: CarouselStepState
    content: CarouselStepState
    slides: CarouselStepState
    final: CarouselStepState


def skeleton_requires_image(skeleton: Skeleton) -> bool:
    """Return true when the slide form should ask for an image.

    Args:
        skeleton: The carousel's skeleton, with elements loaded.

    Returns:
        True for a picture background or any image element.
    """

    if skeleton.background_kind == BackgroundKind.PICTURE:

        return True

    for element in skeleton.elements:

        if element.content_kind == SkeletonElementContentKind.IMAGE:

            return True

    return False


def carousel_step_states(
    skeleton: Skeleton,
    album_id: uuid.UUID | None,
    slide_count: int,
) -> CarouselStepStates:
    """Return the five derived step states for one carousel.

    The album rule passes when the skeleton needs no picture, or when
    ``album_id`` is set. A skeleton that needs no picture passes
    immediately, with or without an album. An attached album passes
    even when it has zero images. ``content`` is done when that rule
    passes and available otherwise. ``slides`` is locked when the rule
    fails, available when it passes and the carousel has fewer than two
    slides, and done at two or more. ``basic`` is done. ``instructions``
    and ``final`` are locked. Research is optional and does not change
    any state. This does not read or write ``editor_step``.

    Args:
        skeleton: The carousel's skeleton, with elements loaded.
        album_id: ``carousels.album_id``. Null when no album is attached.
        slide_count: Every slide on the carousel, including drafts.

    Returns:
        The five step states, in stepper order.
    """

    album_passes: bool = _album_rule_passes(skeleton, album_id)
    content_state: CarouselStepState = CarouselStepState.AVAILABLE
    slides_state: CarouselStepState = CarouselStepState.LOCKED

    if album_passes:
        content_state = CarouselStepState.DONE
        slides_state = CarouselStepState.AVAILABLE

    if album_passes and slide_count >= CAROUSEL_SLIDES_DONE_COUNT:
        slides_state = CarouselStepState.DONE

    step_states: CarouselStepStates = CarouselStepStates(
        basic=CarouselStepState.DONE,
        instructions=CarouselStepState.LOCKED,
        content=content_state,
        slides=slides_state,
        final=CarouselStepState.LOCKED,
    )

    return step_states


def accepted_editor_step(
    editor_step: int,
    step_states: CarouselStepStates,
) -> int:
    """Return ``editor_step`` when it may be stored.

    Stored steps are 0 Basic, 2 Content, and 3 Slides. Instructions
    and Final are locked and are never stored. Slides is refused while
    its derived state is locked. This does not write the carousel.

    Args:
        editor_step: The requested open step.
        step_states: Derived states for this carousel.

    Returns:
        The same step, when it may be written.

    Raises:
        ValueError: The step is locked, or it is not 0, 2, or 3.
    """

    step_state: CarouselStepState | None = _state_for_editor_step(
        editor_step,
        step_states,
    )

    if step_state is None:
        raise ValueError(UNKNOWN_EDITOR_STEP_DETAIL)

    if step_state == CarouselStepState.LOCKED:
        raise ValueError(_locked_editor_step_detail(editor_step))

    if editor_step not in STORED_EDITOR_STEPS:
        raise ValueError(UNKNOWN_EDITOR_STEP_DETAIL)

    return editor_step


def _state_for_editor_step(
    editor_step: int,
    step_states: CarouselStepStates,
) -> CarouselStepState | None:
    """Return the derived state for a step number, or null when it is not a step.

    Args:
        editor_step: 0 Basic through 4 Final.
        step_states: Derived states for this carousel.

    Returns:
        That step's state, or null for a number outside 0 through 4.
    """

    states_by_step: dict[int, CarouselStepState] = {
        EDITOR_STEP_BASIC: step_states.basic,
        EDITOR_STEP_INSTRUCTIONS: step_states.instructions,
        EDITOR_STEP_CONTENT: step_states.content,
        EDITOR_STEP_SLIDES: step_states.slides,
        EDITOR_STEP_FINAL: step_states.final,
    }
    found_state: CarouselStepState | None = states_by_step.get(editor_step)

    return found_state


def _locked_editor_step_detail(editor_step: int) -> str:
    """Return the refusal sentence for a locked step.

    Args:
        editor_step: A step number whose derived state is locked.

    Returns:
        A sentence naming that step. Slides names the album rule.
    """

    detail: str = _LOCKED_DETAIL_BY_STEP.get(editor_step, LOCKED_EDITOR_STEP_DETAIL)

    return detail


def _album_rule_passes(skeleton: Skeleton, album_id: uuid.UUID | None) -> bool:
    """Return true when Content is satisfied for this skeleton.

    Args:
        skeleton: The carousel's skeleton, with elements loaded.
        album_id: The attached album, or null.

    Returns:
        True when the skeleton needs no picture, or an album is set.
    """

    if not skeleton_requires_image(skeleton):

        return True

    album_is_set: bool = album_id is not None

    return album_is_set


def skeleton_text_elements(skeleton: Skeleton) -> list[SkeletonElement]:
    """Return the skeleton's text elements in frame order.

    Args:
        skeleton: The carousel's skeleton, with elements loaded.

    Returns:
        Text elements only, band then sort order.
    """

    ordered_elements: list[SkeletonElement] = ordered_skeleton_elements(skeleton.elements)
    text_elements: list[SkeletonElement] = [
        element
        for element in ordered_elements
        if element.content_kind == SkeletonElementContentKind.TEXT
    ]

    return text_elements


def text_values_for_skeleton(
    skeleton: Skeleton,
    submitted_texts: list[tuple[uuid.UUID, str]],
) -> list[tuple[uuid.UUID, str]]:
    """Keep one stored value per text element. Unknown ids are rejected.

    A missing element is stored as an empty string. Blank values are
    kept so the form can round-trip them.

    Args:
        skeleton: The carousel's skeleton.
        submitted_texts: Element id and raw value, in request order.

    Returns:
        One pair per text element, in frame order.

    Raises:
        ValueError: An id is not a text element on this skeleton, or it
            appears twice.
    """

    text_elements: list[SkeletonElement] = skeleton_text_elements(skeleton)
    allowed_ids: set[uuid.UUID] = {element.id for element in text_elements}
    seen_ids: set[uuid.UUID] = set()
    value_by_id: dict[uuid.UUID, str] = {}

    for element_id, raw_value in submitted_texts:

        if element_id not in allowed_ids:
            raise ValueError(UNKNOWN_TEXT_ELEMENT_DETAIL)

        if element_id in seen_ids:
            raise ValueError(DUPLICATE_TEXT_ELEMENT_DETAIL)

        seen_ids.add(element_id)
        value_by_id[element_id] = raw_value

    stored_values: list[tuple[uuid.UUID, str]] = [
        (element.id, value_by_id.get(element.id, ""))
        for element in text_elements
    ]

    return stored_values
