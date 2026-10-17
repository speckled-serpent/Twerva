"""How a slide follows its carousel's skeleton.

An image is required when the skeleton has a picture background or an
image element. Text is one value per text element. This module does
not render or write files.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class SlideSkeletonFill:
    """Text and the one image used to draw a slide on its skeleton.

    ``slide_image_relative_path`` is null when the slide has no image yet.
    When this fill is used, picture backgrounds and image elements use
    that path instead of the skeleton's stored file.
    """

    text_by_element_id: dict[uuid.UUID, str]
    slide_image_relative_path: str | None


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
