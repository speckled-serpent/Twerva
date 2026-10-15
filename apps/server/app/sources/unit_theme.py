"""How a unit follows its source's theme.

An image is required when the theme has a picture background or an
image element. Text is one value per text element. This module does
not render or write files.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.enums import BackgroundKind, ThemeElementContentKind
from app.models.theme import Theme
from app.models.theme_element import ThemeElement
from app.themes.elements import ordered_theme_elements


IMAGE_REQUIRED_DETAIL: str = "This theme needs an image on the unit."
IMAGE_NOT_USED_DETAIL: str = "This theme does not use a unit image."
UNKNOWN_TEXT_ELEMENT_DETAIL: str = "That text does not belong to this theme."
DUPLICATE_TEXT_ELEMENT_DETAIL: str = "Each theme text element is stored once."


@dataclass(frozen=True)
class UnitThemeFill:
    """Text and the one image used to draw a unit on its theme.

    ``unit_image_relative_path`` is null when the unit has no image yet.
    When this fill is used, picture backgrounds and image elements use
    that path instead of the theme's stored file.
    """

    text_by_element_id: dict[uuid.UUID, str]
    unit_image_relative_path: str | None


def theme_requires_image(theme: Theme) -> bool:
    """Return true when the unit form should ask for an image.

    Args:
        theme: The source's theme, with elements loaded.

    Returns:
        True for a picture background or any image element.
    """

    if theme.background_kind == BackgroundKind.PICTURE:

        return True

    for element in theme.elements:

        if element.content_kind == ThemeElementContentKind.IMAGE:

            return True

    return False


def theme_text_elements(theme: Theme) -> list[ThemeElement]:
    """Return the theme's text elements in frame order.

    Args:
        theme: The source's theme, with elements loaded.

    Returns:
        Text elements only, band then sort order.
    """

    ordered_elements: list[ThemeElement] = ordered_theme_elements(theme.elements)
    text_elements: list[ThemeElement] = [
        element
        for element in ordered_elements
        if element.content_kind == ThemeElementContentKind.TEXT
    ]

    return text_elements


def text_values_for_theme(
    theme: Theme,
    submitted_texts: list[tuple[uuid.UUID, str]],
) -> list[tuple[uuid.UUID, str]]:
    """Keep one stored value per text element. Unknown ids are rejected.

    A missing element is stored as an empty string. Blank values are
    kept so the form can round-trip them.

    Args:
        theme: The source's theme.
        submitted_texts: Element id and raw value, in request order.

    Returns:
        One pair per text element, in frame order.

    Raises:
        ValueError: An id is not a text element on this theme, or it
            appears twice.
    """

    text_elements: list[ThemeElement] = theme_text_elements(theme)
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
