"""Cluster metrics summary, steer, and agent-summary routes (1.7b–1.7d)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_cluster_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    AgentSummaryArtifact,
    AgentSummaryPostJob,
    ClusterAgentSummaryResponse,
    ClusterMetricsSummaryResponse,
    ClusterSteerRequest,
    SteerActionReadResponse,
)
from app.db import get_our_database_session
from app.metrics.service import (
    calculate_cluster_median_views,
    fetch_latest_snapshots_by_post_job_ids,
)
from app.models import Artifact, Cluster, MetricSnapshot, PostJob, SteerAction
from app.steer.service import apply_steer_action_to_cluster
from app.steer.summary import (
    fetch_recent_cluster_artifacts,
    fetch_recent_cluster_post_jobs,
    fetch_recent_cluster_steer_actions,
    render_cluster_agent_summary_markdown,
)


steer_router: APIRouter = APIRouter(prefix="/clusters", tags=["steer"])


@steer_router.get(
    "/{cluster_id}/metrics/summary",
    response_model=ClusterMetricsSummaryResponse,
)
def get_cluster_metrics_summary(
    cluster_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ClusterMetricsSummaryResponse:
    """Median latest-wins views across post jobs that have snapshots."""

    fetch_cluster_by_id_or_raise(cluster_id, our_database_session)
    post_job_count: int
    snapshot_job_count: int
    views_job_count: int
    median_views: float | None
    post_job_count, snapshot_job_count, views_job_count, median_views = (
        calculate_cluster_median_views(
            cluster_id,
            our_database_session,
        )
    )
    cluster_metrics_summary_response: ClusterMetricsSummaryResponse = (
        ClusterMetricsSummaryResponse(
            cluster_id=cluster_id,
            post_job_count=post_job_count,
            snapshot_job_count=snapshot_job_count,
            views_job_count=views_job_count,
            median_views=median_views,
        )
    )

    return cluster_metrics_summary_response


@steer_router.post(
    "/{cluster_id}/steer",
    response_model=SteerActionReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cluster_steer_action(
    cluster_id: uuid.UUID,
    cluster_steer_request: ClusterSteerRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> SteerActionReadResponse:
    """Record a steer action and apply pause/kill/resume cluster flags."""

    found_cluster: Cluster = fetch_cluster_by_id_or_raise(
        cluster_id,
        our_database_session,
    )
    steer_action: SteerAction = apply_steer_action_to_cluster(
        found_cluster,
        cluster_steer_request.action,
        reason=cluster_steer_request.reason,
        created_by=cluster_steer_request.created_by,
    )
    our_database_session.add(steer_action)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="SteerAction could not be stored (foreign key conflict).",
    )
    our_database_session.refresh(steer_action)
    our_database_session.refresh(found_cluster)
    steer_action_read_response: SteerActionReadResponse = (
        SteerActionReadResponse.model_validate(steer_action)
    )

    return steer_action_read_response


@steer_router.get(
    "/{cluster_id}/agent-summary",
    response_model=None,
)
def get_cluster_agent_summary(
    cluster_id: uuid.UUID,
    summary_format: Literal["json", "markdown"] = Query(
        default="json",
        alias="format",
    ),
    our_database_session: Session = Depends(get_our_database_session),
) -> ClusterAgentSummaryResponse | Response:
    """JSON (default) or markdown brief of recent jobs, metrics, and steers."""

    found_cluster: Cluster = fetch_cluster_by_id_or_raise(
        cluster_id,
        our_database_session,
    )
    post_job_count: int
    snapshot_job_count: int
    views_job_count: int
    median_views: float | None
    post_job_count, snapshot_job_count, views_job_count, median_views = (
        calculate_cluster_median_views(
            cluster_id,
            our_database_session,
        )
    )
    recent_artifacts: list[Artifact] = fetch_recent_cluster_artifacts(
        cluster_id,
        our_database_session,
    )
    recent_post_jobs: list[PostJob] = fetch_recent_cluster_post_jobs(
        cluster_id,
        our_database_session,
    )
    recent_steer_actions: list[SteerAction] = fetch_recent_cluster_steer_actions(
        cluster_id,
        our_database_session,
    )

    if summary_format == "markdown":
        markdown_body: str = render_cluster_agent_summary_markdown(
            found_cluster,
            post_job_count,
            snapshot_job_count,
            views_job_count,
            median_views,
            recent_artifacts,
            recent_post_jobs,
            recent_steer_actions,
        )
        markdown_response: Response = Response(
            content=markdown_body,
            media_type="text/markdown; charset=utf-8",
        )

        return markdown_response

    cluster_agent_summary_response: ClusterAgentSummaryResponse = (
        _build_cluster_agent_summary_response(
            found_cluster,
            post_job_count,
            snapshot_job_count,
            views_job_count,
            median_views,
            recent_artifacts,
            recent_post_jobs,
            recent_steer_actions,
            our_database_session,
        )
    )

    return cluster_agent_summary_response


def _build_cluster_agent_summary_response(
    cluster: Cluster,
    post_job_count: int,
    snapshot_job_count: int,
    views_job_count: int,
    median_views: float | None,
    artifacts: list[Artifact],
    post_jobs: list[PostJob],
    steer_actions: list[SteerAction],
    our_database_session: Session,
) -> ClusterAgentSummaryResponse:
    """Assemble the JSON agent-summary payload."""

    metrics_summary: ClusterMetricsSummaryResponse = ClusterMetricsSummaryResponse(
        cluster_id=cluster.id,
        post_job_count=post_job_count,
        snapshot_job_count=snapshot_job_count,
        views_job_count=views_job_count,
        median_views=median_views,
    )
    agent_summary_artifacts: list[AgentSummaryArtifact] = [
        AgentSummaryArtifact(
            id=artifact.id,
            status=artifact.status,
            caption=artifact.caption,
            created_at=artifact.created_at,
        )
        for artifact in artifacts
    ]
    post_job_ids: list[uuid.UUID] = [post_job.id for post_job in post_jobs]
    latest_snapshot_by_post_job_id: dict[uuid.UUID, MetricSnapshot] = (
        fetch_latest_snapshots_by_post_job_ids(
            post_job_ids,
            our_database_session,
        )
    )
    agent_summary_post_jobs: list[AgentSummaryPostJob] = []

    for post_job in post_jobs:
        latest_snapshot: MetricSnapshot | None = latest_snapshot_by_post_job_id.get(
            post_job.id,
        )
        latest_views: int | None
        latest_captured_at: datetime | None

        if latest_snapshot is None:
            latest_views = None
            latest_captured_at = None
        elif latest_snapshot.views is None:
            latest_views = None
            latest_captured_at = latest_snapshot.captured_at
        else:
            latest_views = int(latest_snapshot.views)
            latest_captured_at = latest_snapshot.captured_at

        agent_summary_post_jobs.append(
            AgentSummaryPostJob(
                id=post_job.id,
                status=post_job.status,
                platform_post_id=post_job.platform_post_id,
                published_at=post_job.published_at,
                latest_views=latest_views,
                latest_captured_at=latest_captured_at,
            ),
        )

    steer_action_read_responses: list[SteerActionReadResponse] = [
        SteerActionReadResponse.model_validate(steer_action)
        for steer_action in steer_actions
    ]
    cluster_agent_summary_response: ClusterAgentSummaryResponse = (
        ClusterAgentSummaryResponse(
            cluster_id=cluster.id,
            slug=cluster.slug,
            name=cluster.name,
            is_active=cluster.is_active,
            metrics=metrics_summary,
            recent_artifacts=agent_summary_artifacts,
            recent_post_jobs=agent_summary_post_jobs,
            recent_steer_actions=steer_action_read_responses,
        )
    )

    return cluster_agent_summary_response
