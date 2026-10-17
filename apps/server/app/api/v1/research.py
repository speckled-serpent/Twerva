"""Research list, create, autosave, and delete.

One row is one document. The body is text stored on the row. There is
no upload and no carousel link.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    ResearchCreateRequest,
    ResearchListItemResponse,
    ResearchPatchRequest,
    ResearchReadResponse,
)
from app.auth.dependencies import require_admin_ops_operator
from app.carousels.editing import (
    allocate_unique_source_slug,
    new_row_id,
    slugify_carousel_name,
)
from app.db import get_our_database_session
from app.models.ops_user import OpsUser
from app.models.research_item import (
    RESEARCH_BODY_MAX_CHARACTERS,
    RESEARCH_SLUG_FALLBACK,
    ResearchItem,
    count_research_words,
)


research_router: APIRouter = APIRouter(prefix="/research", tags=["research"])

TITLE_REQUIRED_DETAIL: str = "Title is required."
BODY_TOO_LONG_DETAIL: str = (
    f"Research body must be {RESEARCH_BODY_MAX_CHARACTERS:,} characters or fewer."
)
BODY_NOT_TEXT_DETAIL: str = "Research body must be plain text."


def research_list_statement() -> Select[tuple[ResearchItem]]:
    """Return every research item, ordered by title."""

    statement: Select[tuple[ResearchItem]] = (
        select(ResearchItem)
        .order_by(ResearchItem.title.asc(), ResearchItem.slug.asc())
    )

    return statement


@research_router.get("", response_model=list[ResearchListItemResponse])
def list_research(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[ResearchListItemResponse]:
    """Return research items. Readers may call this."""

    research_items: list[ResearchItem] = list(
        our_database_session.scalars(research_list_statement()).all(),
    )
    list_items: list[ResearchListItemResponse] = [
        serialize_research_list_item(research_item) for research_item in research_items
    ]

    return list_items


@research_router.post(
    "",
    response_model=ResearchReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_research(
    research_create_request: ResearchCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> ResearchReadResponse:
    """Create an empty document. Readers cannot call this."""

    _ = current_ops_operator
    research_title: str = _require_title(research_create_request.title)
    created_item: ResearchItem = _new_research_item(research_title, our_database_session)
    our_database_session.add(created_item)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Research could not be saved.",
    )
    our_database_session.refresh(created_item)

    return serialize_research(created_item)


@research_router.get("/{research_id}", response_model=ResearchReadResponse)
def get_research(
    research_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ResearchReadResponse:
    """Return one document. A missing id is HTTP 404."""

    found_item: ResearchItem = _fetch_research_or_raise(research_id, our_database_session)

    return serialize_research(found_item)


@research_router.patch("/{research_id}", response_model=ResearchReadResponse)
def patch_research(
    research_id: uuid.UUID,
    research_patch_request: ResearchPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> ResearchReadResponse:
    """Save the title and body. The slug stays. Readers cannot call this."""

    _ = current_ops_operator
    found_item: ResearchItem = _fetch_research_or_raise(research_id, our_database_session)
    found_item.title = _require_title(research_patch_request.title)
    found_item.body = _require_body(research_patch_request.body)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Research could not be saved.",
    )
    our_database_session.refresh(found_item)

    return serialize_research(found_item)


@research_router.delete("/{research_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research(
    research_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete one document. Readers cannot call this."""

    _ = current_ops_operator
    found_item: ResearchItem = _fetch_research_or_raise(research_id, our_database_session)
    our_database_session.delete(found_item)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Research could not be deleted.",
    )


def serialize_research_list_item(research_item: ResearchItem) -> ResearchListItemResponse:
    """Return the list shape. The body stays off this response."""

    list_item: ResearchListItemResponse = ResearchListItemResponse(
        id=research_item.id,
        title=research_item.title,
        slug=research_item.slug,
        word_count=count_research_words(research_item.body),
        character_count=len(research_item.body),
        created_at=research_item.created_at,
        updated_at=research_item.updated_at,
    )

    return list_item


def serialize_research(research_item: ResearchItem) -> ResearchReadResponse:
    """Return one document, including the body and the counts."""

    research_response: ResearchReadResponse = ResearchReadResponse(
        id=research_item.id,
        title=research_item.title,
        slug=research_item.slug,
        body=research_item.body,
        word_count=count_research_words(research_item.body),
        character_count=len(research_item.body),
        created_at=research_item.created_at,
        updated_at=research_item.updated_at,
    )

    return research_response


def _new_research_item(research_title: str, our_database_session: Session) -> ResearchItem:
    """Build an empty document. The slug comes from the title."""

    taken_slugs: set[str] = set(
        our_database_session.scalars(select(ResearchItem.slug)).all(),
    )
    research_slug: str = allocate_unique_source_slug(
        slugify_carousel_name(research_title, RESEARCH_SLUG_FALLBACK),
        taken_slugs,
    )
    created_item: ResearchItem = ResearchItem(
        id=new_row_id(),
        title=research_title,
        slug=research_slug,
        body="",
    )

    return created_item


def _require_title(raw_title: str) -> str:
    """Return a stripped title, or 400 when it is blank."""

    research_title: str = raw_title.strip()

    if research_title == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=TITLE_REQUIRED_DETAIL,
        )

    return research_title


def _require_body(raw_body: str) -> str:
    """Return the body unchanged, or 400 when it is not plain text."""

    if "\x00" in raw_body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=BODY_NOT_TEXT_DETAIL,
        )

    if len(raw_body) > RESEARCH_BODY_MAX_CHARACTERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=BODY_TOO_LONG_DETAIL,
        )

    return raw_body


def _fetch_research_or_raise(
    research_id: uuid.UUID,
    our_database_session: Session,
) -> ResearchItem:
    """Return a document, or 404."""

    found_item: ResearchItem | None = our_database_session.get(ResearchItem, research_id)

    if found_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research not found: {research_id}",
        )

    return found_item
