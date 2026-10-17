"""Validate and order skeleton elements. Does not measure or read files."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import (
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
)
from app.models.skeleton_element import SkeletonElement
from app.skeletons.background import SkeletonBackgroundError, normalize_background_asset_ref


SKELETON_ELEMENT_TEXT_SOURCE_FORBIDDEN_DETAIL: str = (
    "An image element cannot set text_source."
)
SKELETON_ELEMENT_FONT_FAMILY_DETAIL: str = "font_family is required."
SKELETON_ELEMENT_FONT_SIZE_DETAIL: str = "font_size must be a positive integer."
SKELETON_ELEMENT_FONT_COLOR_DETAIL: str = "font_color is required."
SKELETON_ELEMENT_ALIGNMENT_DETAIL: str = "alignment is required."
SKELETON_ELEMENT_FONT_WEIGHT_DETAIL: str = "font_weight must be from 1 through 1000."
SKELETON_ELEMENT_IMAGE_REF_REQUIRED_DETAIL: str = (
    "An image element requires an image asset ref."
)
SKELETON_ELEMENT_IMAGE_REF_DETAIL: str = (
    "image_asset_ref must be a relative path with no .. and no scheme, "
    "ending in .svg, .png, .jpg, or .jpeg."
)
SKELETON_ELEMENT_SORT_ORDER_DETAIL: str = "sort_order must be zero or greater."
SKELETON_ELEMENT_CONTENT_KIND_REQUIRED_DETAIL: str = "content_kind is required."
SKELETON_ELEMENT_BAND_REQUIRED_DETAIL: str = "band is required."
SKELETON_ELEMENT_RECTANGLE_OPACITY_DETAIL: str = (
    "rectangle_opacity must be an integer from 0 through 100."
)
SKELETON_ELEMENT_RECTANGLE_RADIUS_DETAIL: str = (
    "rectangle_radius must be an integer from 0 through 10000."
)
DEFAULT_RECTANGLE_OPACITY: int = 100
DEFAULT_RECTANGLE_RADIUS: int = 0
MAX_RECTANGLE_OPACITY: int = 100
MAX_RECTANGLE_RADIUS: int = 10000

BAND_READ_ORDER: tuple[SkeletonElementBand, ...] = (
    SkeletonElementBand.TOP,
    SkeletonElementBand.MIDDLE,
    SkeletonElementBand.BOTTOM,
)


class SkeletonElementError(Exception):
    """An element value breaks the text or image rules."""

    def __init__(self, detail: str) -> None:

        super().__init__(detail)
        self.detail: str = detail


class ResolvedSkeletonElement:
    """Element columns after create or patch, before they are written."""

    def __init__(
        self,
        content_kind: SkeletonElementContentKind,
        rectangle_color: str | None,
        text_source: SkeletonElementTextSource | None,
        font_family: str | None,
        font_size: int | None,
        font_color: str | None,
        bold: bool,
        italic: bool,
        underline: bool,
        strikethrough: bool,
        font_weight: int | None,
        alignment: SkeletonElementAlignment | None,
        image_asset_ref: str | None,
        rectangle_opacity: int,
        rectangle_radius: int,
    ) -> None:

        self.content_kind: SkeletonElementContentKind = content_kind
        self.rectangle_color: str | None = rectangle_color
        self.text_source: SkeletonElementTextSource | None = text_source
        self.font_family: str | None = font_family
        self.font_size: int | None = font_size
        self.font_color: str | None = font_color
        self.bold: bool = bold
        self.italic: bool = italic
        self.underline: bool = underline
        self.strikethrough: bool = strikethrough
        self.font_weight: int | None = font_weight
        self.alignment: SkeletonElementAlignment | None = alignment
        self.image_asset_ref: str | None = image_asset_ref
        self.rectangle_opacity: int = rectangle_opacity
        self.rectangle_radius: int = rectangle_radius


def resolve_skeleton_element(
    content_kind: SkeletonElementContentKind | None,
    rectangle_color: str | None,
    text_source: SkeletonElementTextSource | None,
    font_family: str | None,
    font_size: int | None,
    font_color: str | None,
    bold: bool | None,
    italic: bool | None,
    underline: bool | None,
    strikethrough: bool | None,
    font_weight: int | None,
    alignment: SkeletonElementAlignment | None,
    image_asset_ref: str | None,
    rectangle_opacity: int | None = None,
    rectangle_radius: int | None = None,
) -> ResolvedSkeletonElement:
    """Return element columns that satisfy the text or image check.

    Args:
        content_kind: ``text`` or ``image``.
        rectangle_color: Rectangle fill, or null when the rectangle is clear.
        text_source: Optional Spotmu field. Null is allowed on text.
        font_family: Type family for a text element.
        font_size: Positive size for a text element.
        font_color: Color text for a text element.
        bold: Style flag. Null is rejected.
        italic: Style flag. Null is rejected.
        underline: Style flag. Null is rejected.
        strikethrough: Style flag. Null is rejected.
        font_weight: Optional weight from 1 through 1000.
        alignment: Horizontal alignment. Required for text.
        image_asset_ref: Relative image path. Required for image.
        rectangle_opacity: 0 through 100. Null stores 100.
        rectangle_radius: Corner radius in pixels. Null stores 0.

    Returns:
        Columns to store, with blanks normalized to null.

    Raises:
        SkeletonElementError: The combination is not a valid text or image row.
    """

    if content_kind is None:
        raise SkeletonElementError(SKELETON_ELEMENT_CONTENT_KIND_REQUIRED_DETAIL)

    stored_bold: bool = _required_boolean("bold", bold)
    stored_italic: bool = _required_boolean("italic", italic)
    stored_underline: bool = _required_boolean("underline", underline)
    stored_strikethrough: bool = _required_boolean("strikethrough", strikethrough)
    stored_font_weight: int | None = _font_weight_to_store(font_weight)
    stored_rectangle_color: str | None = _blank_to_none(rectangle_color)
    stored_image_asset_ref: str | None = _image_asset_ref_to_store(image_asset_ref)
    stored_font_family: str | None = _blank_to_none(font_family)
    stored_font_color: str | None = _blank_to_none(font_color)
    stored_font_size: int | None = _optional_positive_font_size(font_size)
    stored_rectangle_opacity: int = _rectangle_opacity_to_store(rectangle_opacity)
    stored_rectangle_radius: int = _rectangle_radius_to_store(rectangle_radius)

    if content_kind == SkeletonElementContentKind.TEXT:
        _require_text_payload(
            stored_font_family,
            stored_font_size,
            stored_font_color,
            alignment,
        )
    else:
        _require_image_payload(text_source, stored_image_asset_ref)

    resolved_element: ResolvedSkeletonElement = ResolvedSkeletonElement(
        content_kind,
        stored_rectangle_color,
        text_source if content_kind == SkeletonElementContentKind.TEXT else None,
        stored_font_family,
        stored_font_size,
        stored_font_color,
        stored_bold,
        stored_italic,
        stored_underline,
        stored_strikethrough,
        stored_font_weight,
        alignment,
        stored_image_asset_ref,
        stored_rectangle_opacity,
        stored_rectangle_radius,
    )

    return resolved_element


def ordered_skeleton_elements(elements: Iterable[SkeletonElement]) -> list[SkeletonElement]:
    """Return elements by band (top, middle, bottom) then sort_order.

    Args:
        elements: Rows already stored on one skeleton.

    Returns:
        A new list. The input rows are not reordered in place.
    """

    band_rank: dict[SkeletonElementBand, int] = {
        band: index for index, band in enumerate(BAND_READ_ORDER)
    }

    def sort_key(element: SkeletonElement) -> tuple[int, int]:

        return (band_rank[element.band], element.sort_order)

    ordered_elements: list[SkeletonElement] = sorted(elements, key=sort_key)

    return ordered_elements


def elements_in_band(
    elements: Iterable[SkeletonElement],
    band: SkeletonElementBand,
    excluded: SkeletonElement | None,
) -> list[SkeletonElement]:
    """Return one band in current sort_order, optionally skipping one row.

    Args:
        elements: Rows on the skeleton.
        band: Band to collect.
        excluded: Row to leave out, or None.

    Returns:
        Members of ``band`` except ``excluded``, lowest sort_order first.
    """

    members: list[SkeletonElement] = [
        element
        for element in elements
        if element.band == band and element is not excluded
    ]
    members.sort(key=_sort_order_key)

    return members


def insert_index(requested_sort_order: int | None, length: int) -> int:
    """Return where a row should sit in a band.

    Args:
        requested_sort_order: Desired 0-based index, or None to append.
        length: How many rows are already in the band.

    Returns:
        An index from 0 through ``length``. Values past the end append.

    Raises:
        SkeletonElementError: The requested index is negative.
    """

    if requested_sort_order is None:

        return length

    if requested_sort_order < 0:
        raise SkeletonElementError(SKELETON_ELEMENT_SORT_ORDER_DETAIL)

    if requested_sort_order > length:

        return length

    return requested_sort_order


def assign_compact_sort_orders(members: list[SkeletonElement]) -> None:
    """Renumber ``members`` from 0 in their current list order.

    Callers that flush to Postgres should first move these rows off the
    unique ``(skeleton_id, band, sort_order)`` key, then call this.

    Args:
        members: One band, already in the order to store.
    """

    for index, member in enumerate(members):
        member.sort_order = index


def assign_temporary_sort_orders(members: list[SkeletonElement]) -> None:
    """Give ``members`` unique negative sort orders so a later compact can flush.

    Args:
        members: One band about to be renumbered from 0.
    """

    for index, member in enumerate(members):
        member.sort_order = -(index + 1)


def _require_text_payload(
    font_family: str | None,
    font_size: int | None,
    font_color: str | None,
    alignment: SkeletonElementAlignment | None,
) -> None:
    """Reject a text element that is missing family, size, color, or alignment."""

    if font_family is None:
        raise SkeletonElementError(SKELETON_ELEMENT_FONT_FAMILY_DETAIL)

    if font_size is None:
        raise SkeletonElementError(SKELETON_ELEMENT_FONT_SIZE_DETAIL)

    if font_color is None:
        raise SkeletonElementError(SKELETON_ELEMENT_FONT_COLOR_DETAIL)

    if alignment is None:
        raise SkeletonElementError(SKELETON_ELEMENT_ALIGNMENT_DETAIL)


def _require_image_payload(
    text_source: SkeletonElementTextSource | None,
    image_asset_ref: str | None,
) -> None:
    """Reject an image element with a text source or no asset ref."""

    if text_source is not None:
        raise SkeletonElementError(SKELETON_ELEMENT_TEXT_SOURCE_FORBIDDEN_DETAIL)

    if image_asset_ref is None:
        raise SkeletonElementError(SKELETON_ELEMENT_IMAGE_REF_REQUIRED_DETAIL)


def _image_asset_ref_to_store(image_asset_ref: str | None) -> str | None:
    """Return a relative image path, or null when the client sent a blank."""

    try:
        stored_asset_ref: str | None = normalize_background_asset_ref(image_asset_ref)
    except SkeletonBackgroundError as background_error:
        raise SkeletonElementError(SKELETON_ELEMENT_IMAGE_REF_DETAIL) from background_error

    return stored_asset_ref


def rectangle_opacity_value(rectangle_opacity: int | None) -> int:
    """Return a stored opacity. Null means the column default, 100."""

    if rectangle_opacity is None:

        return DEFAULT_RECTANGLE_OPACITY

    return rectangle_opacity


def rectangle_radius_value(rectangle_radius: int | None) -> int:
    """Return a stored radius. Null means the column default, 0."""

    if rectangle_radius is None:

        return DEFAULT_RECTANGLE_RADIUS

    return rectangle_radius


def _rectangle_opacity_to_store(rectangle_opacity: int | None) -> int:
    """Return 0 through 100. Null stores a solid rectangle."""

    if rectangle_opacity is None:

        return DEFAULT_RECTANGLE_OPACITY

    if rectangle_opacity < 0 or rectangle_opacity > MAX_RECTANGLE_OPACITY:
        raise SkeletonElementError(SKELETON_ELEMENT_RECTANGLE_OPACITY_DETAIL)

    return rectangle_opacity


def _rectangle_radius_to_store(rectangle_radius: int | None) -> int:
    """Return a non-negative radius. Null stores square corners."""

    if rectangle_radius is None:

        return DEFAULT_RECTANGLE_RADIUS

    if rectangle_radius < 0 or rectangle_radius > MAX_RECTANGLE_RADIUS:
        raise SkeletonElementError(SKELETON_ELEMENT_RECTANGLE_RADIUS_DETAIL)

    return rectangle_radius


def _font_weight_to_store(font_weight: int | None) -> int | None:
    """Return a weight from 1 through 1000, or null."""

    if font_weight is None:

        return None

    if font_weight < 1 or font_weight > 1000:
        raise SkeletonElementError(SKELETON_ELEMENT_FONT_WEIGHT_DETAIL)

    return font_weight


def _optional_positive_font_size(font_size: int | None) -> int | None:
    """Return a positive size, or null. Zero and negatives are rejected."""

    if font_size is None:

        return None

    if font_size < 1:
        raise SkeletonElementError(SKELETON_ELEMENT_FONT_SIZE_DETAIL)

    return font_size


def _required_boolean(field_name: str, flag_value: bool | None) -> bool:
    """Return a style flag. Null is rejected."""

    if flag_value is None:
        raise SkeletonElementError(f"{field_name} is required.")

    return flag_value


def _blank_to_none(text_value: str | None) -> str | None:
    """Strip text and store null when it is blank."""

    if text_value is None:

        return None

    stripped_text: str = text_value.strip()

    if stripped_text == "":

        return None

    return stripped_text


def _sort_order_key(element: SkeletonElement) -> int:
    """Return the current sort_order for an in-band sort."""

    return element.sort_order
