"""Artifact create/list/get routes (status is part of the payload)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_artifact_by_id_or_raise,
    fetch_brand_by_id_or_raise,
    fetch_cluster_by_id_or_raise,
    fetch_source_item_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import ArtifactCreateRequest, ArtifactReadResponse
from app.db import get_our_database_session
from app.models import Artifact


artifacts_router: APIRouter = APIRouter(prefix="/artifacts", tags=["artifacts"])


@artifacts_router.post(
    "",
    response_model=ArtifactReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_artifact(
    artifact_create_request: ArtifactCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> ArtifactReadResponse:
    """Persist an Artifact, including its status field."""

    fetch_brand_by_id_or_raise(
        artifact_create_request.brand_id,
        our_database_session,
    )
    _require_optional_artifact_parents(
        artifact_create_request,
        our_database_session,
    )
    serialized_slides: list[dict[str, str]] | None = _serialize_artifact_slides(
        artifact_create_request,
    )
    created_artifact: Artifact = Artifact(
        brand_id=artifact_create_request.brand_id,
        source_item_id=artifact_create_request.source_item_id,
        cluster_id=artifact_create_request.cluster_id,
        status=artifact_create_request.status,
        format=artifact_create_request.format,
        caption=artifact_create_request.caption,
        cta_url=artifact_create_request.cta_url,
        slides=serialized_slides,
        approved_at=artifact_create_request.approved_at,
    )
    our_database_session.add(created_artifact)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Artifact could not be stored (foreign key conflict).",
    )
    our_database_session.refresh(created_artifact)

    artifact_read_response: ArtifactReadResponse = ArtifactReadResponse.model_validate(
        created_artifact,
    )

    return artifact_read_response


@artifacts_router.get("", response_model=list[ArtifactReadResponse])
def list_artifacts(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[ArtifactReadResponse]:
    """Return every Artifact, newest first."""

    artifact_selection = select(Artifact).order_by(Artifact.created_at.desc())
    artifact_scalars = our_database_session.scalars(artifact_selection)
    artifacts: list[Artifact] = list(artifact_scalars.all())
    artifact_read_responses: list[ArtifactReadResponse] = [
        ArtifactReadResponse.model_validate(artifact) for artifact in artifacts
    ]

    return artifact_read_responses


@artifacts_router.get("/{artifact_id}", response_model=ArtifactReadResponse)
def get_artifact_by_id(
    artifact_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ArtifactReadResponse:
    """Return one Artifact by primary key, including status."""

    found_artifact: Artifact = fetch_artifact_by_id_or_raise(
        artifact_id,
        our_database_session,
    )
    artifact_read_response: ArtifactReadResponse = ArtifactReadResponse.model_validate(
        found_artifact,
    )

    return artifact_read_response


def _require_optional_artifact_parents(
    artifact_create_request: ArtifactCreateRequest,
    our_database_session: Session,
) -> None:
    """404 when optional source-item or cluster FKs do not resolve."""

    if artifact_create_request.source_item_id is not None:
        fetch_source_item_by_id_or_raise(
            artifact_create_request.source_item_id,
            our_database_session,
        )

    if artifact_create_request.cluster_id is not None:
        fetch_cluster_by_id_or_raise(
            artifact_create_request.cluster_id,
            our_database_session,
        )


def _serialize_artifact_slides(
    artifact_create_request: ArtifactCreateRequest,
) -> list[dict[str, str]] | None:
    """Turn slide schemas into JSON-ready dictionaries."""

    if artifact_create_request.slides is None:

        return None

    serialized_slides: list[dict[str, str]] = [
        slide_schema.model_dump(exclude_none=True)
        for slide_schema in artifact_create_request.slides
    ]

    return serialized_slides
