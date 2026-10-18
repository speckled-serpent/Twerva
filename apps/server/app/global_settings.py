"""Built-in defaults that are not stored on a skeleton.

These are global settings in code. This phase does not add a settings
screen, and it does not add a slide-count column. A later phase uses
the slide-count default when it needs a count and the carousel has no
guidance. The hint on Slides names that default. It does not add or
remove slides. The done mark on Slides stays two slides.
"""

from __future__ import annotations

import random


SLIDE_COUNT_DEFAULT_LOW: int = 5
SLIDE_COUNT_DEFAULT_HIGH: int = 8


def slide_count_or_global_default(
    slide_count: int | None,
    picker: random.Random | None = None,
) -> int:
    """Return a set count, or a random value from 5 to 8 when none is set.

    The range is the global slide-count default. Per-skeleton overrides
    are later. Passing a count, including two, four, or nine, returns
    that count and does not draw. This does not write a slide.

    Args:
        slide_count: A count already chosen, or null when nothing is set.
        picker: Optional generator. The process random module is used
            when this is omitted.

    Returns:
        The set count, or an integer from 5 to 8 inclusive.
    """

    if slide_count is not None:

        return slide_count

    source: random.Random = random.SystemRandom() if picker is None else picker
    chosen_count: int = source.randint(
        SLIDE_COUNT_DEFAULT_LOW,
        SLIDE_COUNT_DEFAULT_HIGH,
    )

    return chosen_count
