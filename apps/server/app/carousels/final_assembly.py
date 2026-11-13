"""Group live slides for Final assembly.

A group is an ordered pick that can be shown together and stays under
the slide-count cap. Draft slides are not passed in. This module does
not read the database, draw frames, parse instruction text, or call a
model.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.carousels.slide_exclusions import assert_slide_pick_allowed


def plan_final_groups(
    live_slide_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
    slide_count: int,
) -> list[list[uuid.UUID]]:
    """Group live slides under a size cap, skipping excluded pairs.

    Slides stay in the order they were given. A slide joins the first
    group that still has room and that ``assert_slide_pick_allowed``
    accepts with this slide added. Otherwise it starts the next group.
    A slide alone is always one group. Both directions of a pair may
    be present. ``slide_count`` is the cap already chosen, at least 1.

    Args:
        live_slide_ids: Approved slides, in the caller's order. Drafts
            are already left out.
        exclusion_pairs: ``(slide_id, excluded_slide_id)`` rows. Both
            directions may be present.
        slide_count: Maximum slides in one group.

    Returns:
        One list of slide ids per group. Empty when nothing is live.
    """

    groups: list[list[uuid.UUID]] = []

    for slide_id in live_slide_ids:
        placed_slide: bool = False

        for group in groups:
            group_has_room: bool = len(group) < slide_count

            if not group_has_room:
                continue

            candidate_ids: list[uuid.UUID] = [*group, slide_id]
            candidate_allowed: bool = _pick_is_allowed(candidate_ids, exclusion_pairs)

            if not candidate_allowed:
                continue

            group.append(slide_id)
            placed_slide = True

            break

        if placed_slide:
            continue

        assert_slide_pick_allowed([slide_id], exclusion_pairs)
        groups.append([slide_id])

    return groups


def _pick_is_allowed(
    slide_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> bool:
    """Return whether this pick contains no excluded pair."""

    try:
        assert_slide_pick_allowed(slide_ids, exclusion_pairs)
    except ValueError:

        return False

    return True
