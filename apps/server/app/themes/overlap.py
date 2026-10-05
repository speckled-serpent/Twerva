"""Flag band overlaps after a frame is placed.

Rectangles from different bands overlap when their areas intersect.
Sharing an edge is not an overlap. Same-band stacks are not compared.
Coordinates are left as placement set them. This module does not draw,
write previews, or create artifacts.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.enums import ThemeElementBand


_BAND_RANK: dict[ThemeElementBand, int] = {
    ThemeElementBand.TOP: 0,
    ThemeElementBand.MIDDLE: 1,
    ThemeElementBand.BOTTOM: 2,
}


@dataclass(frozen=True)
class PlacedElement:
    """One rectangle after placement, tagged with its band."""

    element_id: uuid.UUID
    band: ThemeElementBand
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class BandOverlap:
    """One pair of elements from different bands whose areas intersect."""

    band_a: ThemeElementBand
    band_b: ThemeElementBand
    element_ids: tuple[uuid.UUID, uuid.UUID]


@dataclass(frozen=True)
class InstanceOverlap:
    """Overlap result for one concrete frame. ``blocked`` is per instance."""

    blocked: bool
    overlaps: tuple[BandOverlap, ...]


def find_band_overlaps(
    instances: Sequence[Sequence[PlacedElement]],
) -> tuple[InstanceOverlap, ...]:
    """Return one overlap result per instance. Coordinates are not changed.

    Only rectangles from different bands are compared. Their areas
    intersect when the overlap width and height are both greater than
    zero. A shared edge has zero overlap on that axis and is allowed.
    A same-band stack, including gap zero, is not an overlap. An
    instance with no elements is not blocked.

    Args:
        instances: Placed frames. Each frame is the rectangles for one
            source instance. The sequence order is the result order.

    Returns:
        ``blocked`` and the intersecting pairs for each instance. ``band_a``
        is the earlier band (top, then middle, then bottom).
    """

    instance_results: list[InstanceOverlap] = []

    for placed_elements in instances:
        overlaps: tuple[BandOverlap, ...] = _overlaps_in_instance(placed_elements)
        blocked: bool = len(overlaps) > 0
        instance_results.append(
            InstanceOverlap(blocked=blocked, overlaps=overlaps),
        )

    return tuple(instance_results)


def _overlaps_in_instance(
    placed_elements: Sequence[PlacedElement],
) -> tuple[BandOverlap, ...]:
    """Pair rectangles from different bands and keep strict area hits."""

    found_overlaps: list[BandOverlap] = []
    placed_count: int = len(placed_elements)

    for left_index in range(placed_count):
        left_element: PlacedElement = placed_elements[left_index]

        for right_index in range(left_index + 1, placed_count):
            right_element: PlacedElement = placed_elements[right_index]

            if left_element.band == right_element.band:

                continue

            if not _areas_intersect(left_element, right_element):

                continue

            found_overlaps.append(_ordered_overlap(left_element, right_element))

    found_overlaps.sort(key=_overlap_sort_key)

    return tuple(found_overlaps)


def _areas_intersect(left_element: PlacedElement, right_element: PlacedElement) -> bool:
    """True when the rectangles share a positive area. A shared edge does not."""

    overlap_width: int = _axis_overlap(
        left_element.x,
        left_element.width,
        right_element.x,
        right_element.width,
    )
    overlap_height: int = _axis_overlap(
        left_element.y,
        left_element.height,
        right_element.y,
        right_element.height,
    )

    return overlap_width > 0 and overlap_height > 0


def _axis_overlap(origin_a: int, span_a: int, origin_b: int, span_b: int) -> int:
    """Return the shared length on one axis. Zero means the edges only touch."""

    end_a: int = origin_a + span_a
    end_b: int = origin_b + span_b
    shared_start: int = max(origin_a, origin_b)
    shared_end: int = min(end_a, end_b)
    shared_length: int = shared_end - shared_start

    return shared_length


def _ordered_overlap(left_element: PlacedElement, right_element: PlacedElement) -> BandOverlap:
    """Put the earlier band first and list its element id first."""

    earlier_element: PlacedElement = left_element
    later_element: PlacedElement = right_element

    if _BAND_RANK[right_element.band] < _BAND_RANK[left_element.band]:

        earlier_element = right_element
        later_element = left_element

    return BandOverlap(
        band_a=earlier_element.band,
        band_b=later_element.band,
        element_ids=(earlier_element.element_id, later_element.element_id),
    )


def _overlap_sort_key(overlap: BandOverlap) -> tuple[int, int, str, str]:
    """Stable order: band pair, then element ids."""

    return (
        _BAND_RANK[overlap.band_a],
        _BAND_RANK[overlap.band_b],
        str(overlap.element_ids[0]),
        str(overlap.element_ids[1]),
    )
