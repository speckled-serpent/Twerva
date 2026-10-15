"""Place live units into carousels for one theme.

A carousel is an ordered pick of units that can be shown together.
Draft units are not passed in. Exclusion pairs split a pick. This
module does not call a model, write rows, or generate text.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.sources.unit_exclusions import assert_unit_pick_allowed


def assemble_carousels(
    live_unit_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> list[list[uuid.UUID]]:
    """Group live units so each carousel passes the exclusion check.

    Units stay in the order they were given. A unit joins the first
    carousel that still allows the pair. Otherwise it starts the next
    carousel. A unit alone is always one carousel.

    Args:
        live_unit_ids: Approved units, in source order. Drafts are
            already left out.
        exclusion_pairs: ``(unit_id, excluded_unit_id)`` rows. Both
            directions may be present.

    Returns:
        One list of unit ids per carousel. Empty when nothing is live.
    """

    carousels: list[list[uuid.UUID]] = []

    for unit_id in live_unit_ids:
        placed_unit: bool = False

        for carousel in carousels:
            candidate_ids: list[uuid.UUID] = [*carousel, unit_id]
            candidate_allowed: bool = _pick_is_allowed(candidate_ids, exclusion_pairs)

            if not candidate_allowed:
                continue

            carousel.append(unit_id)
            placed_unit = True

            break

        if placed_unit:
            continue

        assert_unit_pick_allowed([unit_id], exclusion_pairs)
        carousels.append([unit_id])

    return carousels


def _pick_is_allowed(
    unit_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> bool:
    """Return whether this pick contains no excluded pair."""

    try:
        assert_unit_pick_allowed(unit_ids, exclusion_pairs)
    except ValueError:

        return False

    return True
