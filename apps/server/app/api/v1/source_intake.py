"""Upload and URL import for images that belong to a unit.

License, type, and size are checked before any byte is written. A
failure leaves no row and no file.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_content_source_by_id_or_raise,
    fetch_theme_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    UnitImageCreateItem,
    UnitImageImportRequest,
    UnitImageReadResponse,
    UnitReadResponse,
    UnitWithImagesCreateRequest,
    UnitWriteRequest,
)
from app.api.v1.source_writes import (
    _fetch_image_or_raise,
    _fetch_unit_or_raise,
    _next_unit_position,
    _parsed_exclusions,
    _parsed_texts,
    _replace_texts,
    _require_image_when_theme_needs_one,
    _require_name,
    _store_exclusion_pairs,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit, UnitImage
from app.models.enums import UnitImageIntake, UnitImageLicense
from app.models.theme import Theme
from app.models.ops_user import OpsUser
from app.sources.editing import ONE_IMAGE_DETAIL, new_row_id, normalize_image_metadata
from app.sources.unit_theme import IMAGE_NOT_USED_DETAIL, theme_requires_image
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
CHOOSE_IMAGE_FILE_DETAIL: str = "Choose an image file."
ENTER_IMAGE_URL_DETAIL: str = "Enter an image URL."
INVALID_UNIT_IMAGE_DETAIL: str = "Image details are not valid."


def register_source_intake_routes(sources_router: APIRouter) -> None:
    """Attach upload, URL import, and thumbnail streaming."""

    sources_router.add_api_route(
        "/{source_id}/units/with-images",
        create_unit_with_images_upload,
        methods=["POST"],
        response_model=UnitReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
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


@dataclass(frozen=True)
class UnitImageAttachment:
    """One image ready to store on a unit that is being created."""

    payload: bytes
    intake: UnitImageIntake
    image_license: UnitImageLicense
    source: str
    license_note: str
    alt_text: str | None


def create_unit_with_images_upload(
    source_id: uuid.UUID,
    unit_json: str = Form(...),
    files: list[UploadFile] | None = File(None),
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitReadResponse:
    """Create a unit and its images in one request. Storage stays on disk.

    An image-only unit is valid because the images are part of this call.
    A license, type, or download failure writes no row and no file.
    """

    _ = current_ops_operator
    create_request: UnitWithImagesCreateRequest = parse_unit_with_images_json(unit_json)
    upload_files: list[UploadFile] = [] if files is None else list(files)
    file_payloads: list[bytes] = [upload.file.read() for upload in upload_files]

    with httpx.Client() as http_client:
        attachments: list[UnitImageAttachment] = attachments_for_new_unit(
            create_request,
            file_payloads,
            http_client,
        )

    unit_write_request: UnitWriteRequest = UnitWriteRequest(
        name=create_request.name,
        texts=create_request.texts,
        excluded_unit_ids=create_request.excluded_unit_ids,
    )
    created_unit: UnitReadResponse = create_unit_with_images(
        source_id,
        unit_write_request,
        attachments,
        our_database_session,
        configured_album_image_store(),
    )

    return created_unit


def parse_unit_with_images_json(unit_json: str) -> UnitWithImagesCreateRequest:
    """Read the unit JSON field. A bad license is rejected before a write."""

    try:
        create_request: UnitWithImagesCreateRequest = (
            UnitWithImagesCreateRequest.model_validate_json(unit_json)
        )
    except ValidationError as validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_UNIT_IMAGE_DETAIL,
        ) from validation_error

    return create_request


def attachments_for_new_unit(
    create_request: UnitWithImagesCreateRequest,
    file_payloads: list[bytes],
    http_client: httpx.Client,
) -> list[UnitImageAttachment]:
    """Check every license, then read files and download URLs.

    Args:
        create_request: Parsed unit and image list.
        file_payloads: Multipart files, in ``file_index`` order.
        http_client: Used once per URL image.

    Returns:
        Attachments whose metadata already passed the license gate.

    Raises:
        HTTPException: Too many images, a missing file, a blank URL, or
            a license failure. No file is written.
    """

    if len(create_request.images) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=TOO_MANY_FILES_DETAIL,
        )

    for image_item in create_request.images:
        _metadata_or_400(
            image_item.license,
            image_item.source,
            image_item.license_note,
            image_item.alt_text,
        )

    attachments: list[UnitImageAttachment] = []

    for image_item in create_request.images:
        payload, intake = _payload_for_create_item(image_item, file_payloads, http_client)
        image_source, license_note, alt_text = _metadata_or_400(
            image_item.license,
            image_item.source,
            image_item.license_note,
            image_item.alt_text,
        )
        attachment: UnitImageAttachment = UnitImageAttachment(
            payload=payload,
            intake=intake,
            image_license=image_item.license,
            source=image_source,
            license_note=license_note,
            alt_text=alt_text,
        )
        attachments.append(attachment)

    return attachments


def create_unit_with_images(
    source_id: uuid.UUID,
    unit_write_request: UnitWriteRequest,
    attachments: list[UnitImageAttachment],
    our_database_session: Session,
    image_store: LocalAlbumImageStore,
) -> UnitReadResponse:
    """Store the unit and every image in one commit, or store nothing.

    Args:
        source_id: Album id.
        unit_write_request: Name, theme text, and excluded unit ids.
        attachments: Images for this unit. Empty is allowed when the
            text or a field gives the unit content.
        our_database_session: Open session.
        image_store: Disk store. Bytes stay under ``ARTIFACT_STORAGE_DIR``.

    Returns:
        The new unit, including its images.

    Raises:
        HTTPException: The unit would be empty, or an image fails the
            license, type, or size gate. No row and no file remain.
    """

    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )

    if not theme_requires_image(found_theme):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=IMAGE_NOT_USED_DETAIL,
        )

    if len(attachments) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ONE_IMAGE_DETAIL,
        )

    if len(attachments) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=TOO_MANY_FILES_DETAIL,
        )

    unit_name: str = _require_name(unit_write_request.name)
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_theme,
        unit_write_request.texts,
    )
    staged_images: list[tuple[PreparedUnitImage, UnitImageAttachment]] = []

    for attachment in attachments:
        _metadata_or_400(
            attachment.image_license,
            attachment.source,
            attachment.license_note,
            attachment.alt_text,
        )

        try:
            prepared_image: PreparedUnitImage = prepare_image_bytes(attachment.payload)
        except ImageIntakeError as intake_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=intake_error.detail,
            ) from intake_error

        staged_images.append((prepared_image, attachment))

    _require_image_when_theme_needs_one(found_theme, len(staged_images))
    unit_id: uuid.UUID = new_row_id()
    excluded_ids: list[uuid.UUID] = _parsed_exclusions(
        unit_id,
        unit_write_request.excluded_unit_ids,
        found_source,
    )
    next_position: int = _next_unit_position(found_source.id, our_database_session)
    saved_paths: list[str] = []

    try:
        created_images: list[UnitImage] = [
            _materialize_unit_image(
                found_source.id,
                unit_id,
                image_position,
                prepared_image,
                attachment,
                image_store,
                saved_paths,
            )
            for image_position, (prepared_image, attachment) in enumerate(staged_images)
        ]
    except Exception:
        _delete_saved_paths(image_store, saved_paths)

        raise

    created_unit: Unit = Unit(
        id=unit_id,
        source_id=found_source.id,
        position=next_position,
        name=unit_name,
    )
    created_unit.images = created_images
    created_unit.element_texts = []
    created_unit.exclusions = []
    our_database_session.add(created_unit)
    _store_exclusion_pairs(
        created_unit,
        excluded_ids,
        found_source,
        our_database_session,
    )

    for created_image in created_images:
        our_database_session.add(created_image)

    _replace_texts(created_unit, stored_texts, our_database_session)

    try:
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail="Unit could not be saved.",
        )
    except Exception:
        _delete_saved_paths(image_store, saved_paths)

        raise

    our_database_session.refresh(created_unit)

    from app.api.v1.sources import serialize_unit

    return serialize_unit(created_unit)


def _payload_for_create_item(
    image_item: UnitImageCreateItem,
    file_payloads: list[bytes],
    http_client: httpx.Client,
) -> tuple[bytes, UnitImageIntake]:
    """Return bytes for one create item. License was already checked."""

    if image_item.kind == "file":
        file_index: int | None = image_item.file_index
        file_missing: bool = (
            file_index is None
            or file_index < 0
            or file_index >= len(file_payloads)
        )

        if file_missing or file_index is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=CHOOSE_IMAGE_FILE_DETAIL,
            )

        return file_payloads[file_index], UnitImageIntake.UPLOAD

    image_url: str = "" if image_item.url is None else image_item.url.strip()

    if image_url == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ENTER_IMAGE_URL_DETAIL,
        )

    try:
        downloaded: bytes = download_image_once(image_url, http_client)
    except ImageIntakeError as intake_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=intake_error.detail,
        ) from intake_error

    return downloaded, UnitImageIntake.URL


def _materialize_unit_image(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    position: int,
    prepared_image: PreparedUnitImage,
    attachment: UnitImageAttachment,
    image_store: LocalAlbumImageStore,
    saved_paths: list[str],
) -> UnitImage:
    """Write one original and its thumbnail. The row is not committed yet."""

    image_id: uuid.UUID = new_row_id()
    relative_path: str = album_image_relative_path(
        source_id,
        unit_id,
        image_id,
        prepared_image.extension,
    )
    thumbnail_path: str | None = None
    saved_paths.append(relative_path)
    image_store.save(relative_path, prepared_image.payload)

    if prepared_image.thumbnail_jpeg is not None:
        thumbnail_path = album_thumbnail_relative_path(source_id, unit_id, image_id)
        saved_paths.append(thumbnail_path)
        image_store.save(thumbnail_path, prepared_image.thumbnail_jpeg)

    created_image: UnitImage = UnitImage(
        id=image_id,
        unit_id=unit_id,
        position=position,
        relative_path=relative_path,
        media_type=prepared_image.media_type,
        byte_size=len(prepared_image.payload),
        width=prepared_image.width,
        height=prepared_image.height,
        alt_text=attachment.alt_text,
        license=attachment.image_license,
        source=attachment.source,
        license_note=attachment.license_note,
        intake=attachment.intake,
        thumbnail_path=thumbnail_path,
    )

    return created_image


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
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )

    if not theme_requires_image(found_theme):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=IMAGE_NOT_USED_DETAIL,
        )

    if len(payloads) != 1 or len(list(found_unit.images)) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ONE_IMAGE_DETAIL,
        )
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
