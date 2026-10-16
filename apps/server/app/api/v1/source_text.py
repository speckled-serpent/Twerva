"""Inspiration, rules, and drafted unit text.

Generate writes a draft. Accept copies that draft onto the live text.
Images are not part of this path.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_content_source_by_id_or_raise,
    fetch_theme_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    SourceGuidancePatchRequest,
    SourceReadResponse,
    UnitAcceptTextRequest,
    UnitReadResponse,
)
from app.api.v1.source_writes import (
    _fetch_unit_or_raise,
    _next_unit_position,
    _parsed_texts,
    _replace_texts,
    _require_image_when_theme_needs_one,
    _store_draft_texts,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit
from app.models.enums import UnitTextStatus
from app.models.ops_user import OpsUser
from app.models.theme import Theme
from app.settings import get_settings
from app.sources.editing import new_row_id
from app.sources.text_generation import (
    DraftedUnitText,
    TextElementPrompt,
    TextGenerationError,
    TextGenerationProvider,
    TextGenerationUnavailable,
    require_text_generation_provider,
)
from app.sources.unit_text_review import unit_counts_as_live
from app.sources.unit_theme import theme_text_elements


NO_TEXT_ELEMENTS_DETAIL: str = "This theme has no text elements to draft."
ACCEPT_WITHOUT_DRAFT_DETAIL: str = "This unit has no draft to accept."
GUIDANCE_TOO_LONG_DETAIL: str = (
    "Inspiration and rules must be 8000 characters or fewer."
)
MAX_GUIDANCE_LENGTH: int = 8000


def register_source_text_routes(sources_router: APIRouter) -> None:
    """Attach guidance, generate, and accept routes."""

    sources_router.add_api_route(
        "/{source_id}/guidance",
        patch_source_guidance,
        methods=["PATCH"],
        response_model=SourceReadResponse,
    )
    sources_router.add_api_route(
        "/{source_id}/units/generate",
        generate_source_unit,
        methods=["POST"],
        response_model=UnitReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/generate",
        generate_unit_text,
        methods=["POST"],
        response_model=UnitReadResponse,
    )
    sources_router.add_api_route(
        "/{source_id}/units/{unit_id}/accept-text",
        accept_unit_text,
        methods=["POST"],
        response_model=UnitReadResponse,
    )


def patch_source_guidance(
    source_id: uuid.UUID,
    guidance_request: SourceGuidancePatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SourceReadResponse:
    """Save inspiration and rules. A too-long value writes nothing."""

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    inspiration: str = guidance_request.inspiration
    rules: str = guidance_request.rules

    if len(inspiration) > MAX_GUIDANCE_LENGTH or len(rules) > MAX_GUIDANCE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GUIDANCE_TOO_LONG_DETAIL,
        )

    found_source.inspiration = inspiration
    found_source.rules = rules
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Inspiration could not be saved.",
    )
    our_database_session.refresh(found_source)

    from app.api.v1.sources import serialize_content_source

    return serialize_content_source(found_source)


def generate_source_unit(
    source_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitReadResponse:
    """Create one draft unit. The image stays empty for a manual upload."""

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )
    provider: TextGenerationProvider = _provider_or_http()
    drafted_text: DraftedUnitText = _draft_or_http(
        provider,
        found_source,
        found_theme,
        None,
    )
    next_position: int = _next_unit_position(found_source.id, our_database_session)
    created_unit: Unit = Unit(
        id=new_row_id(),
        source_id=found_source.id,
        position=next_position,
        name=drafted_text.name,
        text_status=UnitTextStatus.DRAFT,
    )
    created_unit.images = []
    created_unit.element_texts = []
    created_unit.exclusions = []
    our_database_session.add(created_unit)
    _store_draft_texts(
        created_unit,
        _draft_pairs(found_theme, drafted_text),
        our_database_session,
    )
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Unit could not be saved.",
    )
    our_database_session.refresh(created_unit)

    from app.api.v1.sources import serialize_unit

    return serialize_unit(created_unit)


def generate_unit_text(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitReadResponse:
    """Draft this unit's theme text. The approved value stays until accept."""

    _ = current_ops_operator
    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )
    provider: TextGenerationProvider = _provider_or_http()
    drafted_text: DraftedUnitText = _draft_or_http(
        provider,
        found_source,
        found_theme,
        found_unit.name,
    )
    _store_draft_texts(
        found_unit,
        _draft_pairs(found_theme, drafted_text),
        our_database_session,
    )
    found_unit.text_status = UnitTextStatus.DRAFT
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Unit could not be saved.",
    )
    our_database_session.refresh(found_unit)

    from app.api.v1.sources import serialize_unit

    return serialize_unit(found_unit)


def accept_unit_text(
    source_id: uuid.UUID,
    unit_id: uuid.UUID,
    accept_request: UnitAcceptTextRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> UnitReadResponse:
    """Copy the submitted text onto the live unit. A draft is required."""

    _ = current_ops_operator
    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )

    if unit_counts_as_live(found_unit):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ACCEPT_WITHOUT_DRAFT_DETAIL,
        )

    _require_image_when_theme_needs_one(found_theme, len(list(found_unit.images)))
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_theme,
        accept_request.texts,
    )
    _replace_texts(found_unit, stored_texts, our_database_session)
    found_unit.text_status = UnitTextStatus.LIVE
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Unit could not be saved.",
    )
    our_database_session.refresh(found_unit)

    from app.api.v1.sources import serialize_unit

    return serialize_unit(found_unit)


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
    source: ContentSource,
    theme: Theme,
    unit_name: str | None,
) -> DraftedUnitText:
    """Draft text for every theme text element. A failure writes nothing."""

    prompts: list[TextElementPrompt] = _text_prompts(theme)

    if len(prompts) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_TEXT_ELEMENTS_DETAIL,
        )

    try:
        drafted_text: DraftedUnitText = provider.draft_unit_text(
            source.inspiration or "",
            source.rules or "",
            unit_name,
            prompts,
        )
    except TextGenerationError as generation_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(generation_error),
        ) from generation_error

    return drafted_text


def _text_prompts(theme: Theme) -> list[TextElementPrompt]:
    """Label each text element by its name for the provider."""

    prompts: list[TextElementPrompt] = []

    for element in theme_text_elements(theme):
        label: str = element.name.strip()

        if label == "":
            label = "text"

        prompt: TextElementPrompt = TextElementPrompt(
            theme_element_id=element.id,
            label=label,
        )
        prompts.append(prompt)

    return prompts


def _draft_pairs(
    theme: Theme,
    drafted_text: DraftedUnitText,
) -> list[tuple[uuid.UUID, str]]:
    """One draft string per text element, in frame order."""

    pairs: list[tuple[uuid.UUID, str]] = [
        (
            element.id,
            drafted_text.values_by_element_id.get(element.id, ""),
        )
        for element in theme_text_elements(theme)
    ]

    return pairs
