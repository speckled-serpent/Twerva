"""Post-job metric snapshot routes (1.7a)."""

from __future__ import annotations

import uuid
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_post_job_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    MetricSnapshotReadResponse,
    PostJobMetricsCreateRequest,
)
from app.db import get_our_database_session
from app.metrics.errors import MetricsError, StubMetricsNotAvailableError
from app.metrics.service import append_metric_snapshot, append_stub_metric_snapshot
from app.models import MetricSnapshot, PostJob


metrics_router: APIRouter = APIRouter(prefix="/post-jobs", tags=["metrics"])


@metrics_router.post(
    "/{post_job_id}/metrics",
    response_model=MetricSnapshotReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post_job_metric_snapshot(
    post_job_id: uuid.UUID,
    post_job_metrics_create_request: PostJobMetricsCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> MetricSnapshotReadResponse:
    """Append a `metric_snapshots` row for an existing PostJob."""

    found_post_job: PostJob = fetch_post_job_by_id_or_raise(
        post_job_id,
        our_database_session,
    )
    metric_snapshot: MetricSnapshot = append_metric_snapshot(
        found_post_job,
        views=post_job_metrics_create_request.views,
        likes=post_job_metrics_create_request.likes,
        comments=post_job_metrics_create_request.comments,
        shares=post_job_metrics_create_request.shares,
        captured_at=post_job_metrics_create_request.captured_at,
        raw=post_job_metrics_create_request.raw,
    )
    our_database_session.add(metric_snapshot)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="MetricSnapshot could not be stored (foreign key conflict).",
    )
    our_database_session.refresh(metric_snapshot)
    metric_snapshot_read_response: MetricSnapshotReadResponse = (
        MetricSnapshotReadResponse.model_validate(metric_snapshot)
    )

    return metric_snapshot_read_response


@metrics_router.post(
    "/{post_job_id}/metrics/stub",
    response_model=MetricSnapshotReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stub_post_job_metric_snapshot(
    post_job_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> MetricSnapshotReadResponse:
    """Write documented mock views for a mock-published PostJob (1.7a-ii)."""

    found_post_job: PostJob = fetch_post_job_by_id_or_raise(
        post_job_id,
        our_database_session,
    )
    metric_snapshot: MetricSnapshot

    try:
        metric_snapshot = append_stub_metric_snapshot(found_post_job)
    except MetricsError as metrics_error:
        _raise_http_exception_for_metrics_error(metrics_error)

    our_database_session.add(metric_snapshot)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Stub MetricSnapshot could not be stored (foreign key conflict).",
    )
    our_database_session.refresh(metric_snapshot)
    metric_snapshot_read_response: MetricSnapshotReadResponse = (
        MetricSnapshotReadResponse.model_validate(metric_snapshot)
    )

    return metric_snapshot_read_response


def _raise_http_exception_for_metrics_error(metrics_error: MetricsError) -> NoReturn:
    """Map metrics domain errors to HTTP status codes."""

    if isinstance(metrics_error, StubMetricsNotAvailableError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(metrics_error),
        ) from metrics_error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(metrics_error),
    ) from metrics_error
