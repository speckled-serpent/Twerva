"""Publish route: run a scheduled PostJob through the adapter (1.6c)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_account_by_id_or_raise,
    fetch_artifact_by_id_or_raise,
    fetch_post_job_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import PostJobReadResponse
from app.db import get_our_database_session
from app.models import Account, Artifact, PostJob
from app.publish.adapter import PublishAdapter
from app.publish.errors import (
    PostJobNotPublishableError,
    PublishAdapterNotConfiguredError,
    PublishAdapterUnknownError,
    PublishError,
)
from app.publish.factory import get_publish_adapter
from app.publish.service import publish_post_job
from app.settings import get_settings
from app.storage.artifacts import ensure_artifact_storage_directory


publish_router: APIRouter = APIRouter(prefix="/publish", tags=["publish"])


@publish_router.post(
    "/run/{post_job_id}",
    response_model=PostJobReadResponse,
)
def publish_post_job_by_id(
    post_job_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> PostJobReadResponse:
    """Mock-publish (default) a `scheduled` or `failed` PostJob."""

    found_post_job: PostJob = fetch_post_job_by_id_or_raise(
        post_job_id,
        our_database_session,
    )
    found_artifact: Artifact = fetch_artifact_by_id_or_raise(
        found_post_job.artifact_id,
        our_database_session,
    )
    found_account: Account = fetch_account_by_id_or_raise(
        found_post_job.account_id,
        our_database_session,
    )
    publish_adapter: PublishAdapter

    try:
        publish_adapter = get_publish_adapter()
    except PublishError as adapter_selection_error:
        _raise_http_exception_for_publish_error(adapter_selection_error)

    artifact_storage_directory: Path = ensure_artifact_storage_directory(
        Path(get_settings().artifact_storage_dir),
    )

    try:
        publish_post_job(
            found_post_job,
            found_artifact,
            found_account,
            publish_adapter,
            artifact_storage_directory,
        )
    except PublishError as publish_error:
        _raise_http_exception_for_publish_error(publish_error)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="PostJob could not be published (foreign key conflict).",
    )
    our_database_session.refresh(found_post_job)
    post_job_read_response: PostJobReadResponse = PostJobReadResponse.model_validate(
        found_post_job,
    )

    return post_job_read_response


def _raise_http_exception_for_publish_error(publish_error: PublishError) -> NoReturn:
    """Map publish domain errors to HTTP status codes."""

    if isinstance(publish_error, PostJobNotPublishableError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(publish_error),
        ) from publish_error

    if isinstance(publish_error, PublishAdapterNotConfiguredError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(publish_error),
        ) from publish_error

    if isinstance(publish_error, PublishAdapterUnknownError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(publish_error),
        ) from publish_error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(publish_error),
    ) from publish_error
