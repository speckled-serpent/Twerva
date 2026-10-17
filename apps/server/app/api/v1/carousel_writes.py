"""Create, rename, change the open step, attach one album, and delete.

No new image bytes on the slide routes. The skeleton stays the one
chosen at create. Slide upload still creates an album when the
carousel does not have one.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    CarouselAlbumAttachRequest,
    CarouselAlbumCreateRequest,
    CarouselCreateRequest,
    CarouselPatchRequest,
    CarouselReadResponse,
    CarouselStepPatchRequest,
    SlideImageMetadataPatch,
    SlideImageReadResponse,
    SlideElementTextWrite,
    SlideReadResponse,
    SlideWriteRequest,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.album import Album, AlbumImage
from app.models.carousel import (
    CAROUSEL_EDITOR_STEP_DEFAULT,
    CAROUSEL_GENERATION_NUMBER_DEFAULT,
    Carousel,
    Slide,
    SlideElementText,
    SlideExclusion,
)
from app.models.enums import SlideImageMediaType, SlideTextStatus
from app.models.skeleton import Skeleton
from app.models.ops_user import OpsUser
from app.settings import get_settings
from app.albums.linking import (
    SLIDES_STILL_POINT_AT_ALBUM_DETAIL,
    slides_point_at_album,
)
from app.carousels.editing import (
    ALBUM_IN_USE_DETAIL,
    BLANK_NAME_DETAIL,
    IMAGE_IN_USE_DETAIL,
    SLIDE_IN_USE_DETAIL,
    allocate_unique_source_slug,
    in_use_detail,
    new_row_id,
    normalize_image_metadata,
    slugify_carousel_name,
    stored_paths_in_use,
)
from app.carousels.slide_exclusions import normalized_exclusion_ids
from app.carousels.slide_skeleton import (
    IMAGE_REQUIRED_DETAIL,
    CarouselStepStates,
    accepted_editor_step,
    carousel_step_states,
    skeleton_requires_image,
    text_values_for_skeleton,
)
from app.storage.artifacts import ArtifactAssetPathEscapeError
from app.skeletons.default_images import resolve_skeleton_image_path


IMAGE_MEDIA_TYPES: dict[SlideImageMediaType, str] = {
    SlideImageMediaType.JPEG: "image/jpeg",
    SlideImageMediaType.PNG: "image/png",
    SlideImageMediaType.SVG: "image/svg+xml",
}
CAROUSEL_SLUG_CONFLICT_DETAIL: str = "A carousel with that name already exists."


def register_source_write_routes(carousels_router: APIRouter) -> None:
    """Attach album and slide writes, plus the packaged image stream."""

    carousels_router.add_api_route(
        "",
        create_carousel,
        methods=["POST"],
        response_model=CarouselReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    carousels_router.add_api_route(
        "/{carousel_id}",
        patch_carousel,
        methods=["PATCH"],
        response_model=CarouselReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/step",
        patch_carousel_step,
        methods=["PATCH"],
        response_model=CarouselReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/album",
        put_carousel_album,
        methods=["PUT"],
        response_model=CarouselReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/album",
        post_carousel_album,
        methods=["POST"],
        response_model=CarouselReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/album",
        delete_carousel_album,
        methods=["DELETE"],
        response_model=CarouselReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}",
        delete_carousel,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides",
        create_slide,
        methods=["POST"],
        response_model=SlideReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}",
        patch_slide,
        methods=["PATCH"],
        response_model=SlideReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}",
        delete_slide,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/images/{image_id}",
        patch_slide_image_metadata,
        methods=["PATCH"],
        response_model=SlideImageReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/images/{image_id}",
        delete_slide_image,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/images/{image_id}/file",
        get_slide_image_file,
        methods=["GET"],
    )


def create_carousel(
    source_create_request: CarouselCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Create a carousel bound to a skeleton. Readers cannot call this.

    Generation and the open step use the column defaults: generation 1
    and editor step 3.
    """

    _ = current_ops_operator
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        source_create_request.skeleton_id,
        our_database_session,
    )
    album_name: str = _require_name(source_create_request.name)
    taken_slugs: set[str] = set(
        our_database_session.scalars(select(Carousel.slug)).all(),
    )
    album_slug: str = allocate_unique_source_slug(
        slugify_carousel_name(album_name),
        taken_slugs,
    )
    created_source: Carousel = Carousel(
        id=new_row_id(),
        skeleton_id=source_create_request.skeleton_id,
        name=album_name,
        slug=album_slug,
        inspiration="",
        rules="",
        generation_number=CAROUSEL_GENERATION_NUMBER_DEFAULT,
        editor_step=CAROUSEL_EDITOR_STEP_DEFAULT,
    )
    created_source.slides = []
    created_source.research_links = []
    our_database_session.add(created_source)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=CAROUSEL_SLUG_CONFLICT_DETAIL,
    )
    our_database_session.refresh(created_source)

    from app.api.v1.carousels import serialize_carousel

    return serialize_carousel(created_source, found_skeleton)


def patch_carousel(
    carousel_id: uuid.UUID,
    source_patch_request: CarouselPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Rename a carousel."""

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )
    updated_name: str = _require_name(source_patch_request.name)
    found_source.name = updated_name
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=CAROUSEL_SLUG_CONFLICT_DETAIL,
    )
    our_database_session.refresh(found_source)

    from app.api.v1.carousels import serialize_carousel

    return serialize_carousel(found_source, found_skeleton)


def patch_carousel_step(
    carousel_id: uuid.UUID,
    step_patch_request: CarouselStepPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Store the open step. A locked step is 400 and leaves the row.

    Readers cannot call this. Create still uses the column default,
    so a new carousel opens at step 3. The skeleton is not changed.
    """

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )
    stored_step: int = _accepted_editor_step(found_source, found_skeleton, step_patch_request)
    found_source.editor_step = stored_step
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Editor step could not be saved.",
    )
    our_database_session.refresh(found_source)

    from app.api.v1.carousels import serialize_carousel

    return serialize_carousel(found_source, found_skeleton)


def put_carousel_album(
    carousel_id: uuid.UUID,
    album_attach_request: CarouselAlbumAttachRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Point the carousel at an existing album.

    Readers cannot call this. An unknown album is 404. Replacing the
    attached album is 409 while a slide on this carousel still points
    at an image in the album being left, including the Default album.
    The stored album stays on 409. Pointing at the album already
    attached is allowed. The response steps follow the album rule.
    """

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_album: Album = _fetch_album_or_raise(
        album_attach_request.album_id,
        our_database_session,
    )
    _reject_when_leaving_album_in_use(
        found_source,
        found_album.id,
        our_database_session,
    )
    _point_carousel_at_album(found_source, found_album)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Album could not be attached.",
    )
    our_database_session.refresh(found_source)

    return _read_carousel(found_source, our_database_session)


def post_carousel_album(
    carousel_id: uuid.UUID,
    album_create_request: CarouselAlbumCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Create an album and point the carousel at it.

    The name and slug follow `POST /api/v1/albums`. A blank name is 400
    and creates nothing. Replacing the attached album is 409 while a
    slide still points at an image in the album being left, and that
    refusal does not create the new album. The response steps follow
    the album rule.
    """

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    album_name: str = _require_name(album_create_request.name)
    _reject_when_leaving_album_in_use(
        found_source,
        None,
        our_database_session,
    )
    created_album: Album = _create_named_album(album_name, our_database_session)
    _point_carousel_at_album(found_source, created_album)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Album could not be saved.",
    )
    our_database_session.refresh(found_source)
    our_database_session.refresh(created_album)

    return _read_carousel(found_source, our_database_session)


def delete_carousel_album(
    carousel_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Clear ``album_id`` and leave the album row and its files.

    Readers cannot call this. Clearing is 409 while a slide on this
    carousel still points at an image in the attached album, including
    the Default album. The stored album stays on 409. A carousel with
    no album is unchanged. The response steps follow the album rule.
    """

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    _reject_when_leaving_album_in_use(
        found_source,
        None,
        our_database_session,
    )

    if found_source.album_id is not None:
        found_source.album = None
        found_source.album_id = None
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail="Album could not be detached.",
        )
        our_database_session.refresh(found_source)

    return _read_carousel(found_source, our_database_session)


def delete_carousel(
    carousel_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete an album. 409 when any of its image paths is still in use."""

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    _reject_when_paths_in_use(
        our_database_session,
        _image_paths_on_source(found_source),
        ALBUM_IN_USE_DETAIL,
    )
    our_database_session.delete(found_source)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Carousel could not be deleted.",
    )


def create_slide(
    carousel_id: uuid.UUID,
    slide_write_request: SlideWriteRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideReadResponse:
    """Add a slide. A skeleton that needs an image is 400 here."""

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )
    slide_name: str = _require_name(slide_write_request.name)
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_skeleton,
        slide_write_request.texts,
    )
    created_slide_id: uuid.UUID = new_row_id()
    excluded_ids: list[uuid.UUID] = _parsed_exclusions(
        created_slide_id,
        slide_write_request.excluded_slide_ids,
        found_source,
    )
    _require_image_when_skeleton_needs_one(found_skeleton, 0)
    next_position: int = _next_slide_position(found_source.id, our_database_session)
    created_slide: Slide = Slide(
        id=created_slide_id,
        carousel_id=found_source.id,
        position=next_position,
        name=slide_name,
    )
    created_slide.images = []
    created_slide.element_texts = []
    created_slide.exclusions = []
    created_slide.text_status = SlideTextStatus.LIVE
    _replace_texts(created_slide, stored_texts, our_database_session)
    our_database_session.add(created_slide)
    _store_exclusion_pairs(created_slide, excluded_ids, found_source, our_database_session)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slide could not be saved.",
    )
    our_database_session.refresh(created_slide)

    from app.api.v1.carousels import serialize_slide

    return serialize_slide(created_slide)


def patch_slide(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    slide_write_request: SlideWriteRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideReadResponse:
    """Replace the name and skeleton text. Images are not changed here."""

    _ = current_ops_operator
    found_slide: Slide = _fetch_slide_or_raise(carousel_id, slide_id, our_database_session)
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )
    slide_name: str = _require_name(slide_write_request.name)
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_skeleton,
        slide_write_request.texts,
    )
    excluded_ids: list[uuid.UUID] = _parsed_exclusions(
        found_slide.id,
        slide_write_request.excluded_slide_ids,
        found_source,
    )
    _require_image_when_skeleton_needs_one(found_skeleton, len(list(found_slide.images)))
    found_slide.name = slide_name

    if found_slide.text_status == SlideTextStatus.DRAFT:
        _store_draft_texts(found_slide, stored_texts, our_database_session)
    else:
        _replace_texts(found_slide, stored_texts, our_database_session)
        found_slide.text_status = SlideTextStatus.LIVE

    _replace_exclusion_pairs(found_slide, excluded_ids, found_source, our_database_session)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slide could not be saved.",
    )
    our_database_session.refresh(found_slide)

    from app.api.v1.carousels import serialize_slide

    return serialize_slide(found_slide)


def delete_slide(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete a slide. 409 when one of its image paths is still in use."""

    _ = current_ops_operator
    found_slide: Slide = _fetch_slide_or_raise(carousel_id, slide_id, our_database_session)
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    _reject_when_paths_in_use(
        our_database_session,
        _image_paths_on_slide(found_slide),
        SLIDE_IN_USE_DETAIL,
    )
    _clear_exclusion_pairs(found_slide, found_source, our_database_session)
    our_database_session.delete(found_slide)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slide could not be deleted.",
    )


def patch_slide_image_metadata(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_id: uuid.UUID,
    image_patch_request: SlideImageMetadataPatch,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideImageReadResponse:
    """Update license, source, alt, and note. A bad license writes nothing."""

    _ = current_ops_operator
    found_image: AlbumImage = _fetch_image_or_raise(
        carousel_id,
        slide_id,
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

    from app.api.v1.carousels import serialize_image

    return serialize_image(found_image)


def delete_slide_image(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Delete one image row. 409 when a skeleton or artifact stores its path."""

    _ = current_ops_operator
    found_image: AlbumImage = _fetch_image_or_raise(
        carousel_id,
        slide_id,
        image_id,
        our_database_session,
    )
    _reject_when_paths_in_use(
        our_database_session,
        {found_image.relative_path},
        IMAGE_IN_USE_DETAIL,
    )
    found_slide: Slide = _fetch_slide_or_raise(carousel_id, slide_id, our_database_session)
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )
    remaining_images: int = len(list(found_slide.images)) - 1
    _require_image_when_skeleton_needs_one(found_skeleton, remaining_images)
    stored_files: list[tuple[str, str | None]] = [
        (found_image.relative_path, found_image.thumbnail_path),
    ]
    found_slide.images = []
    our_database_session.delete(found_image)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Image could not be deleted.",
    )
    _discard_stored_files(stored_files)


def get_slide_image_file(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream an existing image. ``theme-defaults/`` is read from the package.

    Readers may call this. This route does not upload or thumbnail.
    """

    found_image: AlbumImage = _fetch_image_or_raise(
        carousel_id,
        slide_id,
        image_id,
        our_database_session,
    )
    storage_directory: Path = Path(get_settings().artifact_storage_dir)

    try:
        image_path: Path = resolve_skeleton_image_path(
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


def _accepted_editor_step(
    carousel: Carousel,
    skeleton: Skeleton,
    step_patch_request: CarouselStepPatchRequest,
) -> int:
    """Return a step that may be stored. A refusal writes nothing.

    Args:
        carousel: The carousel row, with slides loaded.
        skeleton: That carousel's skeleton, with elements loaded.
        step_patch_request: The requested open step.

    Returns:
        0, 2, or 3 when that step is open.

    Raises:
        HTTPException: 400 when the step is locked or is not stored.
    """

    step_states: CarouselStepStates = carousel_step_states(
        skeleton,
        carousel.album_id,
        len(list(carousel.slides)),
    )

    try:
        stored_step: int = accepted_editor_step(
            step_patch_request.editor_step,
            step_states,
        )
    except ValueError as step_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(step_error),
        ) from step_error

    return stored_step


def _reject_when_leaving_album_in_use(
    carousel: Carousel,
    next_album_id: uuid.UUID | None,
    our_database_session: Session,
) -> None:
    """409 when this change would leave an album a slide still points at.

    Clearing, or pointing at a different album, leaves the current album.
    Pointing at that same album does not. Slides on other carousels do
    not count. The caller has not written yet.

    Args:
        carousel: The carousel being changed, with slides loaded.
        next_album_id: The album that will be attached. Null clears the
            pointer, or stands in for an album that will be created.
        our_database_session: Open session.

    Raises:
        HTTPException: 409 while a slide on this carousel points at an
            image in the album being left.
    """

    leaving_album_id: uuid.UUID | None = carousel.album_id

    if leaving_album_id is None or leaving_album_id == next_album_id:

        return

    slides_still_point: bool = slides_point_at_album(
        carousel,
        leaving_album_id,
        our_database_session,
    )

    if not slides_still_point:

        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=SLIDES_STILL_POINT_AT_ALBUM_DETAIL,
    )


def _fetch_album_or_raise(album_id: uuid.UUID, our_database_session: Session) -> Album:
    """Return an album, or 404. Same detail as the album routes."""

    from app.api.v1.albums import _fetch_album_or_raise as fetch_album_or_raise

    found_album: Album = fetch_album_or_raise(album_id, our_database_session)

    return found_album


def _create_named_album(album_name: str, our_database_session: Session) -> Album:
    """Build an empty album with the same slug rules as ``POST /albums``.

    The name is already stripped. The caller adds the carousel pointer
    and commits both rows together.

    Args:
        album_name: Stripped album name.
        our_database_session: Open session.

    Returns:
        The new album, added to the session and not yet committed.
    """

    from app.api.v1.albums import _new_album

    created_album: Album = _new_album(album_name, our_database_session)
    our_database_session.add(created_album)

    return created_album


def _point_carousel_at_album(carousel: Carousel, album: Album) -> None:
    """Store the one album pointer. The caller commits."""

    carousel.album = album
    carousel.album_id = album.id


def _read_carousel(
    carousel: Carousel,
    our_database_session: Session,
) -> CarouselReadResponse:
    """Return the detail. ``steps`` follows the album now stored."""

    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        carousel.skeleton_id,
        our_database_session,
    )

    from app.api.v1.carousels import serialize_carousel

    carousel_response: CarouselReadResponse = serialize_carousel(carousel, found_skeleton)

    return carousel_response


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
    skeleton: Skeleton,
    text_writes: list[SlideElementTextWrite],
) -> list[tuple[uuid.UUID, str]]:
    """Return one value per text element. A foreign element id is 400."""

    submitted_texts: list[tuple[uuid.UUID, str]] = [
        (text_write.skeleton_element_id, text_write.value)
        for text_write in text_writes
    ]

    try:
        stored_texts: list[tuple[uuid.UUID, str]] = text_values_for_skeleton(
            skeleton,
            submitted_texts,
        )
    except ValueError as text_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(text_error),
        ) from text_error

    return stored_texts


def _require_image_when_skeleton_needs_one(skeleton: Skeleton, image_count: int) -> None:
    """400 when a picture skeleton would be left without its slide image."""

    if not skeleton_requires_image(skeleton) or image_count > 0:

        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=IMAGE_REQUIRED_DETAIL,
    )


def _parsed_image_metadata(
    image_patch_request: SlideImageMetadataPatch,
) -> tuple[str, str, str | None]:
    """Return carousel, license note, and alt. Invalid license writes nothing."""

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
    """409, and do not delete, when a skeleton or artifact stores a path."""

    used_paths: set[str] = stored_paths_in_use(our_database_session, candidate_paths)

    if len(used_paths) == 0:

        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=in_use_detail(summary, used_paths),
    )


def _next_slide_position(carousel_id: uuid.UUID, our_database_session: Session) -> int:
    """Return the next position at the end of an album."""

    positions: list[int] = list(
        our_database_session.scalars(
            select(Slide.position).where(Slide.carousel_id == carousel_id),
        ).all(),
    )

    if len(positions) == 0:

        return 0

    next_position: int = max(positions) + 1

    return next_position


def _parsed_exclusions(
    slide_id: uuid.UUID,
    submitted_ids: list[uuid.UUID],
    carousel: Carousel,
) -> list[uuid.UUID]:
    """Return the other slide ids to store. A bad id is 400."""

    sibling_ids: set[uuid.UUID] = {
        sibling.id for sibling in list(carousel.slides) if sibling.id != slide_id
    }

    try:
        stored_ids: list[uuid.UUID] = normalized_exclusion_ids(
            slide_id,
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
    slide: Slide,
    excluded_ids: list[uuid.UUID],
    carousel: Carousel,
    our_database_session: Session,
) -> None:
    """Write both directions of each new pair."""

    for excluded_id in excluded_ids:
        _append_exclusion(slide, excluded_id, our_database_session)
        partner: Slide | None = _sibling_slide(carousel, excluded_id)

        if partner is None:
            continue

        _append_exclusion(partner, slide.id, our_database_session)


def _replace_exclusion_pairs(
    slide: Slide,
    excluded_ids: list[uuid.UUID],
    carousel: Carousel,
    our_database_session: Session,
) -> None:
    """Replace every pair that names this slide, in both directions."""

    _clear_exclusion_pairs(slide, carousel, our_database_session)
    _store_exclusion_pairs(slide, excluded_ids, carousel, our_database_session)


def _clear_exclusion_pairs(
    slide: Slide,
    carousel: Carousel,
    our_database_session: Session,
) -> None:
    """Drop pairs that name this slide from every slide in the carousel."""

    for sibling in list(carousel.slides):
        kept_rows: list[SlideExclusion] = []

        for exclusion in list(sibling.exclusions):
            names_slide: bool = (
                exclusion.slide_id == slide.id or exclusion.excluded_slide_id == slide.id
            )

            if names_slide:
                our_database_session.delete(exclusion)
            else:
                kept_rows.append(exclusion)

        sibling.exclusions = kept_rows


def _append_exclusion(
    slide: Slide,
    excluded_slide_id: uuid.UUID,
    our_database_session: Session,
) -> None:
    """Add one direction if this slide does not already store it."""

    for exclusion in list(slide.exclusions):

        if exclusion.excluded_slide_id == excluded_slide_id:

            return

    created_exclusion: SlideExclusion = SlideExclusion(
        id=new_row_id(),
        slide_id=slide.id,
        excluded_slide_id=excluded_slide_id,
    )
    slide.exclusions.append(created_exclusion)
    our_database_session.add(created_exclusion)


def _sibling_slide(carousel: Carousel, slide_id: uuid.UUID) -> Slide | None:
    """Return a slide on this carousel, or null."""

    for sibling in list(carousel.slides):

        if sibling.id == slide_id:

            return sibling

    return None


def _store_draft_texts(
    slide: Slide,
    stored_texts: list[tuple[uuid.UUID, str]],
    our_database_session: Session,
) -> None:
    """Write draft copy beside the live value. Live text stays."""

    existing_by_element: dict[uuid.UUID, SlideElementText] = {
        element_text.skeleton_element_id: element_text
        for element_text in list(slide.element_texts)
    }

    for skeleton_element_id, value in stored_texts:
        existing_text: SlideElementText | None = existing_by_element.get(skeleton_element_id)

        if existing_text is None:
            created_text: SlideElementText = SlideElementText(
                id=new_row_id(),
                slide_id=slide.id,
                skeleton_element_id=skeleton_element_id,
                value="",
                draft_value=value,
            )
            slide.element_texts.append(created_text)
            our_database_session.add(created_text)
        else:
            existing_text.draft_value = value


def _replace_texts(
    slide: Slide,
    stored_texts: list[tuple[uuid.UUID, str]],
    our_database_session: Session,
) -> None:
    """Replace skeleton text. One row per text element, including blanks.

    The delete is flushed before the new rows. Postgres rejects a second
    row for the same slide and skeleton element while the old row is still
    pending.
    """

    for existing_text in list(slide.element_texts):
        our_database_session.delete(existing_text)

    slide.element_texts = []
    our_database_session.flush()

    for skeleton_element_id, value in stored_texts:
        created_text: SlideElementText = SlideElementText(
            id=new_row_id(),
            slide_id=slide.id,
            skeleton_element_id=skeleton_element_id,
            value=value,
            draft_value=None,
        )
        slide.element_texts.append(created_text)
        our_database_session.add(created_text)


def _fetch_slide_or_raise(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    our_database_session: Session,
) -> Slide:
    """Return a slide on this album, or 404."""

    found_slide: Slide | None = our_database_session.get(Slide, slide_id)

    if found_slide is None or found_slide.carousel_id != carousel_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Slide not found: {slide_id}",
        )

    return found_slide


def _fetch_image_or_raise(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_id: uuid.UUID,
    our_database_session: Session,
) -> AlbumImage:
    """Return the album image this slide points at, or 404."""

    found_slide: Slide = _fetch_slide_or_raise(carousel_id, slide_id, our_database_session)
    found_image: AlbumImage | None = our_database_session.get(AlbumImage, image_id)
    pointed_image_id: uuid.UUID | None = found_slide.album_image_id

    if pointed_image_id is None and found_slide.album_image is not None:
        pointed_image_id = found_slide.album_image.id

    if found_image is None or pointed_image_id != found_image.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image not found: {image_id}",
        )

    return found_image


def _discard_stored_files(stored_files: list[tuple[str, str | None]]) -> None:
    """Delete album bytes after the row commit. Package files stay."""

    from app.carousels.image_store import LocalAlbumImageStore, configured_album_image_store

    image_store: LocalAlbumImageStore = configured_album_image_store()

    for relative_path, thumbnail_path in stored_files:
        image_store.delete(relative_path)

        if thumbnail_path is not None:
            image_store.delete(thumbnail_path)


def _stored_files_on_slide(slide: Slide) -> list[tuple[str, str | None]]:
    """Return original and thumbnail paths for one slide."""

    stored_files: list[tuple[str, str | None]] = [
        (image.relative_path, image.thumbnail_path) for image in slide.images
    ]

    return stored_files


def _stored_files_on_source(carousel: Carousel) -> list[tuple[str, str | None]]:
    """Return original and thumbnail paths for every image in an album."""

    stored_files: list[tuple[str, str | None]] = []

    for slide in carousel.slides:
        stored_files.extend(_stored_files_on_slide(slide))

    return stored_files


def _image_paths_on_slide(slide: Slide) -> set[str]:
    """Return every image path stored on a slide."""

    image_paths: set[str] = {image.relative_path for image in slide.images}

    return image_paths


def _image_paths_on_source(carousel: Carousel) -> set[str]:
    """Return every image path stored in an album."""

    image_paths: set[str] = set()

    for slide in carousel.slides:
        image_paths.update(_image_paths_on_slide(slide))

    return image_paths
