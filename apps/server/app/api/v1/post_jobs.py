"""PostJob create/list/get routes (status is part of the payload)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_account_by_id_or_raise,
    fetch_artifact_by_id_or_raise,
    fetch_post_job_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import PostJobCreateRequest, PostJobReadResponse
from app.db import get_our_database_session
from app.models import PostJob


post_jobs_router: APIRouter = APIRouter(prefix="/post-jobs", tags=["post-jobs"])


@post_jobs_router.post(
    "",
    response_model=PostJobReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post_job(
    post_job_create_request: PostJobCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> PostJobReadResponse:
    """Persist a PostJob, including its status field."""

    fetch_artifact_by_id_or_raise(
        post_job_create_request.artifact_id,
        our_database_session,
    )
    fetch_account_by_id_or_raise(
        post_job_create_request.account_id,
        our_database_session,
    )
    created_post_job: PostJob = PostJob(
        artifact_id=post_job_create_request.artifact_id,
        account_id=post_job_create_request.account_id,
        status=post_job_create_request.status,
        scheduled_for=post_job_create_request.scheduled_for,
        published_at=post_job_create_request.published_at,
        platform_post_id=post_job_create_request.platform_post_id,
        platform_post_url=post_job_create_request.platform_post_url,
        last_error=post_job_create_request.last_error,
    )
    our_database_session.add(created_post_job)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="PostJob could not be stored (foreign key conflict).",
    )
    our_database_session.refresh(created_post_job)

    post_job_read_response: PostJobReadResponse = PostJobReadResponse.model_validate(
        created_post_job,
    )

    return post_job_read_response


@post_jobs_router.get("", response_model=list[PostJobReadResponse])
def list_post_jobs(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[PostJobReadResponse]:
    """Return every PostJob, newest first."""

    post_job_selection = select(PostJob).order_by(PostJob.created_at.desc())
    post_job_scalars = our_database_session.scalars(post_job_selection)
    post_jobs: list[PostJob] = list(post_job_scalars.all())
    post_job_read_responses: list[PostJobReadResponse] = [
        PostJobReadResponse.model_validate(post_job) for post_job in post_jobs
    ]

    return post_job_read_responses


@post_jobs_router.get("/{post_job_id}", response_model=PostJobReadResponse)
def get_post_job_by_id(
    post_job_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> PostJobReadResponse:
    """Return one PostJob by primary key, including status."""

    found_post_job: PostJob = fetch_post_job_by_id_or_raise(
        post_job_id,
        our_database_session,
    )
    post_job_read_response: PostJobReadResponse = PostJobReadResponse.model_validate(
        found_post_job,
    )

    return post_job_read_response
