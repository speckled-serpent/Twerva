"""Upload and URL import for images that belong to a unit.

License, type, and size are checked before any byte is written. A
failure leaves no row and no file.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import UnitImageImportRequest, UnitImageReadResponse
from app.api.v1.source_writes import _fetch_image_or_raise, _fetch_unit_or_raise
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit, UnitImage
from app.models.enums import ContentSourceKind, UnitImageIntake, UnitImageLicense
from app.models.ops_user import OpsUser
from app.sources.editing import RESOURCE_NOT_IN_SLICE_DETAIL, new_row_id, normalize_image_metadata
from app.sources.image_intake import (
    ImageIntakeError,
    PreparedUnitImage,
    download_image_once,
    prepare_image_bytes,
)
from app.sources.image_store import (
    LocalAlbumImageStore,
    album_image_relative_path,
    album_thumbnail_relative_path,
    configured_album_image_store,
)
from app.storage.artifacts import ArtifactAssetPathEscapeError


MAX_FILES_PER_UPLOAD: int = 20
TOO_MANY_FILES_DETAIL: str = "Upload at most 20 images at a time."
NO_FILES_DETAIL: str = "Choose at least one image."


def register_source_intake_routes(sources_router: APIRouter) -> None:
    """Attach upload, URL import, and thumbnail streaming."""

    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/images",
        upload_unit_images,
        methods=["POST"],
        response_model=list[UnitImageReadResponse],
        status_code=status.HTTP_201_CREATED,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/images/import",
        import_unit_image,
        methods=["POST"],
        response_model=UnitImageReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/images/{image_id}/thumbnail",
        get_unit_image_thumbnail,
        methods=["GET"],
    )


def upload_unit_images(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    image_license: UnitImageLicense = Form(..., alias="license"),
    source: str = Form(...),
    alt_text: str | None = Form(None),
    license_note: str = Form(""),
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> list[UnitImageReadResponse]:
    """Store one or more files on a unit. Shared license fields apply to each."""

    _ = current_ops_operator
    payloads: list[bytes] = [upload.file.read() for upload in files]
    created_images: list[UnitImageReadResponse] = add_images_from_payloads(
        source_id,
        unit_id,
        payloads,
        image_license,
        source,
        alt_text,
        license_note,
        UnitImageIntake.UPLOAD,
        our_database_session,
        configured_album_image_store(),
    )

    return created_images


def import_unit_image(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    image_import_request: UnitImageImportRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitImageReadResponse:
    """Download one URL and store it. The request is not fetched again later."""

    _ = current_ops_operator

    try:
        with httpx.Client() as http_client:
            payload: bytes = download_image_once(
                image_import_request.url,
                http_client,
            )
    except ImageIntakeError as intake_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=intake_error.detail,
        ) from intake_error

    created_images: list[UnitImageReadResponse] = add_images_from_payloads(
        source_id,
        unit_id,
        [payload],
        image_import_request.license,
        image_import_request.source,
        image_import_request.alt_text,
        image_import_request.license_note,
        UnitImageIntake.URL,
        our_database_session,
        configured_album_image_store(),
    )

    return created_images[0]


def add_images_from_payloads(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    payloads: list[bytes],
    image_license: UnitImageLicense,
    source: str,
    alt_text: str | None,
    license_note: str,
    intake: UnitImageIntake,
    our_database_session: Session,
    image_store: LocalAlbumImageStore,
) -> list[UnitImageReadResponse]:
    """Validate every file, then write rows and bytes. A failure writes nothing.

    Args:
        source_id: Album id.
        unit_id: Unit that will own the images.
        payloads: Raw files, already read.
        image_license: Allowlisted license shared by the batch.
        source: Provenance. A URL or a short note.
        alt_text: Optional description.
        license_note: Required when the license is ``licensed``.
        intake: ``upload`` or ``url``.
        our_database_session: Open session.
        image_store: Where the bytes go.

    Returns:
        The new image rows.
    """

    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    _require_album(our_database_session, source_id)
    image_source, cleaned_note, cleaned_alt = _metadata_or_400(
        image_license,
        source,
        license_note,
        alt_text,
    )
    prepared_images: list[PreparedUnitImage] = _prepare_all_or_400(payloads)
    saved_paths: list[str] = []

    try:
        created_rows: list[UnitImage] = _write_prepared_images(
            found_unit,
            prepared_images,
            image_license,
            image_source,
            cleaned_note,
            cleaned_alt,
            intake,
            image_store,
            our_database_session,
            saved_paths,
        )
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail="Image could not be saved.",
        )
    except Exception:
        _delete_saved_paths(image_store, saved_paths)

        raise

    for created_row in created_rows:
        our_database_session.refresh(created_row)

    from app.api.v1.sources import serialize_image

    created_responses: list[UnitImageReadResponse] = [
        serialize_image(created_row) for created_row in created_rows
    ]

    return created_responses


def get_unit_image_thumbnail(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream the JPEG thumbnail. SVG and packaged defaults have none.

    Readers may call this.
    """

    found_image: UnitImage = _fetch_image_or_raise(
        source_id,
        unit_id,
        image_id,
        our_database_session,
    )

    if found_image.thumbnail_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This image has no thumbnail.",
        )

    image_store: LocalAlbumImageStore = configured_album_image_store()

    try:
        thumbnail_file: Path = image_store.open(found_image.thumbnail_path)
    except ArtifactAssetPathEscapeError as escape_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image path is not allowed.",
        ) from escape_error

    if not thumbnail_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thumbnail file is missing.",
        )

    thumbnail_response: FileResponse = FileResponse(
        path=thumbnail_file,
        media_type="image/jpeg",
    )

    return thumbnail_response


def _require_album(our_database_session: Session, source_id: uuid.UUID) -> None:
    """Units on a resource are not in this slice."""

    found_source: ContentSource | None = our_database_session.get(ContentSource, source_id)

    if found_source is not None and found_source.kind != ContentSourceKind.ALBUM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=RESOURCE_NOT_IN_SLICE_DETAIL,
        )


def _metadata_or_400(
    image_license: UnitImageLicense,
    source: str,
    license_note: str,
    alt_text: str | None,
) -> tuple[str, str, str | None]:
    """Return cleaned license fields, or 400. Does not write."""

    try:
        cleaned_metadata: tuple[str, str, str | None] = normalize_image_metadata(
            image_license,
            source,
            license_note,
            alt_text,
        )
    except ValueError as metadata_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(metadata_error),
        ) from metadata_error

    return cleaned_metadata


def _prepare_all_or_400(payloads: list[bytes]) -> list[PreparedUnitImage]:
    """Inspect every file before the first write."""

    if len(payloads) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_FILES_DETAIL,
        )

    if len(payloads) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=TOO_MANY_FILES_DETAIL,
        )

    prepared_images: list[PreparedUnitImage] = []

    for payload in payloads:

        try:
            prepared_image: PreparedUnitImage = prepare_image_bytes(payload)
        except ImageIntakeError as intake_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=intake_error.detail,
            ) from intake_error

        prepared_images.append(prepared_image)

    return prepared_images


def _write_prepared_images(
    unit: Unit,
    prepared_images: list[PreparedUnitImage],
    image_license: UnitImageLicense,
    image_source: str,
    license_note: str,
    alt_text: str | None,
    intake: UnitImageIntake,
    image_store: LocalAlbumImageStore,
    our_database_session: Session,
    saved_paths: list[str],
) -> list[UnitImage]:
    """Write files then rows. ``saved_paths`` records what to undo."""

    next_position: int = _next_image_position(unit)
    created_rows: list[UnitImage] = []

    for offset, prepared_image in enumerate(prepared_images):
        image_id: uuid.UUID = new_row_id()
        relative_path: str = album_image_relative_path(
            unit.source_id,
            unit.id,
            image_id,
            prepared_image.extension,
        )
        thumbnail_path: str | None = None
        image_store.save(relative_path, prepared_image.payload)
        saved_paths.append(relative_path)

        if prepared_image.thumbnail_jpeg is not None:
            thumbnail_path = album_thumbnail_relative_path(
                unit.source_id,
                unit.id,
                image_id,
            )
            image_store.save(thumbnail_path, prepared_image.thumbnail_jpeg)
            saved_paths.append(thumbnail_path)

        created_image: UnitImage = UnitImage(
            id=image_id,
            unit_id=unit.id,
            position=next_position + offset,
            relative_path=relative_path,
            media_type=prepared_image.media_type,
            byte_size=len(prepared_image.payload),
            width=prepared_image.width,
            height=prepared_image.height,
            alt_text=alt_text,
            license=image_license,
            source=image_source,
            license_note=license_note,
            intake=intake,
            thumbnail_path=thumbnail_path,
        )
        unit.images.append(created_image)
        our_database_session.add(created_image)
        created_rows.append(created_image)

    return created_rows


def _next_image_position(unit: Unit) -> int:
    """Return the next image position on this unit."""

    positions: list[int] = [image.position for image in list(unit.images)]

    if len(positions) == 0:

        return 0

    next_position: int = max(positions) + 1

    return next_position


def _delete_saved_paths(image_store: LocalAlbumImageStore, saved_paths: list[str]) -> None:
    """Remove files written for a batch that did not commit."""

    for relative_path in saved_paths:
        image_store.delete(relative_path)
