"""Group live slides for Final assembly and store the drawn frames.

``plan_final_groups`` does not read the database, draw frames, parse
instruction text, or call a model. ``assemble_carousel_final`` reads
the carousel's live slides, draws each frame, and writes the assembly
rows. It does not read instructions, research, or campaign interests,
and it does not publish.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.carousels.editing import new_row_id
from app.carousels.generations import ensure_current_generation
from app.carousels.final_render import (
    AssembledFrameRender,
    assembled_frame_relative_path,
    render_assembled_frame,
)
from app.carousels.slide_exclusions import assert_slide_pick_allowed
from app.carousels.slide_text_review import live_slides
from app.global_settings import slide_count_or_global_default
from app.models.campaign import CampaignPost
from app.models.carousel import (
    AssembledCarousel,
    AssembledCarouselFrame,
    Carousel,
    CarouselAssembly,
    CarouselGeneration,
    Slide,
)
from app.models.skeleton import Skeleton
from app.publish.errors import PublishMediaPathEscapeError
from app.publish.media import resolve_asset_reference_path
from app.settings import get_settings
from app.storage.artifacts import ensure_artifact_storage_directory


TOO_FEW_LIVE_SLIDES_DETAIL: str = "Add at least two live slides before assembly."
GENERATION_ON_TIMELINE_DETAIL: str = (
    "This generation is on a campaign timeline. Duplicate it before assembling again."
)
ASSEMBLY_STORE_CONFLICT_DETAIL: str = "Assembly could not be stored."
DRAFT_ASSEMBLY_STATUS: str = "draft"
MINIMUM_LIVE_SLIDES: int = 2


def plan_final_groups(
    live_slide_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
    slide_count: int,
) -> list[list[uuid.UUID]]:
    """Group live slides under a size cap, skipping excluded pairs.

    Slides stay in the order they were given. A slide joins the first
    group that still has room and that ``assert_slide_pick_allowed``
    accepts with this slide added. Otherwise it starts the next group.
    A slide alone is always one group. Both directions of a pair may
    be present. ``slide_count`` is the cap already chosen, at least 1.

    Args:
        live_slide_ids: Approved slides, in the caller's order. Drafts
            are already left out.
        exclusion_pairs: ``(slide_id, excluded_slide_id)`` rows. Both
            directions may be present.
        slide_count: Maximum slides in one group.

    Returns:
        One list of slide ids per group. Empty when nothing is live.
    """

    groups: list[list[uuid.UUID]] = []

    for slide_id in live_slide_ids:
        placed_slide: bool = False

        for group in groups:
            group_has_room: bool = len(group) < slide_count

            if not group_has_room:
                continue

            candidate_ids: list[uuid.UUID] = [*group, slide_id]
            candidate_allowed: bool = _pick_is_allowed(candidate_ids, exclusion_pairs)

            if not candidate_allowed:
                continue

            group.append(slide_id)
            placed_slide = True

            break

        if placed_slide:
            continue

        assert_slide_pick_allowed([slide_id], exclusion_pairs)
        groups.append([slide_id])

    return groups


def _pick_is_allowed(
    slide_ids: Sequence[uuid.UUID],
    exclusion_pairs: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> bool:
    """Return whether this pick contains no excluded pair."""

    try:
        assert_slide_pick_allowed(slide_ids, exclusion_pairs)
    except ValueError:

        return False

    return True


def assemble_carousel_final(
    carousel_id: uuid.UUID,
    our_database_session: Session,
) -> Carousel:
    """Draw the live slides and store one assembly for this generation.

    Fewer than two live slides writes nothing. Draft slides are left
    out. When a campaign post points at this assembly, the call raises
    409 and leaves the rows and PNG files where they are. A later call
    for the same generation, with no campaign post, keeps the assembly
    row, replaces its carousels and frames, and deletes the previous
    PNG files only after the new rows commit. A failure rolls the rows
    back and deletes PNGs written for the failed call.

    Args:
        carousel_id: Carousel to assemble.
        our_database_session: Open session. This function commits it.

    Returns:
        The carousel, with the assembly attached.

    Raises:
        HTTPException: The carousel is missing, fewer than two slides
            are live, or a campaign post points at this assembly.
    """

    carousel: Carousel = fetch_carousel_by_id_or_raise(carousel_id, our_database_session)
    skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        carousel.skeleton_id,
        our_database_session,
    )
    ordered_live_slides: list[Slide] = sorted(
        live_slides(list(carousel.slides)),
        key=_slide_order,
    )

    if len(ordered_live_slides) < MINIMUM_LIVE_SLIDES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=TOO_FEW_LIVE_SLIDES_DETAIL,
        )

    slide_count: int = slide_count_or_global_default(None)
    groups: list[list[uuid.UUID]] = plan_final_groups(
        [slide.id for slide in ordered_live_slides],
        _exclusion_pairs(list(carousel.slides)),
        slide_count,
    )
    storage_directory: Path = ensure_artifact_storage_directory(
        Path(get_settings().artifact_storage_dir),
    )
    existing_assembly: CarouselAssembly | None = _existing_assembly(carousel)

    if existing_assembly is not None:
        _raise_if_generation_is_on_a_timeline(
            existing_assembly,
            our_database_session,
        )

    assembly_id: uuid.UUID = new_row_id() if existing_assembly is None else existing_assembly.id
    previous_refs: list[str] = []

    if existing_assembly is not None:
        previous_refs = _frame_asset_refs(existing_assembly)

    slides_by_id: dict[uuid.UUID, Slide] = {slide.id: slide for slide in ordered_live_slides}
    new_refs: list[str] = []

    try:
        assembled_carousels: list[AssembledCarousel] = _draw_groups(
            assembly_id,
            groups,
            slides_by_id,
            skeleton,
            storage_directory,
            carousel.name,
            new_refs,
        )
        _store_groups(
            carousel,
            existing_assembly,
            assembly_id,
            slide_count,
            assembled_carousels,
            our_database_session,
        )
        commit_database_session_or_raise_conflict(
            our_database_session,
            ASSEMBLY_STORE_CONFLICT_DETAIL,
        )
    except Exception:
        _delete_asset_refs(new_refs, storage_directory)
        raise

    _delete_asset_refs(previous_refs, storage_directory)
    our_database_session.refresh(carousel)

    return carousel


def _raise_if_generation_is_on_a_timeline(
    assembly: CarouselAssembly,
    our_database_session: Session,
) -> None:
    """Refuse a new assemble when any campaign post uses this assembly.

    The check runs before frames are drawn and before child rows are
    replaced, so a refused call leaves the PNG files on disk.

    Args:
        assembly: The assembly for the carousel's current generation.
        our_database_session: Open session. This function does not commit.

    Raises:
        HTTPException: A campaign post points at one assembled carousel.
    """

    posted_ids: list[uuid.UUID] = list(
        our_database_session.scalars(
            select(CampaignPost.id)
            .join(
                AssembledCarousel,
                CampaignPost.assembled_carousel_id == AssembledCarousel.id,
            )
            .where(AssembledCarousel.assembly_id == assembly.id)
            .limit(1),
        ).all(),
    )

    if len(posted_ids) == 0:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=GENERATION_ON_TIMELINE_DETAIL,
    )


def _slide_order(slide: Slide) -> tuple[int, str]:
    """Return the campaign-run order: position, then id."""

    order: tuple[int, str] = (slide.position, str(slide.id))

    return order


def _exclusion_pairs(slides: Sequence[Slide]) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Return every stored exclusion pair, including both directions."""

    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []

    for slide in slides:

        for exclusion in list(slide.exclusions):
            pairs.append((exclusion.slide_id, exclusion.excluded_slide_id))

    return pairs


def _existing_assembly(carousel: Carousel) -> CarouselAssembly | None:
    """Return the assembly for this generation, or null on the first call."""

    for assembly in list(carousel.assemblies):

        if assembly.generation_number == carousel.generation_number:

            return assembly

    return None


def _store_groups(
    carousel: Carousel,
    existing_assembly: CarouselAssembly | None,
    assembly_id: uuid.UUID,
    slide_count: int,
    assembled_carousels: list[AssembledCarousel],
    our_database_session: Session,
) -> CarouselAssembly:
    """Replace the generation's children, creating the parent on the first call.

    The first call hangs the new row on the current generation's
    snapshot header. A later call keeps that ``generation_id`` and
    deletes the previous carousels before inserting the new ones.
    """

    assembly: CarouselAssembly
    current_generation: CarouselGeneration = ensure_current_generation(
        carousel,
        our_database_session,
    )

    if existing_assembly is None:
        assembly = CarouselAssembly(
            id=assembly_id,
            carousel_id=carousel.id,
            generation_id=current_generation.id,
            generation_number=carousel.generation_number,
            slide_count=slide_count,
        )
        current_generation.assembly = assembly
        carousel.assemblies.append(assembly)
        our_database_session.add(assembly)
    else:
        assembly = existing_assembly
        assembly.slide_count = slide_count
        assembly.assembled_carousels.clear()
        our_database_session.flush()

    for assembled in assembled_carousels:
        our_database_session.add(assembled)

        for frame in assembled.frames:
            our_database_session.add(frame)

    assembly.assembled_carousels.extend(assembled_carousels)

    return assembly


def _frame_asset_refs(assembly: CarouselAssembly) -> list[str]:
    """Return the PNG paths already stored on this assembly."""

    asset_refs: list[str] = []

    for assembled in list(assembly.assembled_carousels):

        for frame in list(assembled.frames):
            asset_refs.append(frame.asset_ref)

    return asset_refs


def _draw_groups(
    assembly_id: uuid.UUID,
    groups: Sequence[Sequence[uuid.UUID]],
    slides_by_id: dict[uuid.UUID, Slide],
    skeleton: Skeleton,
    storage_directory: Path,
    caption: str,
    new_refs: list[str],
) -> list[AssembledCarousel]:
    """Draw every group. ``new_refs`` collects paths already written."""

    assembled_carousels: list[AssembledCarousel] = []

    for group_position, slide_ids in enumerate(groups):
        assembled: AssembledCarousel = AssembledCarousel(
            id=new_row_id(),
            assembly_id=assembly_id,
            position=group_position,
            status=DRAFT_ASSEMBLY_STATUS,
            caption=caption,
            cta_url=None,
        )
        frames: list[AssembledCarouselFrame] = []

        for frame_position, slide_id in enumerate(slide_ids):
            frame: AssembledCarouselFrame = _draw_frame(
                assembled.id,
                frame_position,
                slides_by_id[slide_id],
                skeleton,
                storage_directory,
                assembly_id,
                new_refs,
            )
            frames.append(frame)

        assembled.frames = frames
        assembled_carousels.append(assembled)

    return assembled_carousels


def _draw_frame(
    assembled_carousel_id: uuid.UUID,
    position: int,
    slide: Slide,
    skeleton: Skeleton,
    storage_directory: Path,
    assembly_id: uuid.UUID,
    new_refs: list[str],
) -> AssembledCarouselFrame:
    """Draw one slide. A raised error still records the path when it was chosen."""

    frame_id: uuid.UUID = new_row_id()
    asset_ref: str = assembled_frame_relative_path(assembly_id, frame_id)
    new_refs.append(asset_ref)
    rendered: AssembledFrameRender = render_assembled_frame(
        skeleton,
        slide,
        storage_directory,
        assembly_id,
        frame_id,
    )
    frame: AssembledCarouselFrame = AssembledCarouselFrame(
        id=frame_id,
        assembled_carousel_id=assembled_carousel_id,
        position=position,
        slide_id=slide.id,
        album_image_id=slide.album_image_id,
        asset_ref=rendered.asset_ref,
        blocked=rendered.blocked,
        block_reason=rendered.block_reason,
        block_detail=rendered.block_detail,
    )

    return frame


def _delete_asset_refs(asset_refs: Sequence[str], storage_directory: Path) -> None:
    """Delete stored PNGs. A missing file or an escaped path is skipped."""

    for asset_ref in asset_refs:
        _delete_asset_ref(asset_ref, storage_directory)


def _delete_asset_ref(asset_ref: str, storage_directory: Path) -> None:
    """Delete one PNG when it is a file inside the store."""

    try:
        asset_path: Path = resolve_asset_reference_path(asset_ref, storage_directory)
    except PublishMediaPathEscapeError:

        return

    if asset_path.is_file():
        asset_path.unlink()
