"""Render one slide on its carousel skeleton. No artifact row is written."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.schemas import SkeletonPreviewResponse, SlidePreviewRequest
from app.api.v1.carousel_writes import _fetch_slide_or_raise, _parsed_texts
from app.api.v1.skeleton_samples import _preview_response
from app.auth.dependencies import require_authenticated_ops_operator
from app.db import get_our_database_session
from app.models.album import AlbumImage
from app.models.carousel import Carousel, Slide
from app.models.ops_user import OpsUser
from app.models.skeleton import Skeleton
from app.settings import get_settings
from app.carousels.slide_skeleton import SlideSkeletonFill, skeleton_requires_image
from app.skeletons.samples import SkeletonSampleRender, render_skeleton_sample


def register_source_preview_routes(carousels_router: APIRouter) -> None:
    """Attach the in-carousel preview route.

    Args:
        carousels_router: Router mounted at ``/carousels``.
    """

    carousels_router.add_api_route(
        "/{carousel_id}/slides/preview",
        preview_slide_on_skeleton,
        methods=["POST"],
        response_model=SkeletonPreviewResponse,
        status_code=status.HTTP_200_OK,
    )


def preview_slide_on_skeleton(
    carousel_id: uuid.UUID,
    preview_request: SlidePreviewRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> SkeletonPreviewResponse:
    """Draw the carousel skeleton with this slide's text and image.

    Readers may call this. The PNG is inline. No slide, artifact, post
    job, or preview file is written.
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
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_skeleton,
        preview_request.texts,
    )
    image_path: str | None = _saved_image_path(
        carousel_id,
        preview_request.slide_id,
        our_database_session,
        skeleton_requires_image(found_skeleton),
    )
    slide_fill: SlideSkeletonFill = SlideSkeletonFill(
        text_by_element_id={
            element_id: value for element_id, value in stored_texts
        },
        slide_image_relative_path=image_path,
    )
    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    rendered_sample: SkeletonSampleRender = render_skeleton_sample(
        found_skeleton,
        None,
        artifact_storage_directory,
        slide_fill,
    )
    preview_response: SkeletonPreviewResponse = _preview_response(rendered_sample)

    return preview_response


def _saved_image_path(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID | None,
    our_database_session: Session,
    skeleton_needs_image: bool,
) -> str | None:
    """Return the slide's stored image path when the skeleton uses one."""

    if not skeleton_needs_image or slide_id is None:

        return None

    found_slide: Slide = _fetch_slide_or_raise(carousel_id, slide_id, our_database_session)
    images: list[AlbumImage] = list(found_slide.images)

    if len(images) == 0:

        return None

    image_path: str = images[0].relative_path

    return image_path
