"""Place live slides into carousels for one skeleton.

A carousel is an ordered pick of slides that can be shown together.
Draft slides are not passed in. Exclusion pairs split a pick. This
module does not call a model, write rows, or generate text.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.carousels.slide_exclusions import assert_slide_pick_allowed


def assemble_carousels(
    live_slide_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> list[list[uuid.UUID]]:
    """Group live slides so each carousel passes the exclusion check.

    Slides stay in the order they were given. A slide joins the first
    carousel that still allows the pair. Otherwise it starts the next
    carousel. A slide alone is always one carousel.

    Args:
        live_slide_ids: Approved slides, in carousel order. Drafts are
            already left out.
        exclusion_pairs: ``(slide_id, excluded_slide_id)`` rows. Both
            directions may be present.

    Returns:
        One list of slide ids per carousel. Empty when nothing is live.
    """

    carousels: list[list[uuid.UUID]] = []

    for slide_id in live_slide_ids:
        placed_slide: bool = False

        for carousel in carousels:
            candidate_ids: list[uuid.UUID] = [*carousel, slide_id]
            candidate_allowed: bool = _pick_is_allowed(candidate_ids, exclusion_pairs)

            if not candidate_allowed:
                continue

            carousel.append(slide_id)
            placed_slide = True

            break

        if placed_slide:
            continue

        assert_slide_pick_allowed([slide_id], exclusion_pairs)
        carousels.append([slide_id])

    return carousels


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
