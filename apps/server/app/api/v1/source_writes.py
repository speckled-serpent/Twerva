"""Create, rename, and delete albums and units. No new image bytes."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_content_source_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    SourceCreateRequest,
    SourcePatchRequest,
    SourceReadResponse,
    UnitImageMetadataPatch,
    UnitImageReadResponse,
    UnitReadResponse,
    UnitWriteRequest,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit, UnitField, UnitImage
from app.models.enums import ContentSourceKind, UnitImageMediaType
from app.models.ops_user import OpsUser
from app.settings import get_settings
from app.sources.editing import (
    ALBUM_IN_USE_DETAIL,
    BLANK_FIELD_DETAIL,
    BLANK_NAME_DETAIL,
    EMPTY_UNIT_DETAIL,
    IMAGE_IN_USE_DETAIL,
    RESOURCE_NOT_IN_SLICE_DETAIL,
    UNIT_IN_USE_DETAIL,
    allocate_unique_source_slug,
    in_use_detail,
    new_row_id,
    normalize_field_writes,
    normalize_free_text,
    normalize_image_metadata,
    normalize_tags,
    slugify_source_name,
    stored_paths_in_use,
    unit_has_content,
)
from app.storage.artifacts import ArtifactAssetPathEscapeError
from app.themes.default_images import resolve_theme_image_path


IMAGE_MEDIA_TYPES: dict[UnitImageMediaType, str] = {
    UnitImageMediaType.JPEG: "image/jpeg",
    UnitImageMediaType.PNG: "image/png",
    UnitImageMediaType.SVG: "image/svg+xml",
}
SOURCE_SLUG_CONFLICT_DETAIL: str = "An album with that name already exists."


def register_source_write_routes(sources_router: APIRouter) -> None:
    """Attach album and unit writes, plus the packaged image stream."""

    sources_router.add_api_route(
        "",
        create_content_source,
        methods=["POST"],
        response_model=SourceReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    sources_router.add_api_route(
        "/{source_id}",
        patch_content_source,
        methods=["PATCH"],
        response_model=SourceReadResponse,
    )
    sources_router.add_api_route(
        "/{source_id}",
        delete_content_source,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    sources_router.add_api_route(
        "/{source_id}/units",
        create_unit,
        methods=["POST"],
        response_model=UnitReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}",
        patch_unit,
        methods=["PATCH"],
        response_model=UnitReadResponse,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}",
        delete_unit,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/images/{image_id}",
        patch_unit_image_metadata,
        methods=["PATCH"],
        response_model=UnitImageReadResponse,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/images/{image_id}",
        delete_unit_image,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/images/{image_id}/file",
        get_unit_image_file,
        methods=["GET"],
    )


def create_content_source(
    source_create_request: SourceCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SourceReadResponse:
    """Create an album. Resources are rejected. Readers cannot call this."""

    _ = current_ops_operator

    if source_create_request.kind != ContentSourceKind.ALBUM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=RESOURCE_NOT_IN_SLICE_DETAIL,
        )

    album_name: str = _require_name(source_create_request.name)
    taken_slugs: set[str] = set(
        our_database_session.scalars(select(ContentSource.slug)).all(),
    )
    album_slug: str = allocate_unique_source_slug(
        slugify_source_name(album_name),
        taken_slugs,
    )
    created_source: ContentSource = ContentSource(
        id=new_row_id(),
        kind=ContentSourceKind.ALBUM,
        name=album_name,
        slug=album_slug,
    )
    created_source.units = []
    our_database_session.add(created_source)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=SOURCE_SLUG_CONFLICT_DETAIL,
    )
    our_database_session.refresh(created_source)

    from app.api.v1.sources import serialize_content_source

    return serialize_content_source(created_source)


def patch_content_source(
    source_id: uuid.UUID,
    source_patch_request: SourcePatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SourceReadResponse:
    """Rename an album. The slug stays so existing links keep working."""

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_source.name = _require_name(source_patch_request.name)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=SOURCE_SLUG_CONFLICT_DETAIL,
    )
    our_database_session.refresh(found_source)

    from app.api.v1.sources import serialize_content_source

    return serialize_content_source(found_source)


def delete_content_source(
    source_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete an album. 409 when any of its image paths is still in use."""

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    _reject_when_paths_in_use(
        our_database_session,
        _image_paths_on_source(found_source),
        ALBUM_IN_USE_DETAIL,
    )
    stored_files: list[tuple[str, str | None]] = _stored_files_on_source(found_source)
    our_database_session.delete(found_source)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Album could not be deleted.",
    )
    _discard_stored_files(stored_files)


def create_unit(
    source_id: uuid.UUID,
    unit_write_request: UnitWriteRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitReadResponse:
    """Add a unit to an album. An empty unit is 400 and is not stored."""

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )

    if found_source.kind != ContentSourceKind.ALBUM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=RESOURCE_NOT_IN_SLICE_DETAIL,
        )

    free_text, tags, fields = _parsed_unit_write(unit_write_request)
    _require_unit_content(free_text, len(fields), 0)
    next_position: int = _next_unit_position(found_source.id, our_database_session)
    created_unit: Unit = Unit(
        id=new_row_id(),
        source_id=found_source.id,
        position=next_position,
        free_text=free_text,
        tags=tags,
    )
    created_unit.images = []
    created_unit.fields = []
    _replace_fields(created_unit, fields, our_database_session)
    our_database_session.add(created_unit)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Unit could not be saved.",
    )
    our_database_session.refresh(created_unit)

    from app.api.v1.sources import serialize_unit

    return serialize_unit(created_unit)


def patch_unit(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    unit_write_request: UnitWriteRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitReadResponse:
    """Replace free text, tags, and fields. Images are not changed here."""

    _ = current_ops_operator
    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    free_text, tags, fields = _parsed_unit_write(unit_write_request)
    _require_unit_content(free_text, len(fields), len(list(found_unit.images)))
    found_unit.free_text = free_text
    found_unit.tags = tags
    _replace_fields(found_unit, fields, our_database_session)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Unit could not be saved.",
    )
    our_database_session.refresh(found_unit)

    from app.api.v1.sources import serialize_unit

    return serialize_unit(found_unit)


def delete_unit(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete a unit. 409 when one of its image paths is still in use."""

    _ = current_ops_operator
    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    _reject_when_paths_in_use(
        our_database_session,
        _image_paths_on_unit(found_unit),
        UNIT_IN_USE_DETAIL,
    )
    stored_files: list[tuple[str, str | None]] = _stored_files_on_unit(found_unit)
    our_database_session.delete(found_unit)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Unit could not be deleted.",
    )
    _discard_stored_files(stored_files)


def patch_unit_image_metadata(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    image_id: uuid.UUID,
    image_patch_request: UnitImageMetadataPatch,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitImageReadResponse:
    """Update license, source, alt, and note. A bad license writes nothing."""

    _ = current_ops_operator
    found_image: UnitImage = _fetch_image_or_raise(
        source_id,
        unit_id,
        image_id,
        our_database_session,
    )
    image_source, license_note, alt_text = _parsed_image_metadata(image_patch_request)
    found_image.license = image_patch_request.license
    found_image.source = image_source
    found_image.license_note = license_note
    found_image.alt_text = alt_text
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Image details could not be saved.",
    )
    our_database_session.refresh(found_image)

    from app.api.v1.sources import serialize_image

    return serialize_image(found_image)


def delete_unit_image(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete one image row. 409 when a theme or artifact stores its path."""

    _ = current_ops_operator
    found_image: UnitImage = _fetch_image_or_raise(
        source_id,
        unit_id,
        image_id,
        our_database_session,
    )
    _reject_when_paths_in_use(
        our_database_session,
        {found_image.relative_path},
        IMAGE_IN_USE_DETAIL,
    )
    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    remaining_images: int = len(list(found_unit.images)) - 1
    _require_unit_content(
        found_unit.free_text,
        len(list(found_unit.fields)),
        remaining_images,
    )
    stored_files: list[tuple[str, str | None]] = [
        (found_image.relative_path, found_image.thumbnail_path),
    ]
    our_database_session.delete(found_image)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Image could not be deleted.",
    )
    _discard_stored_files(stored_files)


def get_unit_image_file(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream an existing image. ``theme-defaults/`` is read from the package.

    Readers may call this. This route does not upload or thumbnail.
    """

    found_image: UnitImage = _fetch_image_or_raise(
        source_id,
        unit_id,
        image_id,
        our_database_session,
    )
    storage_directory: Path = Path(get_settings().artifact_storage_dir)

    try:
        image_path: Path = resolve_theme_image_path(
            found_image.relative_path,
            storage_directory,
        )
    except ArtifactAssetPathEscapeError as escape_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image path is not allowed.",
        ) from escape_error

    if not image_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file is missing.",
        )

    image_response: FileResponse = FileResponse(
        path=image_path,
        media_type=IMAGE_MEDIA_TYPES[found_image.media_type],
    )

    return image_response


def _require_name(raw_name: str) -> str:
    """Return a stripped album name, or 400 when it is blank."""

    album_name: str = raw_name.strip()

    if album_name == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=BLANK_NAME_DETAIL,
        )

    return album_name


def _parsed_unit_write(
    unit_write_request: UnitWriteRequest,
) -> tuple[str | None, list[str], list[tuple[str, str]]]:
    """Normalize text, tags, and fields. A half-filled field is 400."""

    free_text: str | None = normalize_free_text(unit_write_request.free_text)
    tags: list[str] = normalize_tags(unit_write_request.tags)
    raw_fields: list[tuple[str, str]] = [
        (field.label, field.value) for field in unit_write_request.fields
    ]

    try:
        fields: list[tuple[str, str]] = normalize_field_writes(raw_fields)
    except ValueError as field_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(field_error) or BLANK_FIELD_DETAIL,
        ) from field_error

    return free_text, tags, fields


def _require_unit_content(
    free_text: str | None,
    field_count: int,
    image_count: int,
) -> None:
    """400 when the unit would have no image and no text."""

    if unit_has_content(free_text, field_count, image_count):

        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=EMPTY_UNIT_DETAIL,
    )


def _parsed_image_metadata(
    image_patch_request: UnitImageMetadataPatch,
) -> tuple[str, str, str | None]:
    """Return source, license note, and alt. Invalid license writes nothing."""

    try:
        image_source, license_note, alt_text = normalize_image_metadata(
            image_patch_request.license,
            image_patch_request.source,
            image_patch_request.license_note,
            image_patch_request.alt_text,
        )
    except ValueError as metadata_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(metadata_error),
        ) from metadata_error

    return image_source, license_note, alt_text


def _reject_when_paths_in_use(
    our_database_session: Session,
    candidate_paths: set[str],
    summary: str,
) -> None:
    """409, and do not delete, when a theme or artifact stores a path."""

    used_paths: set[str] = stored_paths_in_use(our_database_session, candidate_paths)

    if len(used_paths) == 0:

        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=in_use_detail(summary, used_paths),
    )


def _next_unit_position(source_id: uuid.UUID, our_database_session: Session) -> int:
    """Return the next position at the end of an album."""

    positions: list[int] = list(
        our_database_session.scalars(
            select(Unit.position).where(Unit.source_id == source_id),
        ).all(),
    )

    if len(positions) == 0:

        return 0

    next_position: int = max(positions) + 1

    return next_position


def _replace_fields(
    unit: Unit,
    fields: list[tuple[str, str]],
    our_database_session: Session,
) -> None:
    """Replace labeled fields. Positions restart at 0."""

    for existing_field in list(unit.fields):
        our_database_session.delete(existing_field)

    unit.fields = []

    for position, (label, value) in enumerate(fields):
        created_field: UnitField = UnitField(
            id=new_row_id(),
            unit_id=unit.id,
            position=position,
            label=label,
            value=value,
        )
        unit.fields.append(created_field)
        our_database_session.add(created_field)


def _fetch_unit_or_raise(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    our_database_session: Session,
) -> Unit:
    """Return a unit on this album, or 404."""

    found_unit: Unit | None = our_database_session.get(Unit, unit_id)

    if found_unit is None or found_unit.source_id != source_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit not found: {unit_id}",
        )

    return found_unit


def _fetch_image_or_raise(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session,
) -> UnitImage:
    """Return an image on this unit, or 404."""

    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    found_image: UnitImage | None = our_database_session.get(UnitImage, image_id)

    if found_image is None or found_image.unit_id != found_unit.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image not found: {image_id}",
        )

    return found_image


def _discard_stored_files(stored_files: list[tuple[str, str | None]]) -> None:
    """Delete album bytes after the row commit. Package files stay."""

    from app.sources.image_store import LocalAlbumImageStore, configured_album_image_store

    image_store: LocalAlbumImageStore = configured_album_image_store()

    for relative_path, thumbnail_path in stored_files:
        image_store.delete(relative_path)

        if thumbnail_path is not None:
            image_store.delete(thumbnail_path)


def _stored_files_on_unit(unit: Unit) -> list[tuple[str, str | None]]:
    """Return original and thumbnail paths for one unit."""

    stored_files: list[tuple[str, str | None]] = [
        (image.relative_path, image.thumbnail_path) for image in unit.images
    ]

    return stored_files


def _stored_files_on_source(source: ContentSource) -> list[tuple[str, str | None]]:
    """Return original and thumbnail paths for every image in an album."""

    stored_files: list[tuple[str, str | None]] = []

    for unit in source.units:
        stored_files.extend(_stored_files_on_unit(unit))

    return stored_files


def _image_paths_on_unit(unit: Unit) -> set[str]:
    """Return every image path stored on a unit."""

    image_paths: set[str] = {image.relative_path for image in unit.images}

    return image_paths


def _image_paths_on_source(source: ContentSource) -> set[str]:
    """Return every image path stored in an album."""

    image_paths: set[str] = set()

    for unit in source.units:
        image_paths.update(_image_paths_on_unit(unit))

    return image_paths
