"""SourceItem create/list/get routes."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_brand_by_id_or_raise, fetch_source_item_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import SourceItemCreateRequest, SourceItemReadResponse
from app.db import get_our_database_session
from app.models import SourceItem


source_items_router: APIRouter = APIRouter(
    prefix="/source-items",
    tags=["source-items"],
)


@source_items_router.post(
    "",
    response_model=SourceItemReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source_item(
    source_item_create_request: SourceItemCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> SourceItemReadResponse:
    """Persist a SourceItem under an existing Brand."""

    fetch_brand_by_id_or_raise(
        source_item_create_request.brand_id,
        our_database_session,
    )
    created_source_item: SourceItem = SourceItem(
        brand_id=source_item_create_request.brand_id,
        source_type=source_item_create_request.source_type,
        external_key=source_item_create_request.external_key,
        title=source_item_create_request.title,
        interest_heading=source_item_create_request.interest_heading,
        overview_bullets=source_item_create_request.overview_bullets,
        canonical_url=source_item_create_request.canonical_url,
        brand_kit_refs=source_item_create_request.brand_kit_refs,
        raw_payload=source_item_create_request.raw_payload,
    )
    our_database_session.add(created_source_item)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="SourceItem conflicts with an existing (brand, type, external_key).",
    )
    our_database_session.refresh(created_source_item)

    source_item_read_response: SourceItemReadResponse = (
        SourceItemReadResponse.model_validate(created_source_item)
    )

    return source_item_read_response


@source_items_router.get("", response_model=list[SourceItemReadResponse])
def list_source_items(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[SourceItemReadResponse]:
    """Return every SourceItem, newest first."""

    source_item_selection = select(SourceItem).order_by(SourceItem.created_at.desc())
    source_item_scalars = our_database_session.scalars(source_item_selection)
    source_items: list[SourceItem] = list(source_item_scalars.all())
    source_item_read_responses: list[SourceItemReadResponse] = [
        SourceItemReadResponse.model_validate(source_item)
        for source_item in source_items
    ]

    return source_item_read_responses


@source_items_router.get("/{source_item_id}", response_model=SourceItemReadResponse)
def get_source_item_by_id(
    source_item_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> SourceItemReadResponse:
    """Return one SourceItem by primary key."""

    found_source_item: SourceItem = fetch_source_item_by_id_or_raise(
        source_item_id,
        our_database_session,
    )
    source_item_read_response: SourceItemReadResponse = (
        SourceItemReadResponse.model_validate(found_source_item)
    )

    return source_item_read_response
