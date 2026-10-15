"""Which units count as live.

Generated text is a draft until a person accepts it. A draft unit is
not live, even when an older approved value is still stored. This
module does not call a model or write rows.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.content_source import Unit
from app.models.enums import UnitTextStatus


def unit_counts_as_live(unit: Unit) -> bool:
    """Return true when this unit's text is approved.

    Args:
        unit: A unit on a source. A missing status counts as live, which
            is the state of rows saved before drafts existed.

    Returns:
        True for ``live``. False for ``draft``.
    """

    text_status: UnitTextStatus | None = unit.text_status

    if text_status is None:

        return True

    return text_status == UnitTextStatus.LIVE


def live_units(units: Sequence[Unit]) -> list[Unit]:
    """Return the units whose text is approved.

    Args:
        units: Units on one source, in any order.

    Returns:
        The live units, in the same order.
    """

    approved_units: list[Unit] = [
        unit for unit in units if unit_counts_as_live(unit)
    ]

    return approved_units
