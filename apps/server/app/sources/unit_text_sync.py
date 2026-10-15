"""Empty text slots when a theme gains a text element.

Removing a theme element already drops ``unit_element_texts`` through
the foreign key's ON DELETE CASCADE, including any ``draft_value`` on
those rows. This module is the other direction. A new text element
gets one empty row on every unit whose source uses that theme.

Draft copy is not a separate table. It is ``draft_value`` on the same
row, and only units with ``text_status`` ``draft`` use it. A live unit
keeps ``draft_value`` null so it stays live. Image elements do not
get rows. Stored unit images are left alone.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import Row, Select, select
from sqlalchemy.engine import Result
from sqlalchemy.orm import Session

from app.models.content_source import ContentSource, Unit, UnitElementText
from app.models.enums import ThemeElementContentKind, UnitTextStatus
from app.models.theme_element import ThemeElement
from app.sources.editing import new_row_id


def sync_empty_texts_for_theme_element(
    theme_element: ThemeElement,
    our_database_session: Session,
) -> None:
    """Insert an empty value for this text element on every bound unit.

    A unit that already stores the element is left as it is, including
    a non-empty live value or draft. Sources on another theme are not
    touched. The caller commits.

    Args:
        theme_element: Element that was just flushed. Text only is stored.
        our_database_session: Open session.
    """

    if theme_element.content_kind != ThemeElementContentKind.TEXT:

        return

    our_database_session.flush()
    bound_units: list[tuple[uuid.UUID, UnitTextStatus]] = _units_on_theme(
        theme_element.theme_id,
        our_database_session,
    )

    if len(bound_units) == 0:

        return

    stored_unit_ids: set[uuid.UUID] = _units_already_storing_element(
        theme_element.id,
        our_database_session,
    )
    inserted_row: bool = False

    for unit_id, text_status in bound_units:

        if unit_id in stored_unit_ids:

            continue

        empty_text: UnitElementText = _empty_element_text(
            unit_id,
            theme_element.id,
            text_status,
        )
        our_database_session.add(empty_text)
        inserted_row = True

    if not inserted_row:

        return

    our_database_session.flush()


def _units_on_theme(
    theme_id: uuid.UUID,
    our_database_session: Session,
) -> list[tuple[uuid.UUID, UnitTextStatus]]:
    """Return each unit on a source bound to ``theme_id``, with its status."""

    joined_units: Select[tuple[uuid.UUID, UnitTextStatus]] = select(
        Unit.id,
        Unit.text_status,
    ).join(
        ContentSource,
        Unit.source_id == ContentSource.id,
    )
    units_on_theme: Select[tuple[uuid.UUID, UnitTextStatus]] = joined_units.where(
        ContentSource.theme_id == theme_id,
    )
    unit_result: Result[tuple[uuid.UUID, UnitTextStatus]] = our_database_session.execute(
        units_on_theme,
    )
    unit_rows: Sequence[Row[tuple[uuid.UUID, UnitTextStatus]]] = unit_result.all()
    bound_units: list[tuple[uuid.UUID, UnitTextStatus]] = []

    for unit_row in unit_rows:
        unit_id: uuid.UUID = unit_row[0]
        text_status: UnitTextStatus = unit_row[1]
        bound_units.append((unit_id, text_status))

    return bound_units


def _units_already_storing_element(
    theme_element_id: uuid.UUID,
    our_database_session: Session,
) -> set[uuid.UUID]:
    """Return units that already have a row for this element."""

    stored_statement: Select[tuple[uuid.UUID]] = select(UnitElementText.unit_id)
    for_this_element: Select[tuple[uuid.UUID]] = stored_statement.where(
        UnitElementText.theme_element_id == theme_element_id,
    )
    stored_result: Result[tuple[uuid.UUID]] = our_database_session.execute(
        for_this_element,
    )
    stored_rows: Sequence[Row[tuple[uuid.UUID]]] = stored_result.all()
    stored_unit_ids: set[uuid.UUID] = set()

    for stored_row in stored_rows:
        stored_unit_id: uuid.UUID = stored_row[0]
        stored_unit_ids.add(stored_unit_id)

    return stored_unit_ids


def _empty_element_text(
    unit_id: uuid.UUID,
    theme_element_id: uuid.UUID,
    text_status: UnitTextStatus,
) -> UnitElementText:
    """Build one empty slot. Draft units also get an empty draft string."""

    draft_value: str | None = None

    if text_status == UnitTextStatus.DRAFT:
        draft_value = ""

    empty_text: UnitElementText = UnitElementText(
        id=new_row_id(),
        unit_id=unit_id,
        theme_element_id=theme_element_id,
        value="",
        draft_value=draft_value,
    )

    return empty_text
