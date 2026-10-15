"""Which units in one source cannot be shown together.

A unit stores the other unit ids it excludes. The pair is symmetric:
if either unit names the other, a pick that contains both is refused.
This module does not read the database or write rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence


SELF_EXCLUSION_DETAIL: str = "A unit cannot exclude itself."
UNKNOWN_EXCLUSION_DETAIL: str = "That unit is not in this source."
DUPLICATE_EXCLUSION_DETAIL: str = "Each excluded unit is stored once."
EXCLUDED_PAIR_DETAIL: str = "That pick includes units that cannot be shown together."


def normalized_exclusion_ids(
    unit_id: uuid.UUID,
    submitted_ids: Sequence[uuid.UUID],
    sibling_ids: set[uuid.UUID],
) -> list[uuid.UUID]:
    """Keep one other unit id per exclusion. Self and outsiders are rejected.

    Args:
        unit_id: The unit whose list is being saved.
        submitted_ids: Ids from the request, in request order.
        sibling_ids: Other units on the same source.

    Returns:
        The ids to store, in request order.

    Raises:
        ValueError: The unit names itself, names a unit outside the
            source, or names the same unit twice.
    """

    seen_ids: set[uuid.UUID] = set()
    stored_ids: list[uuid.UUID] = []

    for excluded_id in submitted_ids:

        if excluded_id == unit_id:
            raise ValueError(SELF_EXCLUSION_DETAIL)

        if excluded_id not in sibling_ids:
            raise ValueError(UNKNOWN_EXCLUSION_DETAIL)

        if excluded_id in seen_ids:
            raise ValueError(DUPLICATE_EXCLUSION_DETAIL)

        seen_ids.add(excluded_id)
        stored_ids.append(excluded_id)

    return stored_ids


def assert_unit_pick_allowed(
    unit_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """Refuse a pick that contains an excluded pair.

    Either direction of a pair counts. A unit id that is not in the
    pick is ignored. Duplicate ids in the pick count once. A pick of
    units that do not exclude each other is allowed.

    Args:
        unit_ids: Units the pick would show together.
        exclusion_pairs: ``(unit_id, excluded_unit_id)`` rows. Both
            directions may be present.

    Raises:
        ValueError: Two picked units exclude each other.
    """

    picked_ids: set[uuid.UUID] = set(unit_ids)

    for unit_id, excluded_unit_id in exclusion_pairs:

        if unit_id in picked_ids and excluded_unit_id in picked_ids:
            raise ValueError(EXCLUDED_PAIR_DETAIL)
