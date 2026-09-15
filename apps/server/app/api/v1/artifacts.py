"""Artifact create/list/get plus review-queue approve/reject/patch (1.5a)."""

from __future__ import annotations

import uuid
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.api.v1.lookups import (
    fetch_artifact_by_id_or_raise,
    fetch_brand_by_id_or_raise,
    fetch_cluster_by_id_or_raise,
    fetch_source_item_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    ArtifactApproveRequest,
    ArtifactCreateRequest,
    ArtifactPatchRequest,
    ArtifactReadResponse,
    ArtifactRejectRequest,
)
from app.approval.errors import (
    ApprovalError,
    ArtifactApprovalTransitionError,
    ArtifactCaptionPatchNotAllowedError,
)
from app.approval.service import (
    approve_artifact,
    patch_artifact_caption_and_cta_url,
    reject_artifact,
)
from app.db import get_our_database_session
from app.models import Artifact
from app.models.enums import ArtifactStatus


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
    artifact_status: Annotated[ArtifactStatus | None, Query(alias="status")] = None,
    our_database_session: Session = Depends(get_our_database_session),
) -> list[ArtifactReadResponse]:
    """Return Artifacts, newest first. Optional `status` is the review queue filter."""

    artifact_selection: Select[tuple[Artifact]] = select(Artifact)
    ordered_artifact_selection: Select[tuple[Artifact]] = artifact_selection.order_by(
        Artifact.created_at.desc(),
    )
    filtered_artifact_selection: Select[tuple[Artifact]]

    if artifact_status is None:
        filtered_artifact_selection = ordered_artifact_selection
    else:
        status_filter = Artifact.status == artifact_status
        filtered_artifact_selection = ordered_artifact_selection.where(status_filter)

    artifact_scalars = our_database_session.scalars(filtered_artifact_selection)
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


@artifacts_router.post("/{artifact_id}/approve", response_model=ArtifactReadResponse)
def approve_artifact_by_id(
    artifact_id: uuid.UUID,
    artifact_approve_request: ArtifactApproveRequest | None = None,
    our_database_session: Session = Depends(get_our_database_session),
) -> ArtifactReadResponse:
    """Approve a draft Artifact; optional caption edit at approve time."""

    found_artifact: Artifact = fetch_artifact_by_id_or_raise(
        artifact_id,
        our_database_session,
    )
    caption_to_apply: str | None = None

    if artifact_approve_request is not None:
        caption_to_apply = artifact_approve_request.caption

    try:
        approve_artifact(found_artifact, caption=caption_to_apply)
    except ApprovalError as approval_error:
        _raise_http_exception_for_approval_error(approval_error)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Artifact could not be approved (conflict).",
    )
    our_database_session.refresh(found_artifact)
    artifact_read_response: ArtifactReadResponse = ArtifactReadResponse.model_validate(
        found_artifact,
    )

    return artifact_read_response


@artifacts_router.post("/{artifact_id}/reject", response_model=ArtifactReadResponse)
def reject_artifact_by_id(
    artifact_id: uuid.UUID,
    artifact_reject_request: ArtifactRejectRequest | None = None,
    our_database_session: Session = Depends(get_our_database_session),
) -> ArtifactReadResponse:
    """Reject a draft or approved Artifact (terminal). `reason` is ignored in MVP."""

    found_artifact: Artifact = fetch_artifact_by_id_or_raise(
        artifact_id,
        our_database_session,
    )
    _ = artifact_reject_request

    try:
        reject_artifact(found_artifact)
    except ApprovalError as approval_error:
        _raise_http_exception_for_approval_error(approval_error)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Artifact could not be rejected (conflict).",
    )
    our_database_session.refresh(found_artifact)
    artifact_read_response: ArtifactReadResponse = ArtifactReadResponse.model_validate(
        found_artifact,
    )

    return artifact_read_response


@artifacts_router.patch("/{artifact_id}", response_model=ArtifactReadResponse)
def patch_artifact_by_id(
    artifact_id: uuid.UUID,
    artifact_patch_request: ArtifactPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> ArtifactReadResponse:
    """Patch caption and/or cta_url while draft or approved (not rejected)."""

    found_artifact: Artifact = fetch_artifact_by_id_or_raise(
        artifact_id,
        our_database_session,
    )
    assigned_fields: set[str] = artifact_patch_request.model_fields_set

    try:
        patch_artifact_caption_and_cta_url(
            found_artifact,
            caption=artifact_patch_request.caption,
            cta_url=artifact_patch_request.cta_url,
            caption_is_set="caption" in assigned_fields,
            cta_url_is_set="cta_url" in assigned_fields,
        )
    except ApprovalError as approval_error:
        _raise_http_exception_for_approval_error(approval_error)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Artifact could not be patched (conflict).",
    )
    our_database_session.refresh(found_artifact)
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


def _raise_http_exception_for_approval_error(approval_error: ApprovalError) -> NoReturn:
    """Map review-queue domain errors to HTTP 409."""

    if isinstance(approval_error, ArtifactApprovalTransitionError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(approval_error),
        ) from approval_error

    if isinstance(approval_error, ArtifactCaptionPatchNotAllowedError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(approval_error),
        ) from approval_error

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(approval_error),
    ) from approval_error
