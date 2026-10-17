"""Skeleton sample previews. One frame, no artifact row, no post job."""

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
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.schemas import (
    SkeletonElementCreateRequest,
    SkeletonPreviewElementRequest,
    SkeletonPreviewRequest,
    SkeletonPreviewResponse,
    SkeletonSampleOverlapResponse,
    SkeletonSampleRequest,
    SkeletonSampleResponse,
)
from app.db import get_our_database_session
from app.models import (
    AdvertisementType,
    SourceItem,
    SourceType,
    Skeleton,
    SkeletonElement,
)
from app.models.enums import SkeletonElementBand, SkeletonElementContentKind
from app.settings import get_settings
from app.skeletons.elements import (
    SKELETON_ELEMENT_SORT_ORDER_DETAIL,
    ResolvedSkeletonElement,
    SkeletonElementError,
    insert_index,
    resolve_skeleton_element,
)
from app.skeletons.overlap import BandOverlap
from app.skeletons.samples import (
    SkeletonSampleBlockReason,
    SkeletonSampleRender,
    render_skeleton_sample,
    resolve_skeleton_preview_file,
    write_skeleton_preview_png,
)


SPOTMU_INTEREST_REQUIRED_DETAIL: str = "Source item must be a Spotmu interest."


def register_skeleton_sample_routes(skeletons_router: APIRouter) -> None:
    """Attach sample routes to the skeleton router.

    Args:
        skeletons_router: Router mounted at ``/skeletons``.
    """

    skeletons_router.add_api_route(
        "/preview",
        create_skeleton_preview,
        methods=["POST"],
        response_model=SkeletonPreviewResponse,
        status_code=status.HTTP_200_OK,
    )
    skeletons_router.add_api_route(
        "/{skeleton_id}/samples",
        create_skeleton_sample,
        methods=["POST"],
        response_model=SkeletonSampleResponse,
        status_code=status.HTTP_201_CREATED,
    )
    skeletons_router.add_api_route(
        "/{skeleton_id}/samples/{preview_id}/image",
        get_skeleton_sample_image,
        methods=["GET"],
    )


def create_skeleton_sample(
    skeleton_id: uuid.UUID,
    skeleton_sample_request: SkeletonSampleRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> SkeletonSampleResponse:
    """Render one preview PNG. Does not approve, schedule, or publish.

    The source item must be a Spotmu interest. Draft and Live skeletons
    both render. Skeleton status is left as it was. No artifact row and no
    post job row are inserted.
    """

    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(skeleton_id, our_database_session)
    found_source_item: SourceItem = fetch_source_item_by_id_or_raise(
        skeleton_sample_request.source_item_id,
        our_database_session,
    )

    if found_source_item.source_type != SourceType.SPOTMU_INTEREST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SPOTMU_INTEREST_REQUIRED_DETAIL,
        )

    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    rendered_sample: SkeletonSampleRender = render_skeleton_sample(
        found_skeleton,
        found_source_item,
        artifact_storage_directory,
    )
    preview_id: uuid.UUID = uuid.uuid4()
    write_skeleton_preview_png(
        found_skeleton.id,
        preview_id,
        rendered_sample.png_bytes,
        artifact_storage_directory,
    )
    sample_response: SkeletonSampleResponse = _sample_response(preview_id, rendered_sample)

    return sample_response


def create_skeleton_preview(
    skeleton_preview_request: SkeletonPreviewRequest,
) -> SkeletonPreviewResponse:
    """Render one frame from the form payload. Does not write a row.

    Readers and admins may call this. The PNG is returned inline. A
    missing font uses the sample renderer's Pillow fallback. Text
    elements draw ``preview_text``. No skeleton, artifact, post job, or
    preview file is created, and no source item is loaded.
    """

    _reject_negative_preview_spacing(skeleton_preview_request)
    preview_skeleton: Skeleton = _preview_skeleton(skeleton_preview_request)
    preview_text_by_element_id: dict[uuid.UUID, str] = _append_preview_elements(
        preview_skeleton,
        skeleton_preview_request.elements,
    )
    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    rendered_sample: SkeletonSampleRender = render_skeleton_sample(
        preview_skeleton,
        None,
        artifact_storage_directory,
        preview_text_by_element_id=preview_text_by_element_id,
    )
    preview_response: SkeletonPreviewResponse = _preview_response(rendered_sample)

    return preview_response


def get_skeleton_sample_image(
    skeleton_id: uuid.UUID,
    preview_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream one preview PNG for a signed-in operator.

    Readers may GET. A missing skeleton or file is 404.
    """

    fetch_skeleton_by_id_or_raise(skeleton_id, our_database_session)
    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    preview_path: Path | None = resolve_skeleton_preview_file(
        skeleton_id,
        preview_id,
        artifact_storage_directory,
    )

    if preview_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preview image not found: {skeleton_id} {preview_id}",
        )

    preview_image_response: FileResponse = FileResponse(
        path=preview_path,
        media_type="image/png",
    )

    return preview_image_response


def _preview_response(rendered_sample: SkeletonSampleRender) -> SkeletonPreviewResponse:
    """Map a render onto the inline PNG response. No preview id is stored."""

    encoded_png: str = base64.b64encode(rendered_sample.png_bytes).decode("ascii")
    overlap_responses: list[SkeletonSampleOverlapResponse] = [
        _overlap_response(overlap) for overlap in rendered_sample.overlaps
    ]
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None = (
        _block_reason_literal(rendered_sample.block_reason)
    )
    preview_response: SkeletonPreviewResponse = SkeletonPreviewResponse(
        blocked=rendered_sample.blocked,
        block_reason=block_reason,
        detail=rendered_sample.detail,
        overlaps=overlap_responses,
        image_png_base64=encoded_png,
    )

    return preview_response


def _preview_skeleton(skeleton_preview_request: SkeletonPreviewRequest) -> Skeleton:
    """Build an unsaved skeleton. The caller does not add it to a session."""

    gradient_payload: dict[str, object] | None = None

    if skeleton_preview_request.background_gradient is not None:
        gradient_payload = skeleton_preview_request.background_gradient.model_dump()

    preview_skeleton: Skeleton = Skeleton(
        id=uuid.uuid4(),
        name="Preview",
        slug="preview",
        advertisement_type=AdvertisementType.CAROUSEL,
        template_key=None,
        status=skeleton_preview_request.status,
        page_margin=skeleton_preview_request.page_margin,
        element_gap=skeleton_preview_request.element_gap,
        element_margin=skeleton_preview_request.element_margin,
        background_kind=skeleton_preview_request.background_kind,
        background_color=skeleton_preview_request.background_color,
        background_gradient=gradient_payload,
        background_asset_ref=skeleton_preview_request.background_asset_ref,
        created_by=None,
    )
    preview_skeleton.elements = []

    return preview_skeleton


def _append_preview_elements(
    preview_skeleton: Skeleton,
    element_requests: list[SkeletonPreviewElementRequest],
) -> dict[uuid.UUID, str]:
    """Validate elements and attach them in band order. No flush.

    Returns:
        Preview text keyed by the unsaved element id. Only text elements
        with ``preview_text`` set are included. Nothing is stored.
    """

    resolved_rows: list[tuple[SkeletonPreviewElementRequest, ResolvedSkeletonElement]] = []
    preview_text_by_element_id: dict[uuid.UUID, str] = {}

    for element_request in element_requests:
        _reject_negative_preview_sort_order(element_request.sort_order)
        resolved_element: ResolvedSkeletonElement = _resolve_preview_element(element_request)
        resolved_rows.append((element_request, resolved_element))

    members_by_band: dict[SkeletonElementBand, list[SkeletonElement]] = {
        SkeletonElementBand.TOP: [],
        SkeletonElementBand.MIDDLE: [],
        SkeletonElementBand.BOTTOM: [],
    }
    created_at: datetime = datetime.now(timezone.utc)

    for element_request, resolved_element in resolved_rows:
        created_element_id: uuid.UUID = uuid.uuid4()
        created_element: SkeletonElement = SkeletonElement(
            id=created_element_id,
            skeleton_id=preview_skeleton.id,
            band=element_request.band,
            sort_order=0,
            content_kind=resolved_element.content_kind,
            name=element_request.name,
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

        if (
            resolved_element.content_kind == SkeletonElementContentKind.TEXT
            and element_request.preview_text is not None
        ):
            preview_text_by_element_id[created_element_id] = element_request.preview_text

        band_members: list[SkeletonElement] = members_by_band[element_request.band]
        target_index: int = insert_index(element_request.sort_order, len(band_members))
        band_members.insert(target_index, created_element)

    for band_members in members_by_band.values():

        for sort_order, band_member in enumerate(band_members):
            band_member.sort_order = sort_order
            preview_skeleton.elements.append(band_member)

    return preview_text_by_element_id


def _resolve_preview_element(
    element_request: SkeletonElementCreateRequest,
) -> ResolvedSkeletonElement:
    """Validate one preview element. A rule failure is HTTP 400."""

    try:
        resolved_element: ResolvedSkeletonElement = resolve_skeleton_element(
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
    except SkeletonElementError as element_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=element_error.detail,
        ) from element_error

    return resolved_element


def _reject_negative_preview_spacing(skeleton_preview_request: SkeletonPreviewRequest) -> None:
    """Reject a negative margin or gap before drawing."""

    spacing_values: tuple[tuple[str, int], ...] = (
        ("page_margin", skeleton_preview_request.page_margin),
        ("element_gap", skeleton_preview_request.element_gap),
        ("element_margin", skeleton_preview_request.element_margin),
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
            detail=SKELETON_ELEMENT_SORT_ORDER_DETAIL,
        )


def _preview_flag(flag_value: bool | None) -> bool:
    """Default an omitted style flag to false."""

    if flag_value is None:

        return False

    return flag_value


def _sample_response(
    preview_id: uuid.UUID,
    rendered_sample: SkeletonSampleRender,
) -> SkeletonSampleResponse:
    """Map the renderer result onto the HTTP body."""

    overlap_responses: list[SkeletonSampleOverlapResponse] = [
        _overlap_response(overlap) for overlap in rendered_sample.overlaps
    ]
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None = (
        _block_reason_literal(rendered_sample.block_reason)
    )
    sample_response: SkeletonSampleResponse = SkeletonSampleResponse(
        preview_id=preview_id,
        blocked=rendered_sample.blocked,
        block_reason=block_reason,
        detail=rendered_sample.detail,
        overlaps=overlap_responses,
    )

    return sample_response


def _overlap_response(overlap: BandOverlap) -> SkeletonSampleOverlapResponse:
    """Copy one overlap pair. Element ids stay in band order."""

    element_ids: list[uuid.UUID] = [overlap.element_ids[0], overlap.element_ids[1]]
    overlap_response: SkeletonSampleOverlapResponse = SkeletonSampleOverlapResponse(
        band_a=overlap.band_a,
        band_b=overlap.band_b,
        element_ids=element_ids,
    )

    return overlap_response


def _block_reason_literal(
    block_reason: SkeletonSampleBlockReason | None,
) -> Literal["overlap", "missing_asset", "measure_error"] | None:
    """Return the response string for a block reason."""

    if block_reason is None:

        return None

    if block_reason == SkeletonSampleBlockReason.OVERLAP:

        return "overlap"

    if block_reason == SkeletonSampleBlockReason.MISSING_ASSET:

        return "missing_asset"

    return "measure_error"
