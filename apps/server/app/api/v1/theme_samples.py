"""Theme sample previews. One frame, no artifact row, no post job."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_source_item_by_id_or_raise,
    fetch_theme_by_id_or_raise,
)
from app.api.v1.schemas import (
    ThemeSampleOverlapResponse,
    ThemeSampleRequest,
    ThemeSampleResponse,
)
from app.db import get_our_database_session
from app.models import SourceItem, SourceType, Theme
from app.settings import get_settings
from app.themes.overlap import BandOverlap
from app.themes.samples import (
    ThemeSampleBlockReason,
    ThemeSampleRender,
    render_theme_sample,
    resolve_theme_preview_file,
    write_theme_preview_png,
)


SPOTMU_INTEREST_REQUIRED_DETAIL: str = "Source item must be a Spotmu interest."


def register_theme_sample_routes(themes_router: APIRouter) -> None:
    """Attach sample routes to the theme router.

    Args:
        themes_router: Router mounted at ``/themes``.
    """

    themes_router.add_api_route(
        "/{theme_id}/samples",
        create_theme_sample,
        methods=["POST"],
        response_model=ThemeSampleResponse,
        status_code=status.HTTP_201_CREATED,
    )
    themes_router.add_api_route(
        "/{theme_id}/samples/{preview_id}/image",
        get_theme_sample_image,
        methods=["GET"],
    )


def create_theme_sample(
    theme_id: uuid.UUID,
    theme_sample_request: ThemeSampleRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> ThemeSampleResponse:
    """Render one preview PNG. Does not approve, schedule, or publish.

    The source item must be a Spotmu interest. Draft and Live themes
    both render. Theme status is left as it was. No artifact row and no
    post job row are inserted.
    """

    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    found_source_item: SourceItem = fetch_source_item_by_id_or_raise(
        theme_sample_request.source_item_id,
        our_database_session,
    )

    if found_source_item.source_type != SourceType.SPOTMU_INTEREST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SPOTMU_INTEREST_REQUIRED_DETAIL,
        )

    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    rendered_sample: ThemeSampleRender = render_theme_sample(
        found_theme,
        found_source_item,
        artifact_storage_directory,
    )
    preview_id: uuid.UUID = uuid.uuid4()
    write_theme_preview_png(
        found_theme.id,
        preview_id,
        rendered_sample.png_bytes,
        artifact_storage_directory,
    )
    sample_response: ThemeSampleResponse = _sample_response(preview_id, rendered_sample)

    return sample_response


def get_theme_sample_image(
    theme_id: uuid.UUID,
    preview_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream one preview PNG for a signed-in operator.

    Readers may GET. A missing theme or file is 404.
    """

    fetch_theme_by_id_or_raise(theme_id, our_database_session)
    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    preview_path: Path | None = resolve_theme_preview_file(
        theme_id,
        preview_id,
        artifact_storage_directory,
    )

    if preview_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preview image not found: {theme_id} {preview_id}",
        )

    preview_image_response: FileResponse = FileResponse(
        path=preview_path,
        media_type="image/png",
    )

    return preview_image_response


def _sample_response(
    preview_id: uuid.UUID,
    rendered_sample: ThemeSampleRender,
) -> ThemeSampleResponse:
    """Map the renderer result onto the HTTP body."""

    overlap_responses: list[ThemeSampleOverlapResponse] = [
        _overlap_response(overlap) for overlap in rendered_sample.overlaps
    ]
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None = (
        _block_reason_literal(rendered_sample.block_reason)
    )
    sample_response: ThemeSampleResponse = ThemeSampleResponse(
        preview_id=preview_id,
        blocked=rendered_sample.blocked,
        block_reason=block_reason,
        detail=rendered_sample.detail,
        overlaps=overlap_responses,
    )

    return sample_response


def _overlap_response(overlap: BandOverlap) -> ThemeSampleOverlapResponse:
    """Copy one overlap pair. Element ids stay in band order."""

    element_ids: list[uuid.UUID] = [overlap.element_ids[0], overlap.element_ids[1]]
    overlap_response: ThemeSampleOverlapResponse = ThemeSampleOverlapResponse(
        band_a=overlap.band_a,
        band_b=overlap.band_b,
        element_ids=element_ids,
    )

    return overlap_response


def _block_reason_literal(
    block_reason: ThemeSampleBlockReason | None,
) -> Literal["overlap", "missing_asset", "measure_error"] | None:
    """Return the response string for a block reason."""

    if block_reason is None:

        return None

    if block_reason == ThemeSampleBlockReason.OVERLAP:

        return "overlap"

    if block_reason == ThemeSampleBlockReason.MISSING_ASSET:

        return "missing_asset"

    return "measure_error"
