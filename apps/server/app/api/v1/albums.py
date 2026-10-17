"""Album list, create, autosave, image intake, and delete."""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.albums.linking import next_album_image_position
from app.api.v1.carousel_writes import IMAGE_MEDIA_TYPES, _discard_stored_files, _reject_when_paths_in_use
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    AlbumCreateRequest,
    AlbumImageReadResponse,
    AlbumImageWrite,
    AlbumListItemResponse,
    AlbumPatchRequest,
    AlbumReadResponse,
    SlideImageImportRequest,
)
from app.auth.dependencies import require_admin_ops_operator
from app.carousels.editing import (
    ALBUM_IN_USE_DETAIL,
    BLANK_NAME_DETAIL,
    allocate_unique_source_slug,
    new_row_id,
    normalize_image_metadata,
    slugify_carousel_name,
)
from app.carousels.image_intake import (
    ImageIntakeError,
    PreparedSlideImage,
    download_image_once,
    prepare_image_bytes,
)
from app.carousels.image_store import (
    LocalAlbumImageStore,
    configured_album_image_store,
    library_image_relative_path,
    library_thumbnail_relative_path,
)
from app.db import get_our_database_session
from app.models.album import Album, AlbumImage
from app.models.enums import SlideImageIntake, SlideImageLicense
from app.models.ops_user import OpsUser
from app.settings import get_settings
from app.skeletons.default_images import resolve_skeleton_image_path
from app.storage.artifacts import ArtifactAssetPathEscapeError


albums_router: APIRouter = APIRouter(prefix="/albums", tags=["albums"])

IMAGE_LIST_MISMATCH_DETAIL: str = "Send every image in this album, in the new order."
CHOOSE_IMAGE_FILE_DETAIL: str = "Choose an image file."


def albums_list_statement() -> Select[tuple[Album]]:
    """Return every album, ordered by name, with images loaded."""

    statement: Select[tuple[Album]] = (
        select(Album)
        .options(selectinload(Album.images))
        .order_by(Album.name.asc(), Album.slug.asc())
    )

    return statement


@albums_router.get("", response_model=list[AlbumListItemResponse])
def list_albums(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[AlbumListItemResponse]:
    """Return albums. Readers may call this."""

    albums: list[Album] = list(our_database_session.scalars(albums_list_statement()).all())
    list_items: list[AlbumListItemResponse] = [
        serialize_album_list_item(album) for album in albums
    ]

    return list_items


@albums_router.post("", response_model=AlbumReadResponse, status_code=status.HTTP_201_CREATED)
def create_album(
    album_create_request: AlbumCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> AlbumReadResponse:
    """Create an empty album. Readers cannot call this."""

    _ = current_ops_operator
    album_name: str = _require_name(album_create_request.name)
    created_album: Album = _new_album(album_name, our_database_session)
    our_database_session.add(created_album)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Album could not be saved.",
    )
    our_database_session.refresh(created_album)

    return serialize_album(created_album)


@albums_router.get("/{album_id}", response_model=AlbumReadResponse)
def get_album(
    album_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> AlbumReadResponse:
    """Return one album and its images. A missing id is HTTP 404."""

    found_album: Album = _fetch_album_or_raise(album_id, our_database_session)

    return serialize_album(found_album)


@albums_router.patch("/{album_id}", response_model=AlbumReadResponse)
def patch_album(
    album_id: uuid.UUID,
    album_patch_request: AlbumPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> AlbumReadResponse:
    """Save the name, image order, and license fields. Readers cannot call this."""

    _ = current_ops_operator
    found_album: Album = _fetch_album_or_raise(album_id, our_database_session)
    album_name: str = _require_name(album_patch_request.name)
    ordered_writes: list[AlbumImageWrite] = list(album_patch_request.images)
    images_by_id: dict[uuid.UUID, AlbumImage] = {
        image.id: image for image in list(found_album.images)
    }
    _require_same_image_ids(images_by_id, ordered_writes)

    found_album.name = album_name
    parked_base: int = 0

    if len(images_by_id) > 0:
        parked_base = max(image.position for image in images_by_id.values()) + 1

    for offset, image_write in enumerate(ordered_writes):
        parked_image: AlbumImage = images_by_id[image_write.id]
        parked_image.position = parked_base + offset

    our_database_session.flush()

    for position, image_write in enumerate(ordered_writes):
        found_image: AlbumImage = images_by_id[image_write.id]
        image_source, license_note, alt_text = _parsed_image_metadata(image_write)
        found_image.position = position
        found_image.license = image_write.license
        found_image.source = image_source
        found_image.license_note = license_note
        found_image.alt_text = alt_text

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Album could not be saved.",
    )
    our_database_session.refresh(found_album)

    return serialize_album(found_album)


@albums_router.delete("/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_album(
    album_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete an album. 409 when a skeleton or artifact still stores a path."""

    _ = current_ops_operator
    found_album: Album = _fetch_album_or_raise(album_id, our_database_session)
    image_paths: set[str] = {image.relative_path for image in list(found_album.images)}
    _reject_when_paths_in_use(our_database_session, image_paths, ALBUM_IN_USE_DETAIL)
    stored_files: list[tuple[str, str | None]] = [
        (image.relative_path, image.thumbnail_path) for image in list(found_album.images)
    ]
    our_database_session.delete(found_album)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Album could not be deleted.",
    )
    _discard_stored_files(stored_files)


@albums_router.post(
    "/{album_id}/images",
    response_model=AlbumImageReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_album_image(
    album_id: uuid.UUID,
    file: UploadFile = File(...),
    image_license: SlideImageLicense = Form(..., alias="license"),
    source: str = Form(...),
    alt_text: str | None = Form(None),
    license_note: str = Form(""),
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> AlbumImageReadResponse:
    """Store one file on the album. Readers cannot call this."""

    _ = current_ops_operator
    payload: bytes = file.file.read()

    if payload == b"":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CHOOSE_IMAGE_FILE_DETAIL,
        )

    created_image: AlbumImage = _store_album_image(
        album_id,
        payload,
        image_license,
        source,
        alt_text,
        license_note,
        SlideImageIntake.UPLOAD,
        our_database_session,
        configured_album_image_store(),
    )

    return serialize_album_image(created_image)


@albums_router.post(
    "/{album_id}/images/import",
    response_model=AlbumImageReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_album_image(
    album_id: uuid.UUID,
    image_import_request: SlideImageImportRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> AlbumImageReadResponse:
    """Download one URL onto the album. The request is not fetched again later."""

    _ = current_ops_operator

    try:
        with httpx.Client() as http_client:
            payload: bytes = download_image_once(image_import_request.url, http_client)
    except ImageIntakeError as intake_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=intake_error.detail,
        ) from intake_error

    created_image: AlbumImage = _store_album_image(
        album_id,
        payload,
        image_import_request.license,
        image_import_request.source,
        image_import_request.alt_text,
        image_import_request.license_note,
        SlideImageIntake.URL,
        our_database_session,
        configured_album_image_store(),
    )

    return serialize_album_image(created_image)


@albums_router.delete(
    "/{album_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_album_image(
    album_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Remove one image. 409 when a skeleton or artifact stores its path."""

    _ = current_ops_operator
    found_image: AlbumImage = _fetch_image_or_raise(album_id, image_id, our_database_session)
    _reject_when_paths_in_use(
        our_database_session,
        {found_image.relative_path},
        "This image is still used by a skeleton or an artifact.",
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


@albums_router.get("/{album_id}/images/{image_id}/file")
def get_album_image_file(
    album_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream an album image. ``theme-defaults/`` is read from the package."""

    found_image: AlbumImage = _fetch_image_or_raise(album_id, image_id, our_database_session)

    return _file_response(found_image.relative_path, IMAGE_MEDIA_TYPES[found_image.media_type])


@albums_router.get("/{album_id}/images/{image_id}/thumbnail")
def get_album_image_thumbnail(
    album_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream the JPEG thumbnail. SVG and packaged defaults have none."""

    found_image: AlbumImage = _fetch_image_or_raise(album_id, image_id, our_database_session)

    if found_image.thumbnail_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This image has no thumbnail.",
        )

    return _file_response(found_image.thumbnail_path, "image/jpeg")


def serialize_album_list_item(album: Album) -> AlbumListItemResponse:
    """Return the list shape, with a count and no image bodies."""

    list_item: AlbumListItemResponse = AlbumListItemResponse(
        id=album.id,
        name=album.name,
        slug=album.slug,
        image_count=len(list(album.images)),
        created_at=album.created_at,
        updated_at=album.updated_at,
    )

    return list_item


def serialize_album(album: Album) -> AlbumReadResponse:
    """Return one album with images in position order."""

    ordered_images: list[AlbumImage] = sorted(list(album.images), key=_image_position)
    album_response: AlbumReadResponse = AlbumReadResponse(
        id=album.id,
        name=album.name,
        slug=album.slug,
        created_at=album.created_at,
        updated_at=album.updated_at,
        images=[serialize_album_image(image) for image in ordered_images],
    )

    return album_response


def serialize_album_image(image: AlbumImage) -> AlbumImageReadResponse:
    """Return one album image, including license and the concrete path."""

    image_response: AlbumImageReadResponse = AlbumImageReadResponse(
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


def _image_position(image: AlbumImage) -> int:
    """Return the sort key for an album image."""

    position: int = image.position

    return position


def _new_album(album_name: str, our_database_session: Session) -> Album:
    """Build an album with a unique slug. The caller commits."""

    taken_slugs: set[str] = set(our_database_session.scalars(select(Album.slug)).all())
    album_slug: str = allocate_unique_source_slug(
        slugify_carousel_name(album_name),
        taken_slugs,
    )
    created_album: Album = Album(
        id=new_row_id(),
        name=album_name,
        slug=album_slug,
    )
    created_album.images = []

    return created_album


def _require_name(raw_name: str) -> str:
    """Return a stripped name, or 400 when it is blank."""

    album_name: str = raw_name.strip()

    if album_name == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=BLANK_NAME_DETAIL,
        )

    return album_name


def _require_same_image_ids(
    images_by_id: dict[uuid.UUID, AlbumImage],
    ordered_writes: list[AlbumImageWrite],
) -> None:
    """Reject a patch that adds, drops, or repeats an image id."""

    submitted_ids: list[uuid.UUID] = [image_write.id for image_write in ordered_writes]
    submitted_set: set[uuid.UUID] = set(submitted_ids)

    if len(submitted_ids) != len(submitted_set) or submitted_set != set(images_by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=IMAGE_LIST_MISMATCH_DETAIL,
        )


def _parsed_image_metadata(image_write: AlbumImageWrite) -> tuple[str, str, str | None]:
    """Return cleaned license fields, or 400."""

    try:
        cleaned_metadata: tuple[str, str, str | None] = normalize_image_metadata(
            image_write.license,
            image_write.source,
            image_write.license_note,
            image_write.alt_text,
        )
    except ValueError as metadata_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(metadata_error),
        ) from metadata_error

    return cleaned_metadata


def _fetch_album_or_raise(album_id: uuid.UUID, our_database_session: Session) -> Album:
    """Return an album, or 404."""

    found_album: Album | None = our_database_session.get(Album, album_id)

    if found_album is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Album not found: {album_id}",
        )

    return found_album


def _fetch_image_or_raise(
    album_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session,
) -> AlbumImage:
    """Return an image on this album, or 404."""

    found_image: AlbumImage | None = our_database_session.get(AlbumImage, image_id)

    if found_image is None or found_image.album_id != album_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image not found: {image_id}",
        )

    return found_image


def _store_album_image(
    album_id: uuid.UUID,
    payload: bytes,
    image_license: SlideImageLicense,
    source: str,
    alt_text: str | None,
    license_note: str,
    intake: SlideImageIntake,
    our_database_session: Session,
    image_store: LocalAlbumImageStore,
) -> AlbumImage:
    """Validate one file, then write the row and the bytes."""

    found_album: Album = _fetch_album_or_raise(album_id, our_database_session)
    image_source, cleaned_note, cleaned_alt = _metadata_from_parts(
        image_license,
        source,
        license_note,
        alt_text,
    )

    try:
        prepared_image: PreparedSlideImage = prepare_image_bytes(payload)
    except ImageIntakeError as intake_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=intake_error.detail,
        ) from intake_error

    image_id: uuid.UUID = new_row_id()
    relative_path: str = library_image_relative_path(
        found_album.id,
        image_id,
        prepared_image.extension,
    )
    saved_paths: list[str] = [relative_path]
    thumbnail_path: str | None = None

    try:
        image_store.save(relative_path, prepared_image.payload)

        if prepared_image.thumbnail_jpeg is not None:
            thumbnail_path = library_thumbnail_relative_path(found_album.id, image_id)
            saved_paths.append(thumbnail_path)
            image_store.save(thumbnail_path, prepared_image.thumbnail_jpeg)

        created_image: AlbumImage = AlbumImage(
            id=image_id,
            album_id=found_album.id,
            position=next_album_image_position(found_album),
            relative_path=relative_path,
            media_type=prepared_image.media_type,
            byte_size=len(prepared_image.payload),
            width=prepared_image.width,
            height=prepared_image.height,
            alt_text=cleaned_alt,
            license=image_license,
            source=image_source,
            license_note=cleaned_note,
            intake=intake,
            thumbnail_path=thumbnail_path,
        )
        found_album.images.append(created_image)
        our_database_session.add(created_image)
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail="Image could not be saved.",
        )
    except Exception:
        _delete_saved_paths(image_store, saved_paths)

        raise

    our_database_session.refresh(created_image)

    return created_image


def _metadata_from_parts(
    image_license: SlideImageLicense,
    source: str,
    license_note: str,
    alt_text: str | None,
) -> tuple[str, str, str | None]:
    """Return cleaned license fields, or 400."""

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


def _delete_saved_paths(image_store: LocalAlbumImageStore, saved_paths: list[str]) -> None:
    """Remove files written for a batch that did not commit."""

    for relative_path in saved_paths:
        image_store.delete(relative_path)


def _file_response(relative_path: str, media_type: str) -> FileResponse:
    """Stream one stored path, or 404 when the file is missing."""

    storage_directory: Path = Path(get_settings().artifact_storage_dir)

    try:
        image_path: Path = resolve_skeleton_image_path(relative_path, storage_directory)
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

    image_response: FileResponse = FileResponse(path=image_path, media_type=media_type)

    return image_response
