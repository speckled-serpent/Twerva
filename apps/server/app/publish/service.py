"""Run one PostJob through a PublishAdapter (1.6c).

Happy path: `scheduled` → `publishing` → `published` with platform
fields and `published_at`. Adapter or media errors: `failed` +
`last_error`.

Retry (1.6c-ii): the same call accepts `failed` and moves it back to
`publishing` (manual re-run). No Redis, no in-process second attempt,
no backoff delay.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.models import Account, Artifact, PostJob
from app.models.enums import POST_JOB_STATUS_TRANSITIONS, PostJobStatus
from app.publish.adapter import PublishAdapter, PublishResult
from app.publish.errors import PostJobNotPublishableError, PostJobStatusTransitionError
from app.publish.media import resolve_artifact_slide_media_paths


PUBLISHABLE_POST_JOB_STATUSES: frozenset[PostJobStatus] = frozenset(
    {PostJobStatus.SCHEDULED, PostJobStatus.FAILED},
)


def publish_post_job(
    post_job: PostJob,
    artifact: Artifact,
    account: Account,
    publish_adapter: PublishAdapter,
    artifact_storage_directory: Path,
    published_at: datetime | None = None,
) -> PostJob:
    """Move a scheduled or failed job through the adapter (not committed).

    `publishing` is set in memory only. The API commits once at the end
    (`published` or `failed`). A crash during the adapter call leaves the
    row `scheduled` or `failed` as it was.

    Args:
        post_job: Row to mutate.
        artifact: Linked artifact (slides + caption).
        account: Linked account (platform for fake/vendor ids).
        publish_adapter: Mock or vendor implementation.
        artifact_storage_directory: `ARTIFACT_STORAGE_DIR` root.
        published_at: Override for tests; default is UTC now.

    Returns:
        The same PostJob after `published` or `failed`.
    """

    require_post_job_is_publishable(post_job)
    apply_post_job_status_transition(post_job, PostJobStatus.PUBLISHING)
    post_job.status = PostJobStatus.PUBLISHING
    post_job.last_error = None

    try:
        media_paths: list[Path] = resolve_artifact_slide_media_paths(
            artifact,
            artifact_storage_directory,
        )
        publish_result: PublishResult = publish_adapter.publish(
            post_job,
            artifact,
            account,
            media_paths,
        )
    except Exception as publish_error:
        apply_post_job_status_transition(post_job, PostJobStatus.FAILED)
        post_job.status = PostJobStatus.FAILED
        post_job.last_error = str(publish_error)

        return post_job

    resolved_published_at: datetime

    if published_at is None:
        resolved_published_at = datetime.now(timezone.utc)
    else:
        resolved_published_at = published_at

    apply_post_job_status_transition(post_job, PostJobStatus.PUBLISHED)
    post_job.status = PostJobStatus.PUBLISHED
    post_job.platform_post_id = publish_result.platform_post_id
    post_job.platform_post_url = publish_result.platform_post_url
    post_job.published_at = resolved_published_at
    post_job.last_error = None

    return post_job


def require_post_job_is_publishable(post_job: PostJob) -> None:
    """Raise when the job is not `scheduled` or `failed`."""

    if post_job.status not in PUBLISHABLE_POST_JOB_STATUSES:
        raise PostJobNotPublishableError(post_job.id, post_job.status)


def apply_post_job_status_transition(
    post_job: PostJob,
    target_status: PostJobStatus,
) -> None:
    """Raise when `POST_JOB_STATUS_TRANSITIONS` does not allow the move."""

    allowed_targets: frozenset[PostJobStatus] = POST_JOB_STATUS_TRANSITIONS.get(
        post_job.status,
        frozenset(),
    )

    if target_status not in allowed_targets:
        raise PostJobStatusTransitionError(
            post_job.id,
            post_job.status,
            target_status,
        )
