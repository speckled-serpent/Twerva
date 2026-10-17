"""Which slides in one carousel cannot be shown together.

A slide stores the other slide ids it excludes. The pair is symmetric:
if either slide names the other, a pick that contains both is refused.
This module does not read the database or write rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence


SELF_EXCLUSION_DETAIL: str = "A slide cannot exclude itself."
UNKNOWN_EXCLUSION_DETAIL: str = "That slide is not in this carousel."
DUPLICATE_EXCLUSION_DETAIL: str = "Each excluded slide is stored once."
EXCLUDED_PAIR_DETAIL: str = "That pick includes slides that cannot be shown together."


def normalized_exclusion_ids(
    slide_id: uuid.UUID,
    submitted_ids: Sequence[uuid.UUID],
    sibling_ids: set[uuid.UUID],
) -> list[uuid.UUID]:
    """Keep one other slide id per exclusion. Self and outsiders are rejected.

    Args:
        slide_id: The slide whose list is being saved.
        submitted_ids: Ids from the request, in request order.
        sibling_ids: Other slides on the same carousel.

    Returns:
        The ids to store, in request order.

    Raises:
        ValueError: The slide names itself, names a slide outside the
            carousel, or names the same slide twice.
    """

    seen_ids: set[uuid.UUID] = set()
    stored_ids: list[uuid.UUID] = []

    for excluded_id in submitted_ids:

        if excluded_id == slide_id:
            raise ValueError(SELF_EXCLUSION_DETAIL)

        if excluded_id not in sibling_ids:
            raise ValueError(UNKNOWN_EXCLUSION_DETAIL)

        if excluded_id in seen_ids:
            raise ValueError(DUPLICATE_EXCLUSION_DETAIL)

        seen_ids.add(excluded_id)
        stored_ids.append(excluded_id)

    return stored_ids


def assert_slide_pick_allowed(
    slide_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """Refuse a pick that contains an excluded pair.

    Either direction of a pair counts. A slide id that is not in the
    pick is ignored. Duplicate ids in the pick count once. A pick of
    slides that do not exclude each other is allowed.

    Args:
        slide_ids: Slides the pick would show together.
        exclusion_pairs: ``(slide_id, excluded_slide_id)`` rows. Both
            directions may be present.

    Raises:
        ValueError: Two picked slides exclude each other.
    """

    picked_ids: set[uuid.UUID] = set(slide_ids)

    for slide_id, excluded_slide_id in exclusion_pairs:

        if slide_id in picked_ids and excluded_slide_id in picked_ids:
            raise ValueError(EXCLUDED_PAIR_DETAIL)
