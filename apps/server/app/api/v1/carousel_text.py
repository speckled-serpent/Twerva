"""Instruction documents and drafted slide text.

Generate writes a draft from the instruction documents, joined in
position order and passed as inspiration with empty rules. Accept
copies the draft onto the live text. Images are not part of this path.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    SlideAcceptTextRequest,
    SlideReadResponse,
)
from app.api.v1.carousel_writes import (
    _fetch_slide_or_raise,
    _next_slide_position,
    _parsed_texts,
    _replace_texts,
    _require_image_when_skeleton_needs_one,
    _store_draft_texts,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.carousel import Carousel, CarouselInstruction, Slide
from app.models.enums import SlideTextStatus
from app.models.ops_user import OpsUser
from app.models.skeleton import Skeleton
from app.settings import get_settings
from app.carousels.editing import new_row_id
from app.carousels.instructions import instruction_prompt_text
from app.carousels.text_generation import (
    DraftedSlideText,
    TextElementPrompt,
    TextGenerationError,
    TextGenerationProvider,
    TextGenerationUnavailable,
    require_text_generation_provider,
)
from app.carousels.slide_text_review import slide_counts_as_live
from app.carousels.slide_skeleton import skeleton_text_elements


NO_TEXT_ELEMENTS_DETAIL: str = "This skeleton has no text elements to draft."
ACCEPT_WITHOUT_DRAFT_DETAIL: str = "This slide has no draft to accept."


def register_source_text_routes(carousels_router: APIRouter) -> None:
    """Attach generate and accept routes."""

    carousels_router.add_api_route(
        "/{carousel_id}/slides/generate",
        generate_source_slide,
        methods=["POST"],
        response_model=SlideReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/generate",
        generate_slide_text,
        methods=["POST"],
        response_model=SlideReadResponse,
    )
    carousels_router.add_api_route(
        "/{carousel_id}/slides/{slide_id}/accept-text",
        accept_slide_text,
        methods=["POST"],
        response_model=SlideReadResponse,
    )


def generate_source_slide(
    carousel_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideReadResponse:
    """Create one draft slide. The image stays empty for a manual upload."""

    _ = current_ops_operator
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        found_source.skeleton_id,
        our_database_session,
    )
    provider: TextGenerationProvider = _provider_or_http()
    drafted_text: DraftedSlideText = _draft_or_http(
        provider,
        found_source,
        found_skeleton,
        None,
    )
    next_position: int = _next_slide_position(found_source.id, our_database_session)
    created_slide: Slide = Slide(
        id=new_row_id(),
        carousel_id=found_source.id,
        position=next_position,
        name=drafted_text.name,
        text_status=SlideTextStatus.DRAFT,
    )
    created_slide.images = []
    created_slide.element_texts = []
    created_slide.exclusions = []
    our_database_session.add(created_slide)
    _store_draft_texts(
        created_slide,
        _draft_pairs(found_skeleton, drafted_text),
        our_database_session,
    )
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slide could not be saved.",
    )
    our_database_session.refresh(created_slide)

    from app.api.v1.carousels import serialize_slide

    return serialize_slide(created_slide)


def generate_slide_text(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideReadResponse:
    """Draft this slide's skeleton text. The approved value stays until accept."""

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
    provider: TextGenerationProvider = _provider_or_http()
    drafted_text: DraftedSlideText = _draft_or_http(
        provider,
        found_source,
        found_skeleton,
        found_slide.name,
    )
    _store_draft_texts(
        found_slide,
        _draft_pairs(found_skeleton, drafted_text),
        our_database_session,
    )
    found_slide.text_status = SlideTextStatus.DRAFT
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slide could not be saved.",
    )
    our_database_session.refresh(found_slide)

    from app.api.v1.carousels import serialize_slide

    return serialize_slide(found_slide)


def accept_slide_text(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    accept_request: SlideAcceptTextRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SlideReadResponse:
    """Copy the submitted text onto the live slide. A draft is required."""

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

    if slide_counts_as_live(found_slide):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ACCEPT_WITHOUT_DRAFT_DETAIL,
        )

    _require_image_when_skeleton_needs_one(found_skeleton, len(list(found_slide.images)))
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_skeleton,
        accept_request.texts,
    )
    _replace_texts(found_slide, stored_texts, our_database_session)
    found_slide.text_status = SlideTextStatus.LIVE
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slide could not be saved.",
    )
    our_database_session.refresh(found_slide)

    from app.api.v1.carousels import serialize_slide

    return serialize_slide(found_slide)


def _provider_or_http() -> TextGenerationProvider:
    """Return the configured provider. A missing key is HTTP 409."""

    try:
        provider: TextGenerationProvider = require_text_generation_provider(get_settings())
    except TextGenerationUnavailable as unavailable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=unavailable.detail,
        ) from unavailable

    return provider


def _draft_or_http(
    provider: TextGenerationProvider,
    carousel: Carousel,
    skeleton: Skeleton,
    slide_name: str | None,
) -> DraftedSlideText:
    """Draft text for every skeleton text element. A failure writes nothing.

    Instruction documents are loaded in position order. Blank bodies
    are dropped, and the rest are one inspiration string. Rules passed
    to the provider are empty.
    """

    prompts: list[TextElementPrompt] = _text_prompts(skeleton)

    if len(prompts) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_TEXT_ELEMENTS_DETAIL,
        )

    inspiration: str = instruction_prompt_text(
        _instruction_bodies_in_position_order(carousel),
    )

    try:
        drafted_text: DraftedSlideText = provider.draft_slide_text(
            inspiration,
            "",
            slide_name,
            prompts,
        )
    except TextGenerationError as generation_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(generation_error),
        ) from generation_error

    return drafted_text


def _instruction_bodies_in_position_order(carousel: Carousel) -> list[str]:
    """Return instruction bodies from position 0 upward."""

    ordered_documents: list[CarouselInstruction] = sorted(
        list(carousel.instructions),
        key=_instruction_position,
    )
    bodies: list[str] = [document.body for document in ordered_documents]

    return bodies


def _instruction_position(document: CarouselInstruction) -> int:
    """Return the sort key for an instruction document."""

    position: int = document.position

    return position


def _text_prompts(skeleton: Skeleton) -> list[TextElementPrompt]:
    """Label each text element by its name for the provider."""

    prompts: list[TextElementPrompt] = []

    for element in skeleton_text_elements(skeleton):
        label: str = element.name.strip()

        if label == "":
            label = "text"

        prompt: TextElementPrompt = TextElementPrompt(
            skeleton_element_id=element.id,
            label=label,
        )
        prompts.append(prompt)

    return prompts


def _draft_pairs(
    skeleton: Skeleton,
    drafted_text: DraftedSlideText,
) -> list[tuple[uuid.UUID, str]]:
    """One draft string per text element, in frame order."""

    pairs: list[tuple[uuid.UUID, str]] = [
        (
            element.id,
            drafted_text.values_by_element_id.get(element.id, ""),
        )
        for element in skeleton_text_elements(skeleton)
    ]

    return pairs
