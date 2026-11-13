"""Draw one live slide on its skeleton and store the PNG.

The frame text is the live ``value`` on each text element. A Spotmu
interest is not consulted. Overlap, a missing file, and a measure
error still write the PNG. This module does not insert a row and does
not call the template carousel renderer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.carousels.slide_skeleton import SlideSkeletonFill
from app.models.carousel import Slide
from app.models.skeleton import Skeleton
from app.publish.media import resolve_asset_reference_path
from app.skeletons.samples import SkeletonSampleRender, render_skeleton_sample
from app.storage.artifacts import ensure_artifact_storage_directory


@dataclass(frozen=True)
class AssembledFrameRender:
    """The stored frame path and whether the skeleton blocked it."""

    asset_ref: str
    blocked: bool
    block_reason: str | None
    block_detail: str | None


def assembled_frame_relative_path(assembly_id: uuid.UUID, frame_id: uuid.UUID) -> str:
    """Return ``assembled/{assembly_id}/{frame_id}.png``.

    Args:
        assembly_id: The assembly this frame belongs to.
        frame_id: The frame row id. Not an artifact id.

    Returns:
        Path relative to ``ARTIFACT_STORAGE_DIR``.
    """

    relative_path: str = f"assembled/{assembly_id}/{frame_id}.png"

    return relative_path


def slide_fill_from_live_slide(slide: Slide) -> SlideSkeletonFill:
    """Build the fill from live text and the album image path.

    Each text element contributes ``value``. ``draft_value`` is not
    read. The image path is the album image's ``relative_path``, or
    null when the slide has no album image.

    Args:
        slide: A live slide, with element texts and the album image
            loaded when they exist.

    Returns:
        The fill ``render_skeleton_sample`` draws. No row is written.
    """

    text_by_element_id: dict[uuid.UUID, str] = {
        element_text.skeleton_element_id: element_text.value
        for element_text in slide.element_texts
    }
    image_path: str | None = None

    if slide.album_image is not None:
        image_path = slide.album_image.relative_path

    fill: SlideSkeletonFill = SlideSkeletonFill(
        text_by_element_id=text_by_element_id,
        slide_image_relative_path=image_path,
    )

    return fill


def render_assembled_frame(
    skeleton: Skeleton,
    slide: Slide,
    artifact_storage_directory: Path,
    assembly_id: uuid.UUID,
    frame_id: uuid.UUID,
) -> AssembledFrameRender:
    """Draw the slide and write the PNG, including when the frame is blocked.

    ``render_skeleton_sample`` is called with this slide's fill and no
    source item, so a Spotmu interest is not drawn. The canvas is the
    skeleton frame, 1080 by 1920. The PNG is written under
    ``assembled/{assembly_id}/{frame_id}.png``.

    Args:
        skeleton: The carousel's skeleton, with elements loaded.
        slide: The live slide to draw.
        artifact_storage_directory: Configured store. Created if missing.
        assembly_id: Directory name under ``assembled``.
        frame_id: File name, without a directory prefix from the client.

    Returns:
        The relative path, whether the frame is blocked, the reason,
        and the detail. No database row is inserted.
    """

    resolved_storage_directory: Path = ensure_artifact_storage_directory(
        artifact_storage_directory,
    )
    fill: SlideSkeletonFill = slide_fill_from_live_slide(slide)
    rendered: SkeletonSampleRender = render_skeleton_sample(
        skeleton,
        None,
        resolved_storage_directory,
        fill,
    )
    relative_path: str = assembled_frame_relative_path(assembly_id, frame_id)
    destination_path: Path = resolve_asset_reference_path(
        relative_path,
        resolved_storage_directory,
    )
    destination_parent: Path = destination_path.parent
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(rendered.png_bytes)
    block_reason: str | None = None

    if rendered.block_reason is not None:
        block_reason = rendered.block_reason.value

    frame_render: AssembledFrameRender = AssembledFrameRender(
        asset_ref=relative_path,
        blocked=rendered.blocked,
        block_reason=block_reason,
        block_detail=rendered.detail,
    )

    return frame_render
