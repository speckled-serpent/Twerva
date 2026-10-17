"""Place skeleton elements on the 1080×1920 carousel frame.

Bands are independent. Top stacks downward from the top page margin,
bottom stacks upward from the bottom page margin, and middle is one
centered block. This module does not measure text, read images, or
decide overlap.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.enums import SkeletonElementBand


SKELETON_FRAME_WIDTH_PIXELS: int = 1080
SKELETON_FRAME_HEIGHT_PIXELS: int = 1920


@dataclass(frozen=True)
class LayoutElement:
    """One element that already has a content height.

    ``sort_order`` is 0-based within ``band``. The lowest value is the
    first element: the topmost in Top, the lowest in Bottom, and the
    first of the Middle block.
    """

    element_id: uuid.UUID
    band: SkeletonElementBand
    sort_order: int
    content_height: int


@dataclass(frozen=True)
class ContentArea:
    """Frame inset by ``page_margin`` on every edge."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class LayoutRectangle:
    """Integer element rectangle. ``height`` includes element margin."""

    element_id: uuid.UUID
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SkeletonLayout:
    """Content area plus one rectangle per element. Empty input has no rectangles."""

    content_area: ContentArea
    rectangles: tuple[LayoutRectangle, ...]


def place_skeleton_elements(
    frame_width: int,
    frame_height: int,
    page_margin: int,
    element_gap: int,
    element_margin: int,
    elements: Sequence[LayoutElement],
) -> SkeletonLayout:
    """Place elements that already have a content height.

    The content area is the frame inset by ``page_margin`` on every
    edge. Every element uses that left edge and that width. Element
    height is the content height plus ``element_margin`` above and
    below. ``element_gap`` sits between rectangles in the same band
    only.

    Top starts ``page_margin`` down from the frame top and stacks
    downward. Bottom's first element is the lowest; its bottom is
    ``page_margin`` up from the frame bottom, and later elements stack
    upward. Middle is one block (heights plus the gaps between them)
    whose top is ``content_top + floor((content_height - block_height) / 2)``,
    so an odd leftover pixel sits below the block.

    An empty band adds no rectangles. Zero elements is valid.

    Args:
        frame_width: Frame width in pixels. Carousel skeletons use 1080.
        frame_height: Frame height in pixels. Carousel skeletons use 1920.
        page_margin: Inset applied on every edge of the frame.
        element_gap: Space between rectangles in the same band.
        element_margin: Space between content and each edge of the rectangle.
        elements: Elements grouped by band and ``sort_order``, each with
            a content height. The sequence order is not the stack order.

    Returns:
        The content area and integer rectangles in band order (top,
        middle, bottom), then ``sort_order`` within the band.
    """

    content_area: ContentArea = _content_area(frame_width, frame_height, page_margin)
    top_elements: tuple[LayoutElement, ...] = _elements_in_band(
        elements,
        SkeletonElementBand.TOP,
    )
    middle_elements: tuple[LayoutElement, ...] = _elements_in_band(
        elements,
        SkeletonElementBand.MIDDLE,
    )
    bottom_elements: tuple[LayoutElement, ...] = _elements_in_band(
        elements,
        SkeletonElementBand.BOTTOM,
    )
    top_rectangles: tuple[LayoutRectangle, ...] = _stack_downward(
        top_elements,
        page_margin,
        element_gap,
        element_margin,
        content_area.x,
        content_area.width,
    )
    middle_rectangles: tuple[LayoutRectangle, ...] = _place_middle_band(
        middle_elements,
        content_area,
        element_gap,
        element_margin,
    )
    bottom_edge: int = frame_height - page_margin
    bottom_rectangles: tuple[LayoutRectangle, ...] = _stack_upward(
        bottom_elements,
        bottom_edge,
        element_gap,
        element_margin,
        content_area.x,
        content_area.width,
    )
    rectangles: tuple[LayoutRectangle, ...] = (
        top_rectangles + middle_rectangles + bottom_rectangles
    )

    return SkeletonLayout(content_area=content_area, rectangles=rectangles)


def _content_area(frame_width: int, frame_height: int, page_margin: int) -> ContentArea:
    """Return the frame inset by ``page_margin`` on every edge."""

    horizontal_inset: int = page_margin + page_margin
    vertical_inset: int = page_margin + page_margin
    content_width: int = frame_width - horizontal_inset
    content_height: int = frame_height - vertical_inset

    return ContentArea(
        x=page_margin,
        y=page_margin,
        width=content_width,
        height=content_height,
    )


def _element_rectangle_height(content_height: int, element_margin: int) -> int:
    """Return content height plus element margin above and below."""

    vertical_margin: int = element_margin + element_margin
    rectangle_height: int = content_height + vertical_margin

    return rectangle_height


def _sort_order_of(element: LayoutElement) -> int:
    """Return the order used to stack this element inside its band."""

    return element.sort_order


def _elements_in_band(
    elements: Sequence[LayoutElement],
    band: SkeletonElementBand,
) -> tuple[LayoutElement, ...]:
    """Return ``band`` members, lowest ``sort_order`` first.

    Args:
        elements: Elements for every band.
        band: Band to collect.

    Returns:
        An empty tuple when the band has no elements.
    """

    matching_elements: list[LayoutElement] = [
        element
        for element in elements
        if element.band == band
    ]
    ordered_elements: list[LayoutElement] = sorted(matching_elements, key=_sort_order_of)

    return tuple(ordered_elements)


def _stack_downward(
    elements: Sequence[LayoutElement],
    origin_y: int,
    element_gap: int,
    element_margin: int,
    x: int,
    width: int,
) -> tuple[LayoutRectangle, ...]:
    """Stack ``elements`` downward. Gap sits between rectangles only."""

    placed_rectangles: list[LayoutRectangle] = []
    cursor_y: int = origin_y

    for index, element in enumerate(elements):

        if index > 0:

            cursor_y = cursor_y + element_gap

        rectangle_height: int = _element_rectangle_height(
            element.content_height,
            element_margin,
        )
        rectangle: LayoutRectangle = LayoutRectangle(
            element_id=element.element_id,
            x=x,
            y=cursor_y,
            width=width,
            height=rectangle_height,
        )
        placed_rectangles.append(rectangle)
        cursor_y = cursor_y + rectangle_height

    return tuple(placed_rectangles)


def _stack_upward(
    elements: Sequence[LayoutElement],
    bottom_edge: int,
    element_gap: int,
    element_margin: int,
    x: int,
    width: int,
) -> tuple[LayoutRectangle, ...]:
    """Stack ``elements`` upward. The first element is the lowest."""

    placed_rectangles: list[LayoutRectangle] = []
    cursor_bottom: int = bottom_edge

    for index, element in enumerate(elements):

        if index > 0:

            cursor_bottom = cursor_bottom - element_gap

        rectangle_height: int = _element_rectangle_height(
            element.content_height,
            element_margin,
        )
        rectangle_y: int = cursor_bottom - rectangle_height
        rectangle: LayoutRectangle = LayoutRectangle(
            element_id=element.element_id,
            x=x,
            y=rectangle_y,
            width=width,
            height=rectangle_height,
        )
        placed_rectangles.append(rectangle)
        cursor_bottom = rectangle_y

    return tuple(placed_rectangles)


def _place_middle_band(
    elements: Sequence[LayoutElement],
    content_area: ContentArea,
    element_gap: int,
    element_margin: int,
) -> tuple[LayoutRectangle, ...]:
    """Center the whole middle block in the content area."""

    element_count: int = len(elements)

    if element_count == 0:

        empty_rectangles: tuple[LayoutRectangle, ...] = ()

        return empty_rectangles

    rectangle_heights: list[int] = [
        _element_rectangle_height(element.content_height, element_margin)
        for element in elements
    ]
    height_total: int = sum(rectangle_heights)
    gap_count: int = element_count - 1
    gap_total: int = element_gap * gap_count
    block_height: int = height_total + gap_total
    leftover_pixels: int = content_area.height - block_height
    offset_pixels: int = leftover_pixels // 2
    block_top: int = content_area.y + offset_pixels

    return _stack_downward(
        elements,
        block_top,
        element_gap,
        element_margin,
        content_area.x,
        content_area.width,
    )
