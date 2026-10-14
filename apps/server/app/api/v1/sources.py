"""Read content sources, and register album and unit writes."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.lookups import fetch_content_source_by_id_or_raise
from app.api.v1.schemas import (
    ResourceFileReadResponse,
    SourceListItemResponse,
    SourceReadResponse,
    UnitFieldReadResponse,
    UnitImageReadResponse,
    UnitReadResponse,
)
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit, UnitField, UnitImage
from app.models.enums import ContentSourceKind


sources_router: APIRouter = APIRouter(prefix="/sources", tags=["sources"])


def content_sources_list_statement(
    kind: ContentSourceKind | None,
) -> Select[tuple[ContentSource]]:
    """Return the list query, optionally limited to one kind.

    Args:
        kind: Album or resource. Null lists every source.

    Returns:
        A select of sources ordered by name, with units loaded.
    """

    statement: Select[tuple[ContentSource]] = (
        select(ContentSource)
        .options(
            selectinload(ContentSource.units).selectinload(Unit.images),
            selectinload(ContentSource.units).selectinload(Unit.fields),
        )
        .order_by(ContentSource.name.asc(), ContentSource.slug.asc())
    )

    if kind is not None:
        statement = statement.where(ContentSource.kind == kind)

    return statement


@sources_router.get("", response_model=list[SourceListItemResponse])
def list_content_sources(
    kind: ContentSourceKind | None = None,
    our_database_session: Session = Depends(get_our_database_session),
) -> list[SourceListItemResponse]:
    """Return sources. Readers may call this. ``kind`` filters the list."""

    statement: Select[tuple[ContentSource]] = content_sources_list_statement(kind)
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
        kind=source.kind,
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
        kind=source.kind,
        name=source.name,
        slug=source.slug,
        created_at=source.created_at,
        updated_at=source.updated_at,
        units=unit_responses,
        resource=_serialize_resource_file(source),
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
    """Return one unit with fields and images in position order."""

    field_responses: list[UnitFieldReadResponse] = [
        _serialize_field(field) for field in _fields_in_position_order(unit)
    ]
    image_responses: list[UnitImageReadResponse] = [
        serialize_image(image) for image in _images_in_position_order(unit)
    ]
    unit_response: UnitReadResponse = UnitReadResponse(
        id=unit.id,
        position=unit.position,
        free_text=unit.free_text,
        tags=list(unit.tags),
        fields=field_responses,
        images=image_responses,
    )

    return unit_response


def _fields_in_position_order(unit: Unit) -> list[UnitField]:
    """Return fields sorted by position."""

    ordered_fields: list[UnitField] = sorted(list(unit.fields), key=_field_position)

    return ordered_fields


def _field_position(field: UnitField) -> int:
    """Return the sort key for a field."""

    position: int = field.position

    return position


def _images_in_position_order(unit: Unit) -> list[UnitImage]:
    """Return images sorted by position."""

    ordered_images: list[UnitImage] = sorted(list(unit.images), key=_image_position)

    return ordered_images


def _image_position(image: UnitImage) -> int:
    """Return the sort key for an image."""

    position: int = image.position

    return position


def _serialize_field(field: UnitField) -> UnitFieldReadResponse:
    """Return one labeled field."""

    field_response: UnitFieldReadResponse = UnitFieldReadResponse(
        id=field.id,
        position=field.position,
        label=field.label,
        value=field.value,
    )

    return field_response


def _serialize_resource_file(source: ContentSource) -> ResourceFileReadResponse | None:
    """Return the resource file and a safe rendering, or null for an album."""

    from app.models.content_source import ResourceFile
    from app.models.enums import ResourceFileMediaType
    from app.sources.resource_markdown import render_markdown_document
    from app.sources.resource_store import (
        LocalResourceFileStore,
        configured_resource_file_store,
    )
    from app.storage.artifacts import ArtifactAssetPathEscapeError

    resource_file: ResourceFile | None = source.resource_file

    if resource_file is None:

        return None

    file_store: LocalResourceFileStore = configured_resource_file_store()
    body_text: str = ""

    try:
        stored_path: Path = file_store.open(resource_file.relative_path)

        if stored_path.is_file():
            body_text = stored_path.read_bytes().decode("utf-8")
    except (ArtifactAssetPathEscapeError, UnicodeDecodeError, OSError):
        body_text = ""

    rendered_html: str | None = None

    if resource_file.media_type == ResourceFileMediaType.MARKDOWN and body_text != "":
        rendered_html = render_markdown_document(body_text)

    resource_response: ResourceFileReadResponse = ResourceFileReadResponse(
        relative_path=resource_file.relative_path,
        media_type=resource_file.media_type,
        byte_size=resource_file.byte_size,
        original_filename=resource_file.original_filename,
        provenance=resource_file.provenance,
        body=body_text,
        rendered_html=rendered_html,
    )

    return resource_response


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
from app.api.v1.source_resources import register_source_resource_routes
from app.api.v1.source_writes import register_source_write_routes


register_source_write_routes(sources_router)
register_source_resource_routes(sources_router)
register_source_intake_routes(sources_router)
