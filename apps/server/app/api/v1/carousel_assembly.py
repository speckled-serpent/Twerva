"""Assemble a carousel's live slides into review rows and serve the PNGs."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.schemas import CarouselReadResponse
from app.auth.dependencies import (
    require_admin_ops_operator,
    require_authenticated_ops_operator,
)
from app.carousels.final_assembly import assemble_carousel_final
from app.db import get_our_database_session
from app.models.carousel import AssembledCarouselFrame, Carousel
from app.models.ops_user import OpsUser
from app.models.skeleton import Skeleton
from app.publish.errors import PublishMediaPathEscapeError
from app.publish.media import resolve_asset_reference_path
from app.settings import get_settings
from app.storage.artifacts import ensure_artifact_storage_directory


FRAME_NOT_FOUND_DETAIL: str = "Frame not found."
FRAME_FILE_MISSING_DETAIL: str = "Frame file is missing."
PNG_MEDIA_TYPE: str = "image/png"


def register_carousel_assembly_routes(carousels_router: APIRouter) -> None:
    """Attach the Final assembly routes.

    Args:
        carousels_router: Router mounted at ``/carousels``.
    """

    carousels_router.add_api_route(
        "/{carousel_id}/assemble",
        assemble_carousel,
        methods=["POST"],
        response_model=CarouselReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/assembly/frames/{frame_id}/file",
        get_assembled_frame_file,
        methods=["GET"],
    )


def assemble_carousel(
    carousel_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Draw the live slides and return the carousel detail.

    Readers cannot call this. The body is empty.
    """

    _ = current_ops_operator
    carousel: Carousel = assemble_carousel_final(carousel_id, our_database_session)
    skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        carousel.skeleton_id,
        our_database_session,
    )

    from app.api.v1.carousels import serialize_carousel

    detail: CarouselReadResponse = serialize_carousel(carousel, skeleton)

    return detail


def get_assembled_frame_file(
    carousel_id: uuid.UUID,
    frame_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> FileResponse:
    """Stream one frozen frame PNG.

    Readers may call this. The frame is not drawn again, and the album
    file is not opened.
    """

    _ = current_ops_operator
    carousel: Carousel = fetch_carousel_by_id_or_raise(carousel_id, our_database_session)
    frame: AssembledCarouselFrame | None = _frame_on_carousel(carousel, frame_id)

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=FRAME_NOT_FOUND_DETAIL,
        )

    storage_directory: Path = ensure_artifact_storage_directory(
        Path(get_settings().artifact_storage_dir),
    )

    try:
        frame_path: Path = resolve_asset_reference_path(frame.asset_ref, storage_directory)
    except PublishMediaPathEscapeError as escape_error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=FRAME_NOT_FOUND_DETAIL,
        ) from escape_error

    if not frame_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=FRAME_FILE_MISSING_DETAIL,
        )

    frame_response: FileResponse = FileResponse(path=frame_path, media_type=PNG_MEDIA_TYPE)

    return frame_response


def _frame_on_carousel(
    carousel: Carousel,
    frame_id: uuid.UUID,
) -> AssembledCarouselFrame | None:
    """Return the frame when it belongs to this carousel."""

    for assembly in list(carousel.assemblies):

        for assembled in list(assembly.assembled_carousels):

            for frame in list(assembled.frames):

                if frame.id == frame_id:

                    return frame

    return None
