"""Read content carousels, and register carousel and slide writes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.lookups import (
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.carousel_preview import register_source_preview_routes
from app.api.v1.schemas import (
    AssembledCarouselReadResponse,
    AssembledFrameReadResponse,
    CarouselAssemblyReadResponse,
    CarouselInstructionReadResponse,
    CarouselListItemResponse,
    CarouselReadResponse,
    CarouselResearchReadResponse,
    CarouselStepsResponse,
    PendingSlideDraftBatchResponse,
    TextGenerationStatusResponse,
    SlideElementTextReadResponse,
    SlideImageReadResponse,
    SlideReadResponse,
)
from app.settings import get_settings
from app.carousels.text_generation import (
    TextGenerationAvailability,
    text_generation_availability,
)
from app.db import get_our_database_session
from app.models.album import AlbumImage
from app.models.carousel import (
    AssembledCarousel,
    AssembledCarouselFrame,
    Carousel,
    CarouselAssembly,
    CarouselInstruction,
    CarouselResearchItem,
    Slide,
    SlideElementText,
)
from app.models.enums import SlideTextStatus
from app.models.research_item import ResearchItem
from app.models.skeleton import Skeleton
from app.carousels.slide_skeleton import (
    CarouselStepStates,
    carousel_step_states,
    instruction_bodies_have_text,
)
from app.carousels.slide_text_review import live_slides, slide_counts_as_live


carousels_router: APIRouter = APIRouter(prefix="/carousels", tags=["carousels"])


def carousels_list_statement() -> Select[tuple[Carousel]]:
    """Return every carousel, ordered by name.

    Returns:
        A select of carousels with slides loaded.
    """

    statement: Select[tuple[Carousel]] = (
        select(Carousel)
        .options(
            selectinload(Carousel.slides).selectinload(Slide.album_image),
            selectinload(Carousel.slides).selectinload(Slide.element_texts),
            selectinload(Carousel.slides).selectinload(Slide.exclusions),
            selectinload(Carousel.assemblies)
            .selectinload(CarouselAssembly.assembled_carousels)
            .selectinload(AssembledCarousel.frames),
        )
        .order_by(Carousel.name.asc(), Carousel.slug.asc())
    )

    return statement


@carousels_router.get("", response_model=list[CarouselListItemResponse])
def list_carousels(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[CarouselListItemResponse]:
    """Return carousels. Readers may call this.

    Instruction documents stay on the detail route.
    """

    statement: Select[tuple[Carousel]] = carousels_list_statement()
    source_scalars = our_database_session.scalars(statement)
    carousels: list[Carousel] = list(source_scalars.all())
    list_items: list[CarouselListItemResponse] = [
        serialize_carousel_list_item(carousel) for carousel in carousels
    ]

    return list_items


@carousels_router.get(
    "/text-generation",
    response_model=TextGenerationStatusResponse,
)
def read_text_generation_status() -> TextGenerationStatusResponse:
    """Return whether Generate can run. Readers may call this."""

    availability: TextGenerationAvailability = text_generation_availability(get_settings())
    status_response: TextGenerationStatusResponse = TextGenerationStatusResponse(
        available=availability.available,
        detail=availability.detail,
    )

    return status_response


@carousels_router.get("/{carousel_id}", response_model=CarouselReadResponse)
def get_carousel(
    carousel_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> CarouselReadResponse:
    """Return one carousel and its slides. A missing id is HTTP 404.

    Readers may call this. The response includes the stored generation
    and open step, the attached research, the instruction documents,
    and the derived step state.
    """

    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )
    source_read_response: CarouselReadResponse = serialize_carousel(
        found_source,
        found_skeleton,
    )

    return source_read_response


def serialize_carousel_list_item(carousel: Carousel) -> CarouselListItemResponse:
    """Return the list shape, with a count and no slide bodies.

    Research, instruction documents, and derived step state stay on
    the detail route.
    """

    list_item: CarouselListItemResponse = CarouselListItemResponse(
        id=carousel.id,
        skeleton_id=carousel.skeleton_id,
        name=carousel.name,
        slug=carousel.slug,
        album_id=carousel.album_id,
        generation_number=carousel.generation_number,
        editor_step=carousel.editor_step,
        slide_count=len(list(carousel.slides)),
        created_at=carousel.created_at,
        updated_at=carousel.updated_at,
    )

    return list_item


def serialize_carousel(
    carousel: Carousel,
    skeleton: Skeleton,
) -> CarouselReadResponse:
    """Return one carousel with research, instructions, step state, and slides.

    Args:
        carousel: The carousel row, with slides, research links, and
            instruction documents loaded.
        skeleton: That carousel's skeleton, with elements loaded.

    Returns:
        The detail response. ``editor_step`` is the stored open step.
        ``steps`` is derived from the skeleton, the album, and the slides.
        ``instructions`` follows position.
    """

    slide_responses: list[SlideReadResponse] = [
        serialize_slide(slide) for slide in _slides_in_position_order(carousel)
    ]
    research_responses: list[CarouselResearchReadResponse] = _research_in_position_order(
        carousel,
    )
    instruction_responses: list[CarouselInstructionReadResponse] = (
        _instructions_in_position_order(carousel)
    )
    has_instruction_text: bool = instruction_bodies_have_text(
        [document.body for document in list(carousel.instructions)],
    )
    live_slide_count: int = len(live_slides(list(carousel.slides)))
    has_final_assembly: bool = _generation_has_final_assembly(carousel)
    step_states: CarouselStepStates = carousel_step_states(
        skeleton,
        carousel.album_id,
        len(slide_responses),
        has_instruction_text,
        live_slide_count,
        has_final_assembly,
    )
    source_read_response: CarouselReadResponse = CarouselReadResponse(
        id=carousel.id,
        skeleton_id=carousel.skeleton_id,
        name=carousel.name,
        slug=carousel.slug,
        album_id=carousel.album_id,
        generation_number=carousel.generation_number,
        editor_step=carousel.editor_step,
        live_slide_count=live_slide_count,
        created_at=carousel.created_at,
        updated_at=carousel.updated_at,
        research=research_responses,
        instructions=instruction_responses,
        steps=_steps_response(step_states),
        slides=slide_responses,
        pending_slide_draft_batch=_pending_slide_draft_batch(carousel),
        assembly=_assembly_response(carousel),
    )

    return source_read_response


def _generation_has_final_assembly(carousel: Carousel) -> bool:
    """Return whether this generation already has an assembly row."""

    for assembly in list(carousel.assemblies):

        if assembly.generation_number == carousel.generation_number:

            return True

    return False


def _assembly_response(carousel: Carousel) -> CarouselAssemblyReadResponse | None:
    """Return this generation's assembly, or null when Final has not run."""

    for assembly in list(carousel.assemblies):

        if assembly.generation_number != carousel.generation_number:
            continue

        assembled_carousels: list[AssembledCarousel] = sorted(
            list(assembly.assembled_carousels),
            key=_assembled_position,
        )
        carousel_responses: list[AssembledCarouselReadResponse] = [
            _serialize_assembled_carousel(assembled) for assembled in assembled_carousels
        ]
        assembly_response: CarouselAssemblyReadResponse = CarouselAssemblyReadResponse(
            id=assembly.id,
            generation_number=assembly.generation_number,
            slide_count=assembly.slide_count,
            carousels=carousel_responses,
        )

        return assembly_response

    return None


def _assembled_position(assembled: AssembledCarousel) -> int:
    """Return the sort key for one assembled carousel."""

    position: int = assembled.position

    return position


def _serialize_assembled_carousel(assembled: AssembledCarousel) -> AssembledCarouselReadResponse:
    """Return one assembled carousel and its frames."""

    frames: list[AssembledCarouselFrame] = sorted(
        list(assembled.frames),
        key=_frame_position,
    )
    frame_responses: list[AssembledFrameReadResponse] = [
        _serialize_frame(frame) for frame in frames
    ]
    blocked: bool = any(frame.blocked for frame in frames)
    assembled_response: AssembledCarouselReadResponse = AssembledCarouselReadResponse(
        id=assembled.id,
        position=assembled.position,
        status=assembled.status,
        caption=assembled.caption,
        cta_url=assembled.cta_url,
        blocked=blocked,
        frames=frame_responses,
    )

    return assembled_response


def _frame_position(frame: AssembledCarouselFrame) -> int:
    """Return the sort key for one frame."""

    position: int = frame.position

    return position


def _serialize_frame(frame: AssembledCarouselFrame) -> AssembledFrameReadResponse:
    """Return one frame without the PNG bytes."""

    frame_response: AssembledFrameReadResponse = AssembledFrameReadResponse(
        id=frame.id,
        position=frame.position,
        slide_id=frame.slide_id,
        album_image_id=frame.album_image_id,
        blocked=frame.blocked,
        block_reason=frame.block_reason,
        block_detail=frame.block_detail,
    )

    return frame_response


def _instructions_in_position_order(
    carousel: Carousel,
) -> list[CarouselInstructionReadResponse]:
    """Return instruction documents in position order.

    Args:
        carousel: The carousel, with instruction documents loaded.

    Returns:
        One entry per row. ``id`` is the document.
    """

    ordered_documents: list[CarouselInstruction] = sorted(
        list(carousel.instructions),
        key=_instruction_position,
    )
    instruction_responses: list[CarouselInstructionReadResponse] = [
        _serialize_instruction(document) for document in ordered_documents
    ]

    return instruction_responses


def _instruction_position(document: CarouselInstruction) -> int:
    """Return the sort key for an instruction document."""

    position: int = document.position

    return position


def _serialize_instruction(
    document: CarouselInstruction,
) -> CarouselInstructionReadResponse:
    """Return one instruction document."""

    instruction_response: CarouselInstructionReadResponse = CarouselInstructionReadResponse(
        id=document.id,
        position=document.position,
        body=document.body,
    )

    return instruction_response


def _research_in_position_order(carousel: Carousel) -> list[CarouselResearchReadResponse]:
    """Return attached research in position order.

    Args:
        carousel: The carousel, with research links loaded.

    Returns:
        One entry per link. ``id`` is the research item.
    """

    ordered_links: list[CarouselResearchItem] = sorted(
        list(carousel.research_links),
        key=_research_position,
    )
    research_responses: list[CarouselResearchReadResponse] = [
        _serialize_research_link(link) for link in ordered_links
    ]

    return research_responses


def _research_position(link: CarouselResearchItem) -> int:
    """Return the sort key for an attached research item."""

    position: int = link.position

    return position


def _serialize_research_link(link: CarouselResearchItem) -> CarouselResearchReadResponse:
    """Return one attached research item."""

    research_item: ResearchItem = link.research_item
    research_response: CarouselResearchReadResponse = CarouselResearchReadResponse(
        id=research_item.id,
        title=research_item.title,
        slug=research_item.slug,
        position=link.position,
    )

    return research_response


def _steps_response(step_states: CarouselStepStates) -> CarouselStepsResponse:
    """Copy derived step states onto the response model."""

    steps_response: CarouselStepsResponse = CarouselStepsResponse(
        basic=step_states.basic,
        instructions=step_states.instructions,
        content=step_states.content,
        slides=step_states.slides,
        final=step_states.final,
    )

    return steps_response


def _pending_slide_draft_batch(
    carousel: Carousel,
) -> PendingSlideDraftBatchResponse | None:
    """Return the pending generated set, or null when none is waiting."""

    for batch in list(carousel.draft_batches):

        if batch.status == "pending":
            pending: PendingSlideDraftBatchResponse = PendingSlideDraftBatchResponse(
                id=batch.id,
                status=batch.status,
                slide_count=batch.slide_count,
            )

            return pending

    return None


def _slides_in_position_order(carousel: Carousel) -> list[Slide]:
    """Return slides sorted by position."""

    ordered_slides: list[Slide] = sorted(list(carousel.slides), key=_slide_position)

    return ordered_slides


def _slide_position(slide: Slide) -> int:
    """Return the sort key for a slide."""

    position: int = slide.position

    return position


def serialize_slide(slide: Slide) -> SlideReadResponse:
    """Return one slide with skeleton text and images in position order."""

    text_responses: list[SlideElementTextReadResponse] = [
        _serialize_element_text(element_text) for element_text in list(slide.element_texts)
    ]
    text_status: SlideTextStatus = (
        SlideTextStatus.LIVE if slide_counts_as_live(slide) else SlideTextStatus.DRAFT
    )
    draft_responses: list[SlideElementTextReadResponse] = _draft_texts(slide, text_status)
    excluded_slide_ids: list[uuid.UUID] = _excluded_slide_ids(slide)
    image_responses: list[SlideImageReadResponse] = [
        serialize_image(image) for image in _images_in_position_order(slide)
    ]
    slide_response: SlideReadResponse = SlideReadResponse(
        id=slide.id,
        position=slide.position,
        name=slide.name,
        text_status=text_status,
        texts=text_responses,
        draft_texts=draft_responses,
        excluded_slide_ids=excluded_slide_ids,
        images=image_responses,
        draft_batch_id=slide.draft_batch_id,
    )

    return slide_response


def _serialize_element_text(element_text: SlideElementText) -> SlideElementTextReadResponse:
    """Return one stored skeleton-element value."""

    text_response: SlideElementTextReadResponse = SlideElementTextReadResponse(
        skeleton_element_id=element_text.skeleton_element_id,
        value=element_text.value,
    )

    return text_response


def _draft_texts(
    slide: Slide,
    text_status: SlideTextStatus,
) -> list[SlideElementTextReadResponse]:
    """Return drafted strings. A live slide has none."""

    if text_status != SlideTextStatus.DRAFT:

        return []

    draft_responses: list[SlideElementTextReadResponse] = []

    for element_text in list(slide.element_texts):
        draft_value: str = element_text.draft_value or ""
        draft_response: SlideElementTextReadResponse = SlideElementTextReadResponse(
            skeleton_element_id=element_text.skeleton_element_id,
            value=draft_value,
        )
        draft_responses.append(draft_response)

    return draft_responses


def _excluded_slide_ids(slide: Slide) -> list[uuid.UUID]:
    """Return the other slide ids this slide cannot be shown with."""

    excluded_ids: list[uuid.UUID] = sorted(
        (exclusion.excluded_slide_id for exclusion in list(slide.exclusions)),
        key=str,
    )

    return excluded_ids


def _images_in_position_order(slide: Slide) -> list[AlbumImage]:
    """Return the album image this slide points at, if any."""

    ordered_images: list[AlbumImage] = list(slide.images)

    return ordered_images


def serialize_image(image: AlbumImage) -> SlideImageReadResponse:
    """Return one image, including license and the concrete path."""

    image_response: SlideImageReadResponse = SlideImageReadResponse(
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


from app.api.v1.carousel_assembly import register_carousel_assembly_routes
from app.api.v1.carousel_text import register_source_text_routes
from app.api.v1.carousel_writes import register_source_write_routes


register_source_write_routes(carousels_router)
register_source_preview_routes(carousels_router)
register_carousel_assembly_routes(carousels_router)
register_source_text_routes(carousels_router)
