"""Place one assembled carousel on a campaign timeline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.schemas import CampaignPostResultsRead, TimelinePostRead
from app.models.account import Account
from app.models.artifact import Artifact
from app.models.campaign import (
    CAMPAIGN_POST_FAILED_STATUS,
    CAMPAIGN_POST_POSTED_STATUS,
    CAMPAIGN_POST_UPCOMING_STATUS,
    Campaign,
    CampaignAccount,
    CampaignPost,
)
from app.models.carousel import AssembledCarousel, AssembledCarouselFrame, CarouselAssembly
from app.models.enums import PostJobStatus
from app.models.metric_snapshot import MetricSnapshot
from app.models.post_job import PostJob
from app.publish.adapter import PublishResult
from app.publish.errors import PublishMediaMissingError
from app.publish.factory import get_publish_adapter
from app.publish.media import resolve_asset_reference_path
from app.schedule.cadence import raise_if_cadence_cap_exceeded
from app.settings import get_settings
from app.storage.artifacts import ensure_artifact_storage_directory


CAMPAIGN_POST_NEEDS_CAROUSEL_DETAIL: str = (
    "Pick a carousel before scheduling a post."
)
CAMPAIGN_POST_ACCOUNT_DETAIL: str = "That account is not on this campaign."
CAMPAIGN_POST_BLOCKED_DETAIL: str = (
    "This carousel is blocked. Assemble again before posting it."
)
CAMPAIGN_POST_DUPLICATE_DETAIL: str = (
    "This carousel is already scheduled on that account."
)
ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL: str = "Assembled carousel not found."
CAMPAIGN_POST_NOT_FOUND_DETAIL: str = "Campaign post not found."
CAMPAIGN_POST_ONLY_UPCOMING_DETAIL: str = (
    "Only an upcoming post can change its time."
)
CAMPAIGN_POST_STAYS_DETAIL: str = "This post stays on the timeline."
CAMPAIGN_POST_ALREADY_UP_DETAIL: str = "This post is already up."
PUBLISHABLE_CAMPAIGN_POST_STATUSES: frozenset[str] = frozenset(
    {CAMPAIGN_POST_UPCOMING_STATUS, CAMPAIGN_POST_FAILED_STATUS},
)


def place_campaign_post(
    campaign: Campaign,
    assembled_carousel_id: uuid.UUID,
    account_id: uuid.UUID,
    scheduled_for: datetime,
    our_database_session: Session,
) -> CampaignPost:
    """Store an upcoming post for one assembled carousel and linked account.

    The campaign status is not consulted. Nothing is added when a check
    fails. The caller commits.

    Args:
        campaign: Campaign that will own the post.
        assembled_carousel_id: Reviewed carousel to place.
        account_id: Linked account that will carry the post.
        scheduled_for: Clock time the operator chose.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The flushed upcoming post, with its carousel, frames, and account
        loaded.

    Raises:
        HTTPException: The carousel is missing, the account is not linked,
            a frame is blocked, or this pair is already scheduled.
        CadenceCapExceededError: The account cap is already met.
    """

    if campaign.carousel_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_NEEDS_CAROUSEL_DETAIL,
        )

    assembled_carousel: AssembledCarousel | None = our_database_session.scalars(
        select(AssembledCarousel)
        .where(AssembledCarousel.id == assembled_carousel_id)
        .options(
            selectinload(AssembledCarousel.frames),
            selectinload(AssembledCarousel.assembly),
        ),
    ).first()

    if assembled_carousel is None or assembled_carousel.assembly.carousel_id != campaign.carousel_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL,
        )

    account_link: CampaignAccount | None = our_database_session.scalars(
        select(CampaignAccount).where(
            CampaignAccount.campaign_id == campaign.id,
            CampaignAccount.account_id == account_id,
        ),
    ).first()

    if account_link is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_ACCOUNT_DETAIL,
        )

    if _assembled_carousel_is_blocked(assembled_carousel):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_BLOCKED_DETAIL,
        )

    existing_post: CampaignPost | None = our_database_session.scalars(
        select(CampaignPost).where(
            CampaignPost.assembled_carousel_id == assembled_carousel.id,
            CampaignPost.account_id == account_id,
        ),
    ).first()

    if existing_post is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CAMPAIGN_POST_DUPLICATE_DETAIL,
        )

    linked_account: Account | None = our_database_session.get(Account, account_id)

    if linked_account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_ACCOUNT_DETAIL,
        )

    raise_if_cadence_cap_exceeded(
        linked_account,
        scheduled_for,
        our_database_session,
    )
    created_post: CampaignPost = CampaignPost(
        campaign_id=campaign.id,
        assembled_carousel_id=assembled_carousel.id,
        account_id=account_id,
        status=CAMPAIGN_POST_UPCOMING_STATUS,
        scheduled_for=scheduled_for,
        published_at=None,
        platform_post_id=None,
        platform_post_url=None,
        last_error=None,
    )
    our_database_session.add(created_post)
    our_database_session.flush()
    loaded_post: CampaignPost = _load_campaign_post(
        created_post.id,
        our_database_session,
    )

    return loaded_post


def reschedule_campaign_post(
    campaign: Campaign,
    campaign_post_id: uuid.UUID,
    scheduled_for: datetime,
    our_database_session: Session,
) -> CampaignPost:
    """Move an upcoming post to a new time.

    The post's own row is left out of the cadence count, so a later
    hour on the same day still fits a cap of one. Caption, frames,
    account, and status stay. The caller commits.

    Args:
        campaign: Campaign that must own the post.
        campaign_post_id: Post to move.
        scheduled_for: New clock time.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The post after the time is stored.

    Raises:
        HTTPException: The post is missing, belongs to another campaign,
            or is not upcoming.
        CadenceCapExceededError: The new UTC day is already at the cap.
            ``scheduled_for`` is left unchanged.
    """

    stored_post: CampaignPost = _require_upcoming_post(
        campaign,
        campaign_post_id,
        our_database_session,
        CAMPAIGN_POST_ONLY_UPCOMING_DETAIL,
    )
    linked_account: Account | None = our_database_session.get(
        Account,
        stored_post.account_id,
    )

    if linked_account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_ACCOUNT_DETAIL,
        )

    raise_if_cadence_cap_exceeded(
        linked_account,
        scheduled_for,
        our_database_session,
        stored_post.id,
    )
    stored_post.scheduled_for = scheduled_for
    our_database_session.flush()
    loaded_post: CampaignPost = _load_campaign_post(
        stored_post.id,
        our_database_session,
    )

    return loaded_post


def remove_campaign_post(
    campaign: Campaign,
    campaign_post_id: uuid.UUID,
    our_database_session: Session,
) -> None:
    """Delete an upcoming post. The assembled carousel and frames stay.

    Args:
        campaign: Campaign that must own the post.
        campaign_post_id: Post to remove.
        our_database_session: Open SQLAlchemy session.

    Raises:
        HTTPException: The post is missing, belongs to another campaign,
            or is already posted or failed.
    """

    stored_post: CampaignPost = _require_upcoming_post(
        campaign,
        campaign_post_id,
        our_database_session,
        CAMPAIGN_POST_STAYS_DETAIL,
    )
    our_database_session.delete(stored_post)
    our_database_session.flush()


def publish_campaign_post(
    campaign: Campaign,
    campaign_post_id: uuid.UUID,
    our_database_session: Session,
) -> CampaignPost:
    """Publish an upcoming or failed post through the configured adapter.

    The caption is the assembled carousel's caption. Null is sent as an
    empty string. The clock and the campaign status are not consulted.
    A missing frame file, a path that leaves the store, or an adapter
    exception stores ``failed`` and ``last_error`` and leaves
    ``published_at`` null. The caller commits. This does not insert an
    artifact or a post job.

    Args:
        campaign: Campaign that must own the post.
        campaign_post_id: Post to publish.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The post after it is ``posted`` or ``failed``.

    Raises:
        HTTPException: The post is missing, belongs to another campaign,
            or is already posted.
    """

    stored_post: CampaignPost = _require_publishable_post(
        campaign,
        campaign_post_id,
        our_database_session,
    )
    linked_account: Account | None = our_database_session.get(
        Account,
        stored_post.account_id,
    )

    if linked_account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_ACCOUNT_DETAIL,
        )

    try:
        media_paths: list[Path] = _frame_media_paths(stored_post)
        caption_text: str = _caption_for_publish(stored_post)
        publish_result: PublishResult = get_publish_adapter().publish_media(
            stored_post.id,
            linked_account,
            media_paths,
            caption_text,
        )
    except Exception as publish_error:
        stored_post.status = CAMPAIGN_POST_FAILED_STATUS
        stored_post.last_error = str(publish_error)
        stored_post.published_at = None
    else:
        stored_post.status = CAMPAIGN_POST_POSTED_STATUS
        stored_post.published_at = datetime.now(timezone.utc)
        stored_post.platform_post_id = publish_result.platform_post_id
        stored_post.platform_post_url = publish_result.platform_post_url
        stored_post.last_error = None

    our_database_session.flush()
    loaded_post: CampaignPost = _load_campaign_post(
        stored_post.id,
        our_database_session,
    )

    return loaded_post


def _caption_for_publish(stored_post: CampaignPost) -> str:
    """Return the caption assemble stored. Null becomes an empty string."""

    stored_caption: str | None = stored_post.assembled_carousel.caption

    if stored_caption is None:

        return ""

    return stored_caption


def _frame_media_paths(post: CampaignPost) -> list[Path]:
    """Resolve frame files in position order under the artifact store."""

    storage_directory: Path = ensure_artifact_storage_directory(
        Path(get_settings().artifact_storage_dir),
    )
    media_paths: list[Path] = []

    for frame in ordered_frames(post.assembled_carousel):
        resolved_path: Path = resolve_asset_reference_path(
            frame.asset_ref,
            storage_directory,
        )

        if not resolved_path.is_file():
            raise PublishMediaMissingError(frame.asset_ref, resolved_path)

        media_paths.append(resolved_path)

    return media_paths


def _require_publishable_post(
    campaign: Campaign,
    campaign_post_id: uuid.UUID,
    our_database_session: Session,
) -> CampaignPost:
    """Return an upcoming or failed post with its frames loaded."""

    stored_post: CampaignPost | None = our_database_session.scalars(
        select(CampaignPost)
        .where(CampaignPost.id == campaign_post_id)
        .options(
            selectinload(CampaignPost.assembled_carousel).selectinload(
                AssembledCarousel.frames,
            ),
            selectinload(CampaignPost.account),
        ),
    ).first()

    if stored_post is None or stored_post.campaign_id != campaign.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CAMPAIGN_POST_NOT_FOUND_DETAIL,
        )

    if stored_post.status not in PUBLISHABLE_CAMPAIGN_POST_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CAMPAIGN_POST_ALREADY_UP_DETAIL,
        )

    return stored_post


def _require_upcoming_post(
    campaign: Campaign,
    campaign_post_id: uuid.UUID,
    our_database_session: Session,
    blocked_status_detail: str,
) -> CampaignPost:
    """Return the upcoming post, or raise 404 or 409."""

    stored_post: CampaignPost | None = our_database_session.get(
        CampaignPost,
        campaign_post_id,
    )

    if stored_post is None or stored_post.campaign_id != campaign.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CAMPAIGN_POST_NOT_FOUND_DETAIL,
        )

    if stored_post.status != CAMPAIGN_POST_UPCOMING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=blocked_status_detail,
        )

    return stored_post


def _assembled_carousel_is_blocked(assembled_carousel: AssembledCarousel) -> bool:
    """Return whether any frozen frame is blocked."""

    frame_is_blocked: bool = any(
        frame.blocked for frame in assembled_carousel.frames
    )

    return frame_is_blocked


def _load_campaign_post(
    campaign_post_id: uuid.UUID,
    our_database_session: Session,
) -> CampaignPost:
    """Return one post with the rows the read model needs."""

    loaded_post: CampaignPost | None = our_database_session.scalars(
        select(CampaignPost)
        .where(CampaignPost.id == campaign_post_id)
        .options(
            selectinload(CampaignPost.assembled_carousel).selectinload(
                AssembledCarousel.frames,
            ),
            selectinload(CampaignPost.assembled_carousel).selectinload(
                AssembledCarousel.assembly,
            ),
            selectinload(CampaignPost.account),
            selectinload(CampaignPost.metric_snapshots),
        ),
    ).first()

    if loaded_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL,
        )

    return loaded_post


def ordered_frames(
    assembled_carousel: AssembledCarousel,
) -> list[AssembledCarouselFrame]:
    """Return frames in position order."""

    ordered: list[AssembledCarouselFrame] = sorted(
        list(assembled_carousel.frames),
        key=lambda frame: frame.position,
    )

    return ordered


POST_JOB_TIMELINE_STATUS: dict[PostJobStatus, str] = {
    PostJobStatus.SCHEDULED: CAMPAIGN_POST_UPCOMING_STATUS,
    PostJobStatus.PUBLISHING: CAMPAIGN_POST_UPCOMING_STATUS,
    PostJobStatus.PUBLISHED: CAMPAIGN_POST_POSTED_STATUS,
    PostJobStatus.MEASURED: CAMPAIGN_POST_POSTED_STATUS,
    PostJobStatus.FAILED: CAMPAIGN_POST_FAILED_STATUS,
}


def list_timeline_posts(our_database_session: Session) -> list[TimelinePostRead]:
    """Return campaign posts and post jobs, soonest scheduled time first.

    A post job with no time sorts after every timed row. Artifacts that
    were never given a post job are left out. Post jobs are not copied.

    Args:
        our_database_session: Open SQLAlchemy session.

    Returns:
        Timeline rows in ``scheduled_for`` order, then id.
    """

    campaign_posts: list[CampaignPost] = list(
        our_database_session.scalars(
            select(CampaignPost).options(
                selectinload(CampaignPost.account),
                selectinload(CampaignPost.campaign),
                selectinload(CampaignPost.metric_snapshots),
                selectinload(CampaignPost.assembled_carousel),
            ),
        ).all(),
    )
    post_jobs: list[PostJob] = list(
        our_database_session.scalars(
            select(PostJob).options(
                selectinload(PostJob.account),
                selectinload(PostJob.artifact),
                selectinload(PostJob.metric_snapshots),
            ),
        ).all(),
    )
    timeline_rows: list[TimelinePostRead] = [
        _timeline_row_from_campaign_post(post) for post in campaign_posts
    ]
    timeline_rows.extend(
        _timeline_row_from_post_job(post_job) for post_job in post_jobs
    )
    timeline_rows.sort(key=_timeline_sort_key)

    return timeline_rows


def latest_snapshot_results(
    snapshots: list[MetricSnapshot],
) -> CampaignPostResultsRead | None:
    """Return the snapshot with the greatest captured_at, or null."""

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


def _timeline_row_from_campaign_post(post: CampaignPost) -> TimelinePostRead:
    """Map one campaign post onto the cross-campaign list."""

    timeline_row: TimelinePostRead = TimelinePostRead(
        origin="campaign_post",
        id=post.id,
        status=post.status,
        scheduled_for=post.scheduled_for,
        published_at=post.published_at,
        campaign_id=post.campaign_id,
        campaign_name=post.campaign.name,
        account_id=post.account_id,
        platform=post.account.platform,
        handle=post.account.handle,
        caption=post.assembled_carousel.caption,
        results=latest_snapshot_results(list(post.metric_snapshots)),
    )

    return timeline_row


def _timeline_row_from_post_job(post_job: PostJob) -> TimelinePostRead:
    """Map one post job onto the cross-campaign list."""

    artifact: Artifact = post_job.artifact
    timeline_status: str = POST_JOB_TIMELINE_STATUS[post_job.status]
    timeline_row: TimelinePostRead = TimelinePostRead(
        origin="post_job",
        id=post_job.id,
        status=timeline_status,
        scheduled_for=post_job.scheduled_for,
        published_at=post_job.published_at,
        campaign_id=None,
        campaign_name=None,
        account_id=post_job.account_id,
        platform=post_job.account.platform,
        handle=post_job.account.handle,
        caption=artifact.caption,
        results=latest_snapshot_results(list(post_job.metric_snapshots)),
    )

    return timeline_row


def _timeline_sort_key(row: TimelinePostRead) -> tuple[int, datetime, str]:
    """Sort timed rows first, then by time, then by id."""

    if row.scheduled_for is None:
        sort_key: tuple[int, datetime, str] = (
            1,
            datetime.max.replace(tzinfo=timezone.utc),
            str(row.id),
        )

        return sort_key

    sort_key = (0, row.scheduled_for, str(row.id))

    return sort_key


def assembly_for_post(post: CampaignPost) -> CarouselAssembly:
    """Return the assembly that owns this post's carousel."""

    assembly: CarouselAssembly = post.assembled_carousel.assembly

    return assembly
