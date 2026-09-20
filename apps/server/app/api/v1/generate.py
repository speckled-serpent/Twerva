"""Carousel generate route (1.4e). Sync; no Celery."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    ArtifactReadResponse,
    CarouselGenerateRequest,
    CarouselTemplateReadResponse,
)
from app.db import get_our_database_session
from app.generate.errors import (
    CarouselClusterBrandMismatchError,
    CarouselClusterMissingError,
    CarouselGenerateError,
    CarouselSourceItemMissingError,
    CarouselUnknownTemplateError,
)
from app.generate.service import generate_carousel_artifact_draft
from app.generate.templates import (
    DEFAULT_CAROUSEL_TEMPLATE_ID,
    CarouselTemplate,
    list_carousel_templates,
)
from app.models import Artifact


generate_router: APIRouter = APIRouter(prefix="/generate", tags=["generate"])


@generate_router.get("/templates", response_model=list[CarouselTemplateReadResponse])
def list_generate_templates() -> list[CarouselTemplateReadResponse]:
    """Return the restricted Spotmu carousel template registry."""

    carousel_templates: list[CarouselTemplate] = list_carousel_templates()
    template_read_responses: list[CarouselTemplateReadResponse] = [
        CarouselTemplateReadResponse(
            template_id=carousel_template.template_id,
            name=carousel_template.name,
            description=carousel_template.description,
            is_default=carousel_template.template_id == DEFAULT_CAROUSEL_TEMPLATE_ID,
        )
        for carousel_template in carousel_templates
    ]

    return template_read_responses


@generate_router.post(
    "/carousel",
    response_model=ArtifactReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_carousel_artifact(
    carousel_generate_request: CarouselGenerateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> ArtifactReadResponse:
    """Render a carousel from a SourceItem and persist a new draft Artifact."""

    created_artifact: Artifact

    try:
        created_artifact = generate_carousel_artifact_draft(
            carousel_generate_request.source_item_id,
            our_database_session,
            cluster_id=carousel_generate_request.cluster_id,
            template_id=carousel_generate_request.template_id,
        )
    except CarouselGenerateError as generate_error:
        _raise_http_exception_for_carousel_generate_error(generate_error)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Carousel artifact could not be stored (foreign key conflict).",
    )
    our_database_session.refresh(created_artifact)
    artifact_read_response: ArtifactReadResponse = ArtifactReadResponse.model_validate(
        created_artifact,
    )

    return artifact_read_response


def _raise_http_exception_for_carousel_generate_error(
    generate_error: CarouselGenerateError,
) -> NoReturn:
    """Map generate domain errors to HTTP status codes."""

    if isinstance(generate_error, CarouselSourceItemMissingError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(generate_error),
        ) from generate_error

    if isinstance(generate_error, CarouselClusterMissingError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(generate_error),
        ) from generate_error

    if isinstance(generate_error, CarouselClusterBrandMismatchError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(generate_error),
        ) from generate_error

    if isinstance(generate_error, CarouselUnknownTemplateError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(generate_error),
        ) from generate_error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(generate_error),
    ) from generate_error
