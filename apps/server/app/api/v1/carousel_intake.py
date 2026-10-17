"""Upload and URL import for images that belong to a slide.

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
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    SlideImageCreateItem,
    SlideImageImportRequest,
    SlideImageReadResponse,
    SlideReadResponse,
    SlideWithImagesCreateRequest,
    SlideWriteRequest,
)
from app.api.v1.carousel_writes import (
    _fetch_image_or_raise,
    _fetch_slide_or_raise,
    _next_slide_position,
    _parsed_exclusions,
    _parsed_texts,
    _replace_texts,
    _require_image_when_skeleton_needs_one,
    _require_name,
    _store_exclusion_pairs,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.albums.linking import ensure_carousel_album, next_album_image_position
from app.models.album import Album, AlbumImage
from app.models.carousel import Carousel, Slide
from app.models.enums import SlideTextStatus
from app.models.enums import SlideImageIntake, SlideImageLicense
from app.models.skeleton import Skeleton
from app.models.ops_user import OpsUser
from app.carousels.editing import ONE_IMAGE_DETAIL, new_row_id, normalize_image_metadata
from app.carousels.slide_skeleton import IMAGE_NOT_USED_DETAIL, skeleton_requires_image
from app.carousels.image_intake import (
    ImageIntakeError,
    PreparedSlideImage,
    download_image_once,
    prepare_image_bytes,
)
from app.carousels.image_store import (
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
INVALID_SLIDE_IMAGE_DETAIL: str = "Image details are not valid."


def register_source_intake_routes(carousels_router: APIRouter) -> None:
    """Attach upload, URL import, and thumbnail streaming."""

    carousels_router.add_api_route(
        "/{carousel_id}/slides/with-images",
        create_slide_with_images_upload,
        methods=["POST"],
        response_model=SlideReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/images",
        upload_slide_images,
        methods=["POST"],
        response_model=list[SlideImageReadResponse],
        status_code=status.HTTP_201_CREATED,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/images/import",
        import_slide_image,
        methods=["POST"],
        response_model=SlideImageReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/images/{image_id}/thumbnail",
        get_slide_image_thumbnail,
        methods=["GET"],
    )


def upload_slide_images(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    image_license: SlideImageLicense = Form(..., alias="license"),
    source: str = Form(...),
    alt_text: str | None = Form(None),
    license_note: str = Form(""),
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> list[SlideImageReadResponse]:
    """Store one or more files on a slide. Shared license fields apply to each."""

    _ = current_ops_operator
    payloads: list[bytes] = [upload.file.read() for upload in files]
    created_images: list[SlideImageReadResponse] = add_images_from_payloads(
        carousel_id,
        slide_id,
        payloads,
        image_license,
        source,
        alt_text,
        license_note,
        SlideImageIntake.UPLOAD,
        our_database_session,
        configured_album_image_store(),
    )

    return created_images


def import_slide_image(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_import_request: SlideImageImportRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideImageReadResponse:
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

    created_images: list[SlideImageReadResponse] = add_images_from_payloads(
        carousel_id,
        slide_id,
        [payload],
        image_import_request.license,
        image_import_request.source,
        image_import_request.alt_text,
        image_import_request.license_note,
        SlideImageIntake.URL,
        our_database_session,
        configured_album_image_store(),
    )

    return created_images[0]


@dataclass(frozen=True)
class SlideImageAttachment:
    """One image ready to store on a slide that is being created."""

    payload: bytes
    intake: SlideImageIntake
    image_license: SlideImageLicense
    source: str
    license_note: str
    alt_text: str | None


def create_slide_with_images_upload(
    carousel_id: uuid.UUID,
    slide_json: str = Form(...),
    files: list[UploadFile] | None = File(None),
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideReadResponse:
    """Create a slide and its images in one request. Storage stays on disk.

    An image-only slide is valid because the images are part of this call.
    A license, type, or download failure writes no row and no file.
    """

    _ = current_ops_operator
    create_request: SlideWithImagesCreateRequest = parse_slide_with_images_json(slide_json)
    upload_files: list[UploadFile] = [] if files is None else list(files)
    file_payloads: list[bytes] = [upload.file.read() for upload in upload_files]

    with httpx.Client() as http_client:
        attachments: list[SlideImageAttachment] = attachments_for_new_slide(
            create_request,
            file_payloads,
            http_client,
        )

    slide_write_request: SlideWriteRequest = SlideWriteRequest(
        name=create_request.name,
        texts=create_request.texts,
        excluded_slide_ids=create_request.excluded_slide_ids,
    )
    created_slide: SlideReadResponse = create_slide_with_images(
        carousel_id,
        slide_write_request,
        attachments,
        our_database_session,
        configured_album_image_store(),
    )

    return created_slide


def parse_slide_with_images_json(slide_json: str) -> SlideWithImagesCreateRequest:
    """Read the slide JSON field. A bad license is rejected before a write."""

    try:
        create_request: SlideWithImagesCreateRequest = (
            SlideWithImagesCreateRequest.model_validate_json(slide_json)
        )
    except ValidationError as validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_SLIDE_IMAGE_DETAIL,
        ) from validation_error

    return create_request


def attachments_for_new_slide(
    create_request: SlideWithImagesCreateRequest,
    file_payloads: list[bytes],
    http_client: httpx.Client,
) -> list[SlideImageAttachment]:
    """Check every license, then read files and download URLs.

    Args:
        create_request: Parsed slide and image list.
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

    attachments: list[SlideImageAttachment] = []

    for image_item in create_request.images:
        payload, intake = _payload_for_create_item(image_item, file_payloads, http_client)
        image_source, license_note, alt_text = _metadata_or_400(
            image_item.license,
            image_item.source,
            image_item.license_note,
            image_item.alt_text,
        )
        attachment: SlideImageAttachment = SlideImageAttachment(
            payload=payload,
            intake=intake,
            image_license=image_item.license,
            source=image_source,
            license_note=license_note,
            alt_text=alt_text,
        )
        attachments.append(attachment)

    return attachments


def create_slide_with_images(
    carousel_id: uuid.UUID,
    slide_write_request: SlideWriteRequest,
    attachments: list[SlideImageAttachment],
    our_database_session: Session,
    image_store: LocalAlbumImageStore,
) -> SlideReadResponse:
    """Store the slide and every image in one commit, or store nothing.

    Args:
        carousel_id: Album id.
        slide_write_request: Name, skeleton text, and excluded slide ids.
        attachments: Images for this slide. Empty is allowed when the
            text or a field gives the slide content.
        our_database_session: Open session.
        image_store: Disk store. Bytes stay under ``ARTIFACT_STORAGE_DIR``.

    Returns:
        The new slide, including its images.

    Raises:
        HTTPException: The slide would be empty, or an image fails the
            license, type, or size gate. No row and no file remain.
    """

    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )

    if not skeleton_requires_image(found_skeleton):
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

    slide_name: str = _require_name(slide_write_request.name)
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_skeleton,
        slide_write_request.texts,
    )
    staged_images: list[tuple[PreparedSlideImage, SlideImageAttachment]] = []

    for attachment in attachments:
        _metadata_or_400(
            attachment.image_license,
            attachment.source,
            attachment.license_note,
            attachment.alt_text,
        )

        try:
            prepared_image: PreparedSlideImage = prepare_image_bytes(attachment.payload)
        except ImageIntakeError as intake_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=intake_error.detail,
            ) from intake_error

        staged_images.append((prepared_image, attachment))

    _require_image_when_skeleton_needs_one(found_skeleton, len(staged_images))
    slide_id: uuid.UUID = new_row_id()
    excluded_ids: list[uuid.UUID] = _parsed_exclusions(
        slide_id,
        slide_write_request.excluded_slide_ids,
        found_source,
    )
    next_position: int = _next_slide_position(found_source.id, our_database_session)
    saved_paths: list[str] = []

    image_album: Album = ensure_carousel_album(found_source, our_database_session)

    try:
        created_images: list[AlbumImage] = [
            _materialize_slide_image(
                found_source.id,
                slide_id,
                image_album,
                prepared_image,
                attachment,
                image_store,
                saved_paths,
            )
            for prepared_image, attachment in staged_images
        ]
    except Exception:
        _delete_saved_paths(image_store, saved_paths)

        raise

    created_slide: Slide = Slide(
        id=slide_id,
        carousel_id=found_source.id,
        position=next_position,
        name=slide_name,
    )
    created_slide.images = created_images
    created_slide.element_texts = []
    created_slide.exclusions = []
    created_slide.text_status = SlideTextStatus.LIVE
    our_database_session.add(created_slide)
    _store_exclusion_pairs(
        created_slide,
        excluded_ids,
        found_source,
        our_database_session,
    )

    for created_image in created_images:
        our_database_session.add(created_image)

    _replace_texts(created_slide, stored_texts, our_database_session)

    try:
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail="Slide could not be saved.",
        )
    except Exception:
        _delete_saved_paths(image_store, saved_paths)

        raise

    our_database_session.refresh(created_slide)

    from app.api.v1.carousels import serialize_slide

    return serialize_slide(created_slide)


def _payload_for_create_item(
    image_item: SlideImageCreateItem,
    file_payloads: list[bytes],
    http_client: httpx.Client,
) -> tuple[bytes, SlideImageIntake]:
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

        return file_payloads[file_index], SlideImageIntake.UPLOAD

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

    return downloaded, SlideImageIntake.URL


def _materialize_slide_image(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    album: Album,
    prepared_image: PreparedSlideImage,
    attachment: SlideImageAttachment,
    image_store: LocalAlbumImageStore,
    saved_paths: list[str],
) -> AlbumImage:
    """Write one original and its thumbnail onto the carousel's album."""

    image_id: uuid.UUID = new_row_id()
    relative_path: str = album_image_relative_path(
        carousel_id,
        slide_id,
        image_id,
        prepared_image.extension,
    )
    thumbnail_path: str | None = None
    saved_paths.append(relative_path)
    image_store.save(relative_path, prepared_image.payload)

    if prepared_image.thumbnail_jpeg is not None:
        thumbnail_path = album_thumbnail_relative_path(carousel_id, slide_id, image_id)
        saved_paths.append(thumbnail_path)
        image_store.save(thumbnail_path, prepared_image.thumbnail_jpeg)

    created_image: AlbumImage = AlbumImage(
        id=image_id,
        album_id=album.id,
        position=next_album_image_position(album),
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
    album.images.append(created_image)

    return created_image


def add_images_from_payloads(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    payloads: list[bytes],
    image_license: SlideImageLicense,
    source: str,
    alt_text: str | None,
    license_note: str,
    intake: SlideImageIntake,
    our_database_session: Session,
    image_store: LocalAlbumImageStore,
) -> list[SlideImageReadResponse]:
    """Validate every file, then write rows and bytes. A failure writes nothing.

    Args:
        carousel_id: Album id.
        slide_id: Slide that will own the images.
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

    found_slide: Slide = _fetch_slide_or_raise(carousel_id, slide_id, our_database_session)
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )

    if not skeleton_requires_image(found_skeleton):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=IMAGE_NOT_USED_DETAIL,
        )

    if len(payloads) != 1 or len(list(found_slide.images)) > 0:
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
    prepared_images: list[PreparedSlideImage] = _prepare_all_or_400(payloads)
    image_album: Album = ensure_carousel_album(found_source, our_database_session)
    saved_paths: list[str] = []

    try:
        created_rows: list[AlbumImage] = _write_prepared_images(
            found_slide,
            image_album,
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

    from app.api.v1.carousels import serialize_image

    created_responses: list[SlideImageReadResponse] = [
        serialize_image(created_row) for created_row in created_rows
    ]

    return created_responses


def get_slide_image_thumbnail(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream the JPEG thumbnail. SVG and packaged defaults have none.

    Readers may call this.
    """

    found_image: AlbumImage = _fetch_image_or_raise(
        carousel_id,
        slide_id,
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
    image_license: SlideImageLicense,
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


def _prepare_all_or_400(payloads: list[bytes]) -> list[PreparedSlideImage]:
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

    prepared_images: list[PreparedSlideImage] = []

    for payload in payloads:

        try:
            prepared_image: PreparedSlideImage = prepare_image_bytes(payload)
        except ImageIntakeError as intake_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=intake_error.detail,
            ) from intake_error

        prepared_images.append(prepared_image)

    return prepared_images


def _write_prepared_images(
    slide: Slide,
    album: Album,
    prepared_images: list[PreparedSlideImage],
    image_license: SlideImageLicense,
    image_source: str,
    license_note: str,
    alt_text: str | None,
    intake: SlideImageIntake,
    image_store: LocalAlbumImageStore,
    our_database_session: Session,
    saved_paths: list[str],
) -> list[AlbumImage]:
    """Write files then album rows. ``saved_paths`` records what to undo."""

    created_rows: list[AlbumImage] = []

    for prepared_image in prepared_images:
        created_image: AlbumImage = _materialize_slide_image(
            slide.carousel_id,
            slide.id,
            album,
            prepared_image,
            SlideImageAttachment(
                payload=b"",
                intake=intake,
                image_license=image_license,
                source=image_source,
                license_note=license_note,
                alt_text=alt_text,
            ),
            image_store,
            saved_paths,
        )
        our_database_session.add(created_image)
        created_rows.append(created_image)

    if len(created_rows) == 1:
        slide.images = created_rows

    return created_rows


def _delete_saved_paths(image_store: LocalAlbumImageStore, saved_paths: list[str]) -> None:
    """Remove files written for a batch that did not commit."""

    for relative_path in saved_paths:
        image_store.delete(relative_path)
