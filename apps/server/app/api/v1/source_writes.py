"""Create, rename, and delete albums and units. No new image bytes."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_content_source_by_id_or_raise,
    fetch_theme_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    SourceCreateRequest,
    SourcePatchRequest,
    SourceReadResponse,
    UnitImageMetadataPatch,
    UnitImageReadResponse,
    UnitElementTextWrite,
    UnitReadResponse,
    UnitWriteRequest,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit, UnitElementText, UnitExclusion, UnitImage
from app.models.enums import UnitImageMediaType, UnitTextStatus
from app.models.theme import Theme
from app.models.ops_user import OpsUser
from app.settings import get_settings
from app.sources.editing import (
    ALBUM_IN_USE_DETAIL,
    BLANK_NAME_DETAIL,
    IMAGE_IN_USE_DETAIL,
    UNIT_IN_USE_DETAIL,
    allocate_unique_source_slug,
    in_use_detail,
    new_row_id,
    normalize_image_metadata,
    slugify_source_name,
    stored_paths_in_use,
)
from app.sources.unit_exclusions import normalized_exclusion_ids
from app.sources.unit_theme import (
    IMAGE_REQUIRED_DETAIL,
    text_values_for_theme,
    theme_requires_image,
)
from app.storage.artifacts import ArtifactAssetPathEscapeError
from app.themes.default_images import resolve_theme_image_path


IMAGE_MEDIA_TYPES: dict[UnitImageMediaType, str] = {
    UnitImageMediaType.JPEG: "image/jpeg",
    UnitImageMediaType.PNG: "image/png",
    UnitImageMediaType.SVG: "image/svg+xml",
}
SOURCE_SLUG_CONFLICT_DETAIL: str = "A source with that name already exists."


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
    """Create a source bound to a theme. Readers cannot call this."""

    _ = current_ops_operator
    fetch_theme_by_id_or_raise(
        source_create_request.theme_id,
        our_database_session,
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
        theme_id=source_create_request.theme_id,
        name=album_name,
        slug=album_slug,
        inspiration="",
        rules="",
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
    """Rename a source."""

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    updated_name: str = _require_name(source_patch_request.name)
    found_source.name = updated_name
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
        conflict_detail="Source could not be deleted.",
    )
    _discard_stored_files(stored_files)


def create_unit(
    source_id: uuid.UUID,
    unit_write_request: UnitWriteRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitReadResponse:
    """Add a unit. A theme that needs an image is 400 here."""

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )
    unit_name: str = _require_name(unit_write_request.name)
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_theme,
        unit_write_request.texts,
    )
    created_unit_id: uuid.UUID = new_row_id()
    excluded_ids: list[uuid.UUID] = _parsed_exclusions(
        created_unit_id,
        unit_write_request.excluded_unit_ids,
        found_source,
    )
    _require_image_when_theme_needs_one(found_theme, 0)
    next_position: int = _next_unit_position(found_source.id, our_database_session)
    created_unit: Unit = Unit(
        id=created_unit_id,
        source_id=found_source.id,
        position=next_position,
        name=unit_name,
    )
    created_unit.images = []
    created_unit.element_texts = []
    created_unit.exclusions = []
    created_unit.text_status = UnitTextStatus.LIVE
    _replace_texts(created_unit, stored_texts, our_database_session)
    our_database_session.add(created_unit)
    _store_exclusion_pairs(created_unit, excluded_ids, found_source, our_database_session)
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
    """Replace the name and theme text. Images are not changed here."""

    _ = current_ops_operator
    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )
    unit_name: str = _require_name(unit_write_request.name)
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_theme,
        unit_write_request.texts,
    )
    excluded_ids: list[uuid.UUID] = _parsed_exclusions(
        found_unit.id,
        unit_write_request.excluded_unit_ids,
        found_source,
    )
    _require_image_when_theme_needs_one(found_theme, len(list(found_unit.images)))
    found_unit.name = unit_name

    if found_unit.text_status == UnitTextStatus.DRAFT:
        _store_draft_texts(found_unit, stored_texts, our_database_session)
    else:
        _replace_texts(found_unit, stored_texts, our_database_session)
        found_unit.text_status = UnitTextStatus.LIVE

    _replace_exclusion_pairs(found_unit, excluded_ids, found_source, our_database_session)
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
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    _reject_when_paths_in_use(
        our_database_session,
        _image_paths_on_unit(found_unit),
        UNIT_IN_USE_DETAIL,
    )
    stored_files: list[tuple[str, str | None]] = _stored_files_on_unit(found_unit)
    _clear_exclusion_pairs(found_unit, found_source, our_database_session)
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
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )
    remaining_images: int = len(list(found_unit.images)) - 1
    _require_image_when_theme_needs_one(found_theme, remaining_images)
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


def _parsed_texts(
    theme: Theme,
    text_writes: list[UnitElementTextWrite],
) -> list[tuple[uuid.UUID, str]]:
    """Return one value per text element. A foreign element id is 400."""

    submitted_texts: list[tuple[uuid.UUID, str]] = [
        (text_write.theme_element_id, text_write.value)
        for text_write in text_writes
    ]

    try:
        stored_texts: list[tuple[uuid.UUID, str]] = text_values_for_theme(
            theme,
            submitted_texts,
        )
    except ValueError as text_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(text_error),
        ) from text_error

    return stored_texts


def _require_image_when_theme_needs_one(theme: Theme, image_count: int) -> None:
    """400 when a picture theme would be left without its unit image."""

    if not theme_requires_image(theme) or image_count > 0:

        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=IMAGE_REQUIRED_DETAIL,
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


def _parsed_exclusions(
    unit_id: uuid.UUID,
    submitted_ids: list[uuid.UUID],
    source: ContentSource,
) -> list[uuid.UUID]:
    """Return the other unit ids to store. A bad id is 400."""

    sibling_ids: set[uuid.UUID] = {
        sibling.id for sibling in list(source.units) if sibling.id != unit_id
    }

    try:
        stored_ids: list[uuid.UUID] = normalized_exclusion_ids(
            unit_id,
            submitted_ids,
            sibling_ids,
        )
    except ValueError as exclusion_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exclusion_error),
        ) from exclusion_error

    return stored_ids


def _store_exclusion_pairs(
    unit: Unit,
    excluded_ids: list[uuid.UUID],
    source: ContentSource,
    our_database_session: Session,
) -> None:
    """Write both directions of each new pair."""

    for excluded_id in excluded_ids:
        _append_exclusion(unit, excluded_id, our_database_session)
        partner: Unit | None = _sibling_unit(source, excluded_id)

        if partner is None:
            continue

        _append_exclusion(partner, unit.id, our_database_session)


def _replace_exclusion_pairs(
    unit: Unit,
    excluded_ids: list[uuid.UUID],
    source: ContentSource,
    our_database_session: Session,
) -> None:
    """Replace every pair that names this unit, in both directions."""

    _clear_exclusion_pairs(unit, source, our_database_session)
    _store_exclusion_pairs(unit, excluded_ids, source, our_database_session)


def _clear_exclusion_pairs(
    unit: Unit,
    source: ContentSource,
    our_database_session: Session,
) -> None:
    """Drop pairs that name this unit from every unit in the source."""

    for sibling in list(source.units):
        kept_rows: list[UnitExclusion] = []

        for exclusion in list(sibling.exclusions):
            names_unit: bool = (
                exclusion.unit_id == unit.id or exclusion.excluded_unit_id == unit.id
            )

            if names_unit:
                our_database_session.delete(exclusion)
            else:
                kept_rows.append(exclusion)

        sibling.exclusions = kept_rows


def _append_exclusion(
    unit: Unit,
    excluded_unit_id: uuid.UUID,
    our_database_session: Session,
) -> None:
    """Add one direction if this unit does not already store it."""

    for exclusion in list(unit.exclusions):

        if exclusion.excluded_unit_id == excluded_unit_id:

            return

    created_exclusion: UnitExclusion = UnitExclusion(
        id=new_row_id(),
        unit_id=unit.id,
        excluded_unit_id=excluded_unit_id,
    )
    unit.exclusions.append(created_exclusion)
    our_database_session.add(created_exclusion)


def _sibling_unit(source: ContentSource, unit_id: uuid.UUID) -> Unit | None:
    """Return a unit on this source, or null."""

    for sibling in list(source.units):

        if sibling.id == unit_id:

            return sibling

    return None


def _store_draft_texts(
    unit: Unit,
    stored_texts: list[tuple[uuid.UUID, str]],
    our_database_session: Session,
) -> None:
    """Write draft copy beside the live value. Live text stays."""

    existing_by_element: dict[uuid.UUID, UnitElementText] = {
        element_text.theme_element_id: element_text
        for element_text in list(unit.element_texts)
    }

    for theme_element_id, value in stored_texts:
        existing_text: UnitElementText | None = existing_by_element.get(theme_element_id)

        if existing_text is None:
            created_text: UnitElementText = UnitElementText(
                id=new_row_id(),
                unit_id=unit.id,
                theme_element_id=theme_element_id,
                value="",
                draft_value=value,
            )
            unit.element_texts.append(created_text)
            our_database_session.add(created_text)
        else:
            existing_text.draft_value = value


def _replace_texts(
    unit: Unit,
    stored_texts: list[tuple[uuid.UUID, str]],
    our_database_session: Session,
) -> None:
    """Replace theme text. One row per text element, including blanks."""

    for existing_text in list(unit.element_texts):
        our_database_session.delete(existing_text)

    unit.element_texts = []

    for theme_element_id, value in stored_texts:
        created_text: UnitElementText = UnitElementText(
            id=new_row_id(),
            unit_id=unit.id,
            theme_element_id=theme_element_id,
            value=value,
            draft_value=None,
        )
        unit.element_texts.append(created_text)
        our_database_session.add(created_text)


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
