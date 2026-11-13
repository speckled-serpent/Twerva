"""Place an assembled carousel on a campaign timeline."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_campaign_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    CampaignPostCreateRequest,
    CampaignPostFrameRead,
    CampaignPostRead,
    CampaignPostRescheduleRequest,
    CampaignPostResultsRead,
    MetricSnapshotReadResponse,
    PostJobMetricsCreateRequest,
)
from app.auth.dependencies import require_admin_ops_operator
from app.campaigns.posts import (
    assembly_for_post,
    ordered_frames,
    place_campaign_post,
    publish_campaign_post,
    remove_campaign_post,
    reschedule_campaign_post,
)
from app.db import get_our_database_session
from app.metrics.errors import MetricsError, StubMetricsNotAvailableError
from app.metrics.service import (
    append_campaign_post_metric,
    append_campaign_post_stub_metric,
)
from app.models.campaign import CAMPAIGN_POST_POSTED_STATUS, Campaign, CampaignPost
from app.models.metric_snapshot import MetricSnapshot
from app.models.carousel import AssembledCarouselFrame, CarouselAssembly
from app.models.ops_user import OpsUser
from app.schedule.errors import CadenceCapExceededError


RECORD_RESULTS_AFTER_POST_DETAIL: str = "Record results after the post is up."


def register_campaign_post_routes(campaigns_router: APIRouter) -> None:
    """Attach the campaign timeline routes.

    Args:
        campaigns_router: Router mounted at ``/campaigns``.
    """

    campaigns_router.add_api_route(
        "/{campaign_id}/posts",
        place_campaign_post_by_id,
        methods=["POST"],
        response_model=CampaignPostRead,
        status_code=status.HTTP_201_CREATED,
    )
    campaigns_router.add_api_route(
        "/{campaign_id}/posts/{post_id}",
        reschedule_campaign_post_by_id,
        methods=["PATCH"],
        response_model=CampaignPostRead,
    )
    campaigns_router.add_api_route(
        "/{campaign_id}/posts/{post_id}",
        remove_campaign_post_by_id,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    campaigns_router.add_api_route(
        "/{campaign_id}/posts/{post_id}/publish",
        publish_campaign_post_by_id,
        methods=["POST"],
        response_model=CampaignPostRead,
    )
    campaigns_router.add_api_route(
        "/{campaign_id}/posts/{post_id}/metrics",
        create_campaign_post_metric_snapshot,
        methods=["POST"],
        response_model=MetricSnapshotReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    campaigns_router.add_api_route(
        "/{campaign_id}/posts/{post_id}/metrics/stub",
        create_campaign_post_stub_metric_snapshot,
        methods=["POST"],
        response_model=MetricSnapshotReadResponse,
        status_code=status.HTTP_201_CREATED,
    )


def place_campaign_post_by_id(
    campaign_id: uuid.UUID,
    campaign_post_create_request: CampaignPostCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CampaignPostRead:
    """Place one assembled carousel on the campaign timeline.

    Readers cannot call this. The campaign status is not consulted.
    """

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )
    created_post: CampaignPost

    try:
        created_post = place_campaign_post(
            found_campaign,
            campaign_post_create_request.assembled_carousel_id,
            campaign_post_create_request.account_id,
            campaign_post_create_request.scheduled_for,
            our_database_session,
        )
    except CadenceCapExceededError as cadence_error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(cadence_error),
        ) from cadence_error

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Campaign post could not be saved.",
    )
    campaign_post_read: CampaignPostRead = serialize_campaign_post(created_post)

    return campaign_post_read


def reschedule_campaign_post_by_id(
    campaign_id: uuid.UUID,
    post_id: uuid.UUID,
    campaign_post_reschedule_request: CampaignPostRescheduleRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CampaignPostRead:
    """Move an upcoming post. Readers cannot call this."""

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )
    moved_post: CampaignPost

    try:
        moved_post = reschedule_campaign_post(
            found_campaign,
            post_id,
            campaign_post_reschedule_request.scheduled_for,
            our_database_session,
        )
    except CadenceCapExceededError as cadence_error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(cadence_error),
        ) from cadence_error

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Campaign post could not be saved.",
    )
    campaign_post_read: CampaignPostRead = serialize_campaign_post(moved_post)

    return campaign_post_read


def remove_campaign_post_by_id(
    campaign_id: uuid.UUID,
    post_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> None:
    """Take an upcoming post off the timeline. Readers cannot call this."""

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )
    remove_campaign_post(found_campaign, post_id, our_database_session)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Campaign post could not be removed.",
    )


def publish_campaign_post_by_id(
    campaign_id: uuid.UUID,
    post_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CampaignPostRead:
    """Publish an upcoming or failed post. Readers cannot call this.

    The body is empty. A failed adapter or a missing file is stored on
    the post and still returned.
    """

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )
    published_post: CampaignPost = publish_campaign_post(
        found_campaign,
        post_id,
        our_database_session,
    )
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Campaign post could not be published.",
    )
    campaign_post_read: CampaignPostRead = serialize_campaign_post(published_post)

    return campaign_post_read


def create_campaign_post_metric_snapshot(
    campaign_id: uuid.UUID,
    post_id: uuid.UUID,
    post_metrics_create_request: PostJobMetricsCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> MetricSnapshotReadResponse:
    """Append a result snapshot for a posted carousel. Readers cannot call this."""

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )
    found_post: CampaignPost = _require_posted_campaign_post(
        found_campaign,
        post_id,
        our_database_session,
    )
    metric_snapshot: MetricSnapshot = append_campaign_post_metric(
        found_post,
        views=post_metrics_create_request.views,
        likes=post_metrics_create_request.likes,
        comments=post_metrics_create_request.comments,
        shares=post_metrics_create_request.shares,
        captured_at=post_metrics_create_request.captured_at,
        raw=post_metrics_create_request.raw,
    )
    metric_snapshot_read: MetricSnapshotReadResponse = _store_metric_snapshot(
        metric_snapshot,
        our_database_session,
    )

    return metric_snapshot_read


def create_campaign_post_stub_metric_snapshot(
    campaign_id: uuid.UUID,
    post_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> MetricSnapshotReadResponse:
    """Copy sample mock counts onto a posted carousel. Readers cannot call this."""

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )
    found_post: CampaignPost = _require_posted_campaign_post(
        found_campaign,
        post_id,
        our_database_session,
    )
    metric_snapshot: MetricSnapshot

    try:
        metric_snapshot = append_campaign_post_stub_metric(found_post)
    except MetricsError as metrics_error:
        _raise_http_exception_for_campaign_post_metrics(metrics_error)

    metric_snapshot_read: MetricSnapshotReadResponse = _store_metric_snapshot(
        metric_snapshot,
        our_database_session,
    )

    return metric_snapshot_read


def _require_posted_campaign_post(
    campaign: Campaign,
    campaign_post_id: uuid.UUID,
    our_database_session: Session,
) -> CampaignPost:
    """Return a posted carousel, or raise 404 or 409."""

    stored_post: CampaignPost | None = our_database_session.get(
        CampaignPost,
        campaign_post_id,
    )

    if stored_post is None or stored_post.campaign_id != campaign.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign post not found.",
        )

    if stored_post.status != CAMPAIGN_POST_POSTED_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=RECORD_RESULTS_AFTER_POST_DETAIL,
        )

    return stored_post


def _store_metric_snapshot(
    metric_snapshot: MetricSnapshot,
    our_database_session: Session,
) -> MetricSnapshotReadResponse:
    """Commit one snapshot and return the read model."""

    our_database_session.add(metric_snapshot)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="MetricSnapshot could not be stored (foreign key conflict).",
    )
    our_database_session.refresh(metric_snapshot)
    metric_snapshot_read: MetricSnapshotReadResponse = (
        MetricSnapshotReadResponse.model_validate(metric_snapshot)
    )

    return metric_snapshot_read


def _raise_http_exception_for_campaign_post_metrics(
    metrics_error: MetricsError,
) -> None:
    """Map a stub refusal to HTTP 409."""

    if isinstance(metrics_error, StubMetricsNotAvailableError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(metrics_error),
        ) from metrics_error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(metrics_error),
    ) from metrics_error


def serialize_campaign_post(post: CampaignPost) -> CampaignPostRead:
    """Map one stored post to the read model."""

    assembly: CarouselAssembly = assembly_for_post(post)
    frames: list[AssembledCarouselFrame] = ordered_frames(post.assembled_carousel)
    frame_reads: list[CampaignPostFrameRead] = [
        CampaignPostFrameRead(
            id=frame.id,
            position=frame.position,
            blocked=frame.blocked,
            block_reason=frame.block_reason,
            block_detail=frame.block_detail,
        )
        for frame in frames
    ]
    post_is_blocked: bool = any(frame.blocked for frame in frames)
    campaign_post_read: CampaignPostRead = CampaignPostRead(
        id=post.id,
        campaign_id=post.campaign_id,
        carousel_id=assembly.carousel_id,
        generation_number=assembly.generation_number,
        assembled_carousel_id=post.assembled_carousel_id,
        account_id=post.account_id,
        platform=post.account.platform,
        handle=post.account.handle,
        status=post.status,
        scheduled_for=post.scheduled_for,
        published_at=post.published_at,
        platform_post_id=post.platform_post_id,
        platform_post_url=post.platform_post_url,
        last_error=post.last_error,
        caption=post.assembled_carousel.caption,
        cta_url=post.assembled_carousel.cta_url,
        blocked=post_is_blocked,
        frames=frame_reads,
        results=_latest_campaign_post_results(post),
    )

    return campaign_post_read


def _latest_campaign_post_results(post: CampaignPost) -> CampaignPostResultsRead | None:
    """Return the snapshot with the greatest captured_at, or null."""

    snapshots: list[MetricSnapshot] = list(post.metric_snapshots)

    if len(snapshots) == 0:
        return None

    latest_snapshot: MetricSnapshot = max(
        snapshots,
        key=lambda snapshot: snapshot.captured_at,
    )
    results: CampaignPostResultsRead = CampaignPostResultsRead(
        captured_at=latest_snapshot.captured_at,
        views=latest_snapshot.views,
        likes=latest_snapshot.likes,
        comments=latest_snapshot.comments,
        shares=latest_snapshot.shares,
    )

    return results
