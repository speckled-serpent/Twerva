"""Read one generation snapshot. Readers may call this."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.api.v1.lookups import fetch_carousel_by_id_or_raise
from app.api.v1.schemas import (
    CarouselGenerationImageReadResponse,
    CarouselGenerationInstructionReadResponse,
    CarouselGenerationReadResponse,
    CarouselGenerationResearchReadResponse,
    CarouselGenerationSlideReadResponse,
    CarouselGenerationSlideTextReadResponse,
)
from app.auth.dependencies import require_authenticated_ops_operator
from app.db import get_our_database_session
from app.models.carousel import (
    CarouselGeneration,
    CarouselGenerationImage,
    CarouselGenerationInstruction,
    CarouselGenerationResearch,
    CarouselGenerationSlide,
    CarouselGenerationSlideText,
)
from app.models.ops_user import OpsUser


GENERATION_NOT_FOUND_DETAIL: str = "Generation not found."


def register_carousel_generation_routes(carousels_router: APIRouter) -> None:
    """Attach the generation snapshot route.

    Args:
        carousels_router: The carousel router these paths extend.
    """

    carousels_router.add_api_route(
        "/{carousel_id}/generations/{generation_number}",
        get_carousel_generation,
        methods=["GET"],
        response_model=CarouselGenerationReadResponse,
    )


def get_carousel_generation(
    carousel_id: uuid.UUID,
    generation_number: int,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> CarouselGenerationReadResponse:
    """Return one snapshot. A missing carousel or generation is HTTP 404.

    Readers may call this. The route does not draw a frame and does not
    read a PNG.
    """

    _ = current_ops_operator
    fetch_carousel_by_id_or_raise(carousel_id, our_database_session)
    generation: CarouselGeneration | None = our_database_session.scalars(
        _generation_statement(carousel_id, generation_number),
    ).first()

    if generation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GENERATION_NOT_FOUND_DETAIL,
        )

    return _serialize_generation(generation)


def _generation_statement(
    carousel_id: uuid.UUID,
    generation_number: int,
) -> Select[tuple[CarouselGeneration]]:
    """Load one snapshot and the rows the response returns."""

    statement: Select[tuple[CarouselGeneration]] = (
        select(CarouselGeneration)
        .where(
            CarouselGeneration.carousel_id == carousel_id,
            CarouselGeneration.generation_number == generation_number,
        )
        .options(
            selectinload(CarouselGeneration.instructions),
            selectinload(CarouselGeneration.research_items),
            selectinload(CarouselGeneration.images),
            selectinload(CarouselGeneration.slides).selectinload(
                CarouselGenerationSlide.texts,
            ),
            selectinload(CarouselGeneration.slides).selectinload(
                CarouselGenerationSlide.exclusions,
            ),
        )
    )

    return statement


def _serialize_generation(generation: CarouselGeneration) -> CarouselGenerationReadResponse:
    """Return the snapshot body. Frames are not included."""

    instructions: list[CarouselGenerationInstructionReadResponse] = [
        _serialize_instruction(instruction)
        for instruction in sorted(list(generation.instructions), key=_instruction_position)
    ]
    research: list[CarouselGenerationResearchReadResponse] = [
        _serialize_research(item)
        for item in sorted(list(generation.research_items), key=_research_position)
    ]
    images: list[CarouselGenerationImageReadResponse] = [
        _serialize_image(image)
        for image in sorted(list(generation.images), key=_image_position)
    ]
    slides: list[CarouselGenerationSlideReadResponse] = [
        _serialize_slide(slide)
        for slide in sorted(list(generation.slides), key=_slide_position)
    ]
    response: CarouselGenerationReadResponse = CarouselGenerationReadResponse(
        id=generation.id,
        carousel_id=generation.carousel_id,
        generation_number=generation.generation_number,
        album_id=generation.album_id,
        instructions=instructions,
        research=research,
        images=images,
        slides=slides,
    )

    return response


def _serialize_instruction(
    instruction: CarouselGenerationInstruction,
) -> CarouselGenerationInstructionReadResponse:
    """Return one copied instruction."""

    response: CarouselGenerationInstructionReadResponse = (
        CarouselGenerationInstructionReadResponse(
            position=instruction.position,
            body=instruction.body,
        )
    )

    return response


def _serialize_research(
    research: CarouselGenerationResearch,
) -> CarouselGenerationResearchReadResponse:
    """Return one copied research document."""

    response: CarouselGenerationResearchReadResponse = CarouselGenerationResearchReadResponse(
        research_item_id=research.research_item_id,
        position=research.position,
        title=research.title,
        body=research.body,
    )

    return response


def _serialize_image(
    image: CarouselGenerationImage,
) -> CarouselGenerationImageReadResponse:
    """Return one copied image id."""

    response: CarouselGenerationImageReadResponse = CarouselGenerationImageReadResponse(
        album_image_id=image.album_image_id,
        position=image.position,
    )

    return response


def _serialize_slide(slide: CarouselGenerationSlide) -> CarouselGenerationSlideReadResponse:
    """Return one copied slide and the other snapshot slides it excludes."""

    texts: list[CarouselGenerationSlideTextReadResponse] = [
        _serialize_text(copied_text) for copied_text in list(slide.texts)
    ]
    excluded_slide_ids: list[uuid.UUID] = [
        exclusion.excluded_generation_slide_id for exclusion in list(slide.exclusions)
    ]
    response: CarouselGenerationSlideReadResponse = CarouselGenerationSlideReadResponse(
        id=slide.id,
        source_slide_id=slide.source_slide_id,
        position=slide.position,
        name=slide.name,
        text_status=slide.text_status,
        album_image_id=slide.album_image_id,
        texts=texts,
        excluded_slide_ids=excluded_slide_ids,
    )

    return response


def _serialize_text(
    copied_text: CarouselGenerationSlideText,
) -> CarouselGenerationSlideTextReadResponse:
    """Return one copied element text."""

    response: CarouselGenerationSlideTextReadResponse = CarouselGenerationSlideTextReadResponse(
        skeleton_element_id=copied_text.skeleton_element_id,
        value=copied_text.value,
        draft_value=copied_text.draft_value,
    )

    return response


def _instruction_position(instruction: CarouselGenerationInstruction) -> int:
    """Return the stored instruction position."""

    position: int = instruction.position

    return position


def _research_position(research: CarouselGenerationResearch) -> int:
    """Return the stored research position."""

    position: int = research.position

    return position


def _image_position(image: CarouselGenerationImage) -> int:
    """Return the stored image position."""

    position: int = image.position

    return position


def _slide_position(slide: CarouselGenerationSlide) -> int:
    """Return the stored slide position."""

    position: int = slide.position

    return position
