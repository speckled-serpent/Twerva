"""Empty text slots when a skeleton gains a text element.

Removing a skeleton element already drops ``slide_element_texts`` through
the foreign key's ON DELETE CASCADE, including any ``draft_value`` on
those rows. This module is the other direction. A new text element
gets one empty row on every slide whose carousel uses that skeleton.

Draft copy is not a separate table. It is ``draft_value`` on the same
row, and only slides with ``text_status`` ``draft`` use it. A live slide
keeps ``draft_value`` null so it stays live. Image elements do not
get rows. Stored slide images are left alone.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import Row, Select, select
from sqlalchemy.engine import Result
from sqlalchemy.orm import Session

from app.models.carousel import Carousel, Slide, SlideElementText
from app.models.enums import SkeletonElementContentKind, SlideTextStatus
from app.models.skeleton_element import SkeletonElement
from app.carousels.editing import new_row_id


def sync_empty_texts_for_skeleton_element(
    skeleton_element: SkeletonElement,
    our_database_session: Session,
) -> None:
    """Insert an empty value for this text element on every bound slide.

    A slide that already stores the element is left as it is, including
    a non-empty live value or draft. Carousels on another skeleton are not
    touched. The caller commits.

    Args:
        skeleton_element: Element that was just flushed. Text only is stored.
        our_database_session: Open session.
    """

    if skeleton_element.content_kind != SkeletonElementContentKind.TEXT:

        return

    our_database_session.flush()
    bound_slides: list[tuple[uuid.UUID, SlideTextStatus]] = _slides_on_skeleton(
        skeleton_element.skeleton_id,
        our_database_session,
    )

    if len(bound_slides) == 0:

        return

    stored_slide_ids: set[uuid.UUID] = _slides_already_storing_element(
        skeleton_element.id,
        our_database_session,
    )
    inserted_row: bool = False

    for slide_id, text_status in bound_slides:

        if slide_id in stored_slide_ids:

            continue

        empty_text: SlideElementText = _empty_element_text(
            slide_id,
            skeleton_element.id,
            text_status,
        )
        our_database_session.add(empty_text)
        inserted_row = True

    if not inserted_row:

        return

    our_database_session.flush()


def _slides_on_skeleton(
    skeleton_id: uuid.UUID,
    our_database_session: Session,
) -> list[tuple[uuid.UUID, SlideTextStatus]]:
    """Return each slide on a carousel bound to ``skeleton_id``, with its status."""

    joined_slides: Select[tuple[uuid.UUID, SlideTextStatus]] = select(
        Slide.id,
        Slide.text_status,
    ).join(
        Carousel,
        Slide.carousel_id == Carousel.id,
    )
    slides_on_skeleton: Select[tuple[uuid.UUID, SlideTextStatus]] = joined_slides.where(
        Carousel.skeleton_id == skeleton_id,
    )
    slide_result: Result[tuple[uuid.UUID, SlideTextStatus]] = our_database_session.execute(
        slides_on_skeleton,
    )
    slide_rows: Sequence[Row[tuple[uuid.UUID, SlideTextStatus]]] = slide_result.all()
    bound_slides: list[tuple[uuid.UUID, SlideTextStatus]] = []

    for slide_row in slide_rows:
        slide_id: uuid.UUID = slide_row[0]
        text_status: SlideTextStatus = slide_row[1]
        bound_slides.append((slide_id, text_status))

    return bound_slides


def _slides_already_storing_element(
    skeleton_element_id: uuid.UUID,
    our_database_session: Session,
) -> set[uuid.UUID]:
    """Return slides that already have a row for this element."""

    stored_statement: Select[tuple[uuid.UUID]] = select(SlideElementText.slide_id)
    for_this_element: Select[tuple[uuid.UUID]] = stored_statement.where(
        SlideElementText.skeleton_element_id == skeleton_element_id,
    )
    stored_result: Result[tuple[uuid.UUID]] = our_database_session.execute(
        for_this_element,
    )
    stored_rows: Sequence[Row[tuple[uuid.UUID]]] = stored_result.all()
    stored_slide_ids: set[uuid.UUID] = set()

    for stored_row in stored_rows:
        stored_slide_id: uuid.UUID = stored_row[0]
        stored_slide_ids.add(stored_slide_id)

    return stored_slide_ids


def _empty_element_text(
    slide_id: uuid.UUID,
    skeleton_element_id: uuid.UUID,
    text_status: SlideTextStatus,
) -> SlideElementText:
    """Build one empty slot. Draft slides also get an empty draft string."""

    draft_value: str | None = None

    if text_status == SlideTextStatus.DRAFT:
        draft_value = ""

    empty_text: SlideElementText = SlideElementText(
        id=new_row_id(),
        slide_id=slide_id,
        skeleton_element_id=skeleton_element_id,
        value="",
        draft_value=draft_value,
    )

    return empty_text
