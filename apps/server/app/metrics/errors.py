"""Domain errors for metric capture and the mock stub puller."""

from __future__ import annotations

import uuid

from app.models.enums import PostJobStatus


class MetricsError(Exception):
    """Base error for metric snapshot writes."""


class StubMetricsNotAvailableError(MetricsError):
    """Stub puller only writes snapshots for mock-published jobs."""

    def __init__(
        self,
        post_job_id: uuid.UUID,
        platform_post_id: str | None,
        current_status: PostJobStatus,
    ) -> None:

        super().__init__(
            (
                f"Stub metrics are only written for mock-published jobs "
                f"(platform_post_id starting with 'mock-'). "
                f"PostJob {post_job_id} status={current_status.value} "
                f"platform_post_id={platform_post_id!r}."
            ),
        )
        self.post_job_id: uuid.UUID = post_job_id
        self.platform_post_id: str | None = platform_post_id
        self.current_status: PostJobStatus = current_status
