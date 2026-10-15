"""Read content sources, and register source and unit writes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.lookups import fetch_content_source_by_id_or_raise
from app.api.v1.source_preview import register_source_preview_routes
from app.api.v1.schemas import (
    SourceListItemResponse,
    SourceReadResponse,
    UnitElementTextReadResponse,
    UnitImageReadResponse,
    UnitReadResponse,
)
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit, UnitElementText, UnitImage


sources_router: APIRouter = APIRouter(prefix="/sources", tags=["sources"])


def content_sources_list_statement() -> Select[tuple[ContentSource]]:
    """Return every source, ordered by name.

    Returns:
        A select of sources with units loaded.
    """

    statement: Select[tuple[ContentSource]] = (
        select(ContentSource)
        .options(
            selectinload(ContentSource.units).selectinload(Unit.images),
            selectinload(ContentSource.units).selectinload(Unit.element_texts),
            selectinload(ContentSource.units).selectinload(Unit.exclusions),
        )
        .order_by(ContentSource.name.asc(), ContentSource.slug.asc())
    )

    return statement


@sources_router.get("", response_model=list[SourceListItemResponse])
def list_content_sources(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[SourceListItemResponse]:
    """Return sources. Readers may call this."""

    statement: Select[tuple[ContentSource]] = content_sources_list_statement()
    source_scalars = our_database_session.scalars(statement)
    sources: list[ContentSource] = list(source_scalars.all())
    list_items: list[SourceListItemResponse] = [
        serialize_content_source_list_item(source) for source in sources
    ]

    return list_items


@sources_router.get("/{source_id}", response_model=SourceReadResponse)
def get_content_source(
    source_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> SourceReadResponse:
    """Return one source and its units. A missing id is HTTP 404."""

    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    source_read_response: SourceReadResponse = serialize_content_source(found_source)

    return source_read_response


def serialize_content_source_list_item(source: ContentSource) -> SourceListItemResponse:
    """Return the list shape, with a count and no unit bodies."""

    list_item: SourceListItemResponse = SourceListItemResponse(
        id=source.id,
        theme_id=source.theme_id,
        name=source.name,
        slug=source.slug,
        unit_count=len(list(source.units)),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )

    return list_item


def serialize_content_source(source: ContentSource) -> SourceReadResponse:
    """Return one source with units, fields, and images in position order."""

    unit_responses: list[UnitReadResponse] = [
        serialize_unit(unit) for unit in _units_in_position_order(source)
    ]
    source_read_response: SourceReadResponse = SourceReadResponse(
        id=source.id,
        theme_id=source.theme_id,
        name=source.name,
        slug=source.slug,
        created_at=source.created_at,
        updated_at=source.updated_at,
        units=unit_responses,
    )

    return source_read_response


def _units_in_position_order(source: ContentSource) -> list[Unit]:
    """Return units sorted by position."""

    ordered_units: list[Unit] = sorted(list(source.units), key=_unit_position)

    return ordered_units


def _unit_position(unit: Unit) -> int:
    """Return the sort key for a unit."""

    position: int = unit.position

    return position


def serialize_unit(unit: Unit) -> UnitReadResponse:
    """Return one unit with theme text and images in position order."""

    text_responses: list[UnitElementTextReadResponse] = [
        _serialize_element_text(element_text) for element_text in list(unit.element_texts)
    ]
    excluded_unit_ids: list[uuid.UUID] = _excluded_unit_ids(unit)
    image_responses: list[UnitImageReadResponse] = [
        serialize_image(image) for image in _images_in_position_order(unit)
    ]
    unit_response: UnitReadResponse = UnitReadResponse(
        id=unit.id,
        position=unit.position,
        name=unit.name,
        texts=text_responses,
        excluded_unit_ids=excluded_unit_ids,
        images=image_responses,
    )

    return unit_response


def _serialize_element_text(element_text: UnitElementText) -> UnitElementTextReadResponse:
    """Return one stored theme-element value."""

    text_response: UnitElementTextReadResponse = UnitElementTextReadResponse(
        theme_element_id=element_text.theme_element_id,
        value=element_text.value,
    )

    return text_response


def _excluded_unit_ids(unit: Unit) -> list[uuid.UUID]:
    """Return the other unit ids this unit cannot be shown with."""

    excluded_ids: list[uuid.UUID] = sorted(
        (exclusion.excluded_unit_id for exclusion in list(unit.exclusions)),
        key=str,
    )

    return excluded_ids


def _images_in_position_order(unit: Unit) -> list[UnitImage]:
    """Return images sorted by position."""

    ordered_images: list[UnitImage] = sorted(list(unit.images), key=_image_position)

    return ordered_images


def _image_position(image: UnitImage) -> int:
    """Return the sort key for an image."""

    position: int = image.position

    return position


def serialize_image(image: UnitImage) -> UnitImageReadResponse:
    """Return one image, including license and the concrete path."""

    image_response: UnitImageReadResponse = UnitImageReadResponse(
        id=image.id,
        position=image.position,
        relative_path=image.relative_path,
        media_type=image.media_type,
        byte_size=image.byte_size,
        width=image.width,
        height=image.height,
        alt_text=image.alt_text,
        license=image.license,
        source=image.source,
        license_note=image.license_note,
        intake=image.intake,
        thumbnail_path=image.thumbnail_path,
    )

    return image_response


from app.api.v1.source_intake import register_source_intake_routes
from app.api.v1.source_writes import register_source_write_routes


register_source_write_routes(sources_router)
register_source_intake_routes(sources_router)
register_source_preview_routes(sources_router)
