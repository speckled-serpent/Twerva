"""Brand create/list/get routes."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_brand_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import BrandCreateRequest, BrandReadResponse
from app.db import get_our_database_session
from app.models import Brand


brands_router: APIRouter = APIRouter(prefix="/brands", tags=["brands"])


@brands_router.post(
    "",
    response_model=BrandReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_brand(
    brand_create_request: BrandCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> BrandReadResponse:
    """Persist a Brand and return the stored row."""

    created_brand: Brand = Brand(
        slug=brand_create_request.slug,
        name=brand_create_request.name,
        notes=brand_create_request.notes,
        voice_notes=brand_create_request.voice_notes,
    )
    our_database_session.add(created_brand)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Brand slug already exists.",
    )
    our_database_session.refresh(created_brand)

    brand_read_response: BrandReadResponse = BrandReadResponse.model_validate(
        created_brand,
    )

    return brand_read_response


@brands_router.get("", response_model=list[BrandReadResponse])
def list_brands(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[BrandReadResponse]:
    """Return every Brand, newest first."""

    brand_selection = select(Brand).order_by(Brand.created_at.desc())
    brand_scalars = our_database_session.scalars(brand_selection)
    brands: list[Brand] = list(brand_scalars.all())
    brand_read_responses: list[BrandReadResponse] = [
        BrandReadResponse.model_validate(brand) for brand in brands
    ]

    return brand_read_responses


@brands_router.get("/{brand_id}", response_model=BrandReadResponse)
def get_brand_by_id(
    brand_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> BrandReadResponse:
    """Return one Brand by primary key."""

    found_brand: Brand = fetch_brand_by_id_or_raise(brand_id, our_database_session)
    brand_read_response: BrandReadResponse = BrandReadResponse.model_validate(
        found_brand,
    )

    return brand_read_response
