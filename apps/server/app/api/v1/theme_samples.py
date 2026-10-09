"""Theme sample previews. One frame, no artifact row, no post job."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
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
    ThemeElementCreateRequest,
    ThemePreviewRequest,
    ThemePreviewResponse,
    ThemeSampleOverlapResponse,
    ThemeSampleRequest,
    ThemeSampleResponse,
)
from app.db import get_our_database_session
from app.models import (
    AdvertisementType,
    SourceItem,
    SourceType,
    Theme,
    ThemeElement,
)
from app.models.enums import ThemeElementBand
from app.settings import get_settings
from app.themes.elements import (
    THEME_ELEMENT_SORT_ORDER_DETAIL,
    ResolvedThemeElement,
    ThemeElementError,
    insert_index,
    resolve_theme_element,
)
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
        "/preview",
        create_theme_preview,
        methods=["POST"],
        response_model=ThemePreviewResponse,
        status_code=status.HTTP_200_OK,
    )
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


def create_theme_preview(
    theme_preview_request: ThemePreviewRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> ThemePreviewResponse:
    """Render one frame from the form payload. Does not write a row.

    Readers and admins may call this. The PNG is returned inline. A
    missing font uses the sample renderer's Pillow fallback. No theme,
    artifact, post job, or preview file is created.
    """

    found_source_item: SourceItem = fetch_source_item_by_id_or_raise(
        theme_preview_request.source_item_id,
        our_database_session,
    )

    if found_source_item.source_type != SourceType.SPOTMU_INTEREST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SPOTMU_INTEREST_REQUIRED_DETAIL,
        )

    _reject_negative_preview_spacing(theme_preview_request)
    preview_theme: Theme = _preview_theme(theme_preview_request)
    _append_preview_elements(preview_theme, theme_preview_request.elements)
    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    rendered_sample: ThemeSampleRender = render_theme_sample(
        preview_theme,
        found_source_item,
        artifact_storage_directory,
    )
    preview_response: ThemePreviewResponse = _preview_response(rendered_sample)

    return preview_response


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


def _preview_response(rendered_sample: ThemeSampleRender) -> ThemePreviewResponse:
    """Map a render onto the inline PNG response. No preview id is stored."""

    encoded_png: str = base64.b64encode(rendered_sample.png_bytes).decode("ascii")
    overlap_responses: list[ThemeSampleOverlapResponse] = [
        _overlap_response(overlap) for overlap in rendered_sample.overlaps
    ]
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None = (
        _block_reason_literal(rendered_sample.block_reason)
    )
    preview_response: ThemePreviewResponse = ThemePreviewResponse(
        blocked=rendered_sample.blocked,
        block_reason=block_reason,
        detail=rendered_sample.detail,
        overlaps=overlap_responses,
        image_png_base64=encoded_png,
    )

    return preview_response


def _preview_theme(theme_preview_request: ThemePreviewRequest) -> Theme:
    """Build an unsaved theme. The caller does not add it to a session."""

    gradient_payload: dict[str, object] | None = None

    if theme_preview_request.background_gradient is not None:
        gradient_payload = theme_preview_request.background_gradient.model_dump()

    preview_theme: Theme = Theme(
        id=uuid.uuid4(),
        name="Preview",
        slug="preview",
        advertisement_type=AdvertisementType.CAROUSEL,
        template_key=None,
        status=theme_preview_request.status,
        page_margin=theme_preview_request.page_margin,
        element_gap=theme_preview_request.element_gap,
        element_margin=theme_preview_request.element_margin,
        background_kind=theme_preview_request.background_kind,
        background_color=theme_preview_request.background_color,
        background_gradient=gradient_payload,
        background_asset_ref=theme_preview_request.background_asset_ref,
        created_by=None,
    )
    preview_theme.elements = []

    return preview_theme


def _append_preview_elements(
    preview_theme: Theme,
    element_requests: list[ThemeElementCreateRequest],
) -> None:
    """Validate elements and attach them in band order. No flush."""

    resolved_rows: list[tuple[ThemeElementCreateRequest, ResolvedThemeElement]] = []

    for element_request in element_requests:
        _reject_negative_preview_sort_order(element_request.sort_order)
        resolved_element: ResolvedThemeElement = _resolve_preview_element(element_request)
        resolved_rows.append((element_request, resolved_element))

    members_by_band: dict[ThemeElementBand, list[ThemeElement]] = {
        ThemeElementBand.TOP: [],
        ThemeElementBand.MIDDLE: [],
        ThemeElementBand.BOTTOM: [],
    }
    created_at: datetime = datetime.now(timezone.utc)

    for element_request, resolved_element in resolved_rows:
        created_element: ThemeElement = ThemeElement(
            id=uuid.uuid4(),
            theme_id=preview_theme.id,
            band=element_request.band,
            sort_order=0,
            content_kind=resolved_element.content_kind,
            rectangle_color=resolved_element.rectangle_color,
            rectangle_opacity=resolved_element.rectangle_opacity,
            rectangle_radius=resolved_element.rectangle_radius,
            text_source=resolved_element.text_source,
            font_family=resolved_element.font_family,
            font_size=resolved_element.font_size,
            font_color=resolved_element.font_color,
            bold=resolved_element.bold,
            italic=resolved_element.italic,
            underline=resolved_element.underline,
            strikethrough=resolved_element.strikethrough,
            font_weight=resolved_element.font_weight,
            alignment=resolved_element.alignment,
            image_asset_ref=resolved_element.image_asset_ref,
            created_at=created_at,
            updated_at=created_at,
        )
        band_members: list[ThemeElement] = members_by_band[element_request.band]
        target_index: int = insert_index(element_request.sort_order, len(band_members))
        band_members.insert(target_index, created_element)

    for band_members in members_by_band.values():

        for sort_order, band_member in enumerate(band_members):
            band_member.sort_order = sort_order
            preview_theme.elements.append(band_member)


def _resolve_preview_element(
    element_request: ThemeElementCreateRequest,
) -> ResolvedThemeElement:
    """Validate one preview element. A rule failure is HTTP 400."""

    try:
        resolved_element: ResolvedThemeElement = resolve_theme_element(
            element_request.content_kind,
            element_request.rectangle_color,
            element_request.text_source,
            element_request.font_family,
            element_request.font_size,
            element_request.font_color,
            _preview_flag(element_request.bold),
            _preview_flag(element_request.italic),
            _preview_flag(element_request.underline),
            _preview_flag(element_request.strikethrough),
            element_request.font_weight,
            element_request.alignment,
            element_request.image_asset_ref,
            element_request.rectangle_opacity,
            element_request.rectangle_radius,
        )
    except ThemeElementError as element_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=element_error.detail,
        ) from element_error

    return resolved_element


def _reject_negative_preview_spacing(theme_preview_request: ThemePreviewRequest) -> None:
    """Reject a negative margin or gap before drawing."""

    spacing_values: tuple[tuple[str, int], ...] = (
        ("page_margin", theme_preview_request.page_margin),
        ("element_gap", theme_preview_request.element_gap),
        ("element_margin", theme_preview_request.element_margin),
    )

    for field_name, spacing_value in spacing_values:

        if spacing_value < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be zero or greater.",
            )


def _reject_negative_preview_sort_order(sort_order: int | None) -> None:
    """Reject a negative index. None appends within the band."""

    if sort_order is None:

        return

    if sort_order < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=THEME_ELEMENT_SORT_ORDER_DETAIL,
        )


def _preview_flag(flag_value: bool | None) -> bool:
    """Default an omitted style flag to false."""

    if flag_value is None:

        return False

    return flag_value


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
