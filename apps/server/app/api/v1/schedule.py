"""Schedule route: approved Artifact → PostJob `scheduled` (1.5c)."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_account_by_id_or_raise, fetch_artifact_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import PostJobReadResponse, SchedulePostJobRequest
from app.db import get_our_database_session
from app.models import Account, Artifact, Cluster, PostJob
from app.schedule.errors import (
    ArtifactNotApprovedError,
    CadenceCapExceededError,
    ScheduleBrandMismatchError,
    ScheduleClusterMismatchError,
    ScheduleError,
)
from app.schedule.service import schedule_approved_artifact


schedule_router: APIRouter = APIRouter(tags=["schedule"])


@schedule_router.post(
    "/schedule",
    response_model=PostJobReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def schedule_post_job(
    schedule_post_job_request: SchedulePostJobRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> PostJobReadResponse:
    """Create a `scheduled` PostJob from an approved Artifact."""

    found_artifact: Artifact = fetch_artifact_by_id_or_raise(
        schedule_post_job_request.artifact_id,
        our_database_session,
    )
    found_account: Account = fetch_account_by_id_or_raise(
        schedule_post_job_request.account_id,
        our_database_session,
    )
    found_cluster: Cluster | None = our_database_session.get(
        Cluster,
        found_account.cluster_id,
    )

    if found_cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster not found: {found_account.cluster_id}",
        )

    created_post_job: PostJob

    try:
        created_post_job = schedule_approved_artifact(
            found_artifact,
            found_account,
            found_cluster,
            schedule_post_job_request.scheduled_for,
            our_database_session,
        )
    except ScheduleError as schedule_error:
        _raise_http_exception_for_schedule_error(schedule_error)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="PostJob could not be scheduled (foreign key conflict).",
    )
    our_database_session.refresh(created_post_job)
    post_job_read_response: PostJobReadResponse = PostJobReadResponse.model_validate(
        created_post_job,
    )

    return post_job_read_response


def _raise_http_exception_for_schedule_error(schedule_error: ScheduleError) -> NoReturn:
    """Map schedule domain errors to HTTP status codes."""

    if isinstance(schedule_error, CadenceCapExceededError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(schedule_error),
        ) from schedule_error

    if isinstance(schedule_error, ArtifactNotApprovedError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(schedule_error),
        ) from schedule_error

    if isinstance(schedule_error, ScheduleBrandMismatchError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(schedule_error),
        ) from schedule_error

    if isinstance(schedule_error, ScheduleClusterMismatchError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(schedule_error),
        ) from schedule_error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(schedule_error),
    ) from schedule_error
