"""Which slides count as live.

Generated text is a draft until a person accepts it. A draft slide is
not live, even when an older approved value is still stored. This
module does not call a model or write rows.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.carousel import Slide
from app.models.enums import SlideTextStatus


def slide_counts_as_live(slide: Slide) -> bool:
    """Return true when this slide's text is approved.

    Args:
        slide: A slide on a carousel. A missing status counts as live, which
            is the state of rows saved before drafts existed.

    Returns:
        True for ``live``. False for ``draft``.
    """

    text_status: SlideTextStatus | None = slide.text_status

    if text_status is None:

        return True

    return text_status == SlideTextStatus.LIVE


def live_slides(slides: Sequence[Slide]) -> list[Slide]:
    """Return the slides whose text is approved.

    Args:
        slides: Slides on one carousel, in any order.

    Returns:
        The live slides, in the same order.
    """

    approved_slides: list[Slide] = [
        slide for slide in slides if slide_counts_as_live(slide)
    ]

    return approved_slides
