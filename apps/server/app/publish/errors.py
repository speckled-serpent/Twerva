"""Domain errors for publish adapter selection, media, and status."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.models.enums import PostJobStatus


class PublishError(Exception):
    """Base error for publish runs and adapter selection."""


class PostJobNotPublishableError(PublishError):
    """Only `scheduled` or `failed` PostJobs may enter `publishing`."""

    def __init__(
        self,
        post_job_id: uuid.UUID,
        current_status: PostJobStatus,
    ) -> None:

        super().__init__(
            (
                f"PostJob {post_job_id} cannot publish from status "
                f"{current_status.value} (need scheduled or failed)."
            ),
        )
        self.post_job_id: uuid.UUID = post_job_id
        self.current_status: PostJobStatus = current_status


class PostJobStatusTransitionError(PublishError):
    """Requested status change is not in POST_JOB_STATUS_TRANSITIONS."""

    def __init__(
        self,
        post_job_id: uuid.UUID | None,
        current_status: PostJobStatus,
        target_status: PostJobStatus,
    ) -> None:

        post_job_label: str = str(post_job_id) if post_job_id is not None else "unknown"
        super().__init__(
            (
                f"PostJob {post_job_label} cannot move from "
                f"{current_status.value} to {target_status.value}."
            ),
        )
        self.post_job_id: uuid.UUID | None = post_job_id
        self.current_status: PostJobStatus = current_status
        self.target_status: PostJobStatus = target_status


class PublishAdapterUnknownError(PublishError):
    """`PUBLISH_ADAPTER` is not a known adapter name."""

    def __init__(self, adapter_name: str) -> None:

        super().__init__(
            (
                f"Unknown PUBLISH_ADAPTER {adapter_name!r}. "
                "Use mock (default) or ayrshare."
            ),
        )
        self.adapter_name: str = adapter_name


class PublishAdapterNotConfiguredError(PublishError):
    """Selected vendor adapter is missing required env credentials."""

    def __init__(self, adapter_name: str, missing_setting_name: str) -> None:

        super().__init__(
            (
                f"PUBLISH_ADAPTER={adapter_name} requires {missing_setting_name}. "
                "Leave PUBLISH_ADAPTER=mock for CI and local dry-run."
            ),
        )
        self.adapter_name: str = adapter_name
        self.missing_setting_name: str = missing_setting_name


class AyrshareLivePublishNotWiredError(PublishError):
    """Ayrshare is selected but 1.6 does not send live HTTP."""

    def __init__(self) -> None:

        super().__init__(
            (
                "Ayrshare live HTTP is not wired in Phase 1.6. "
                "Set PUBLISH_ADAPTER=mock, or wait for the follow-up once "
                "AYRSHARE_API_KEY and connected accounts exist."
            ),
        )


class PublishMediaMissingError(PublishError):
    """A slide `asset_ref` does not exist under ARTIFACT_STORAGE_DIR."""

    def __init__(self, asset_reference: str, resolved_path: Path) -> None:

        super().__init__(
            (
                f"Publish media missing for asset_ref {asset_reference!r} "
                f"(resolved {resolved_path})."
            ),
        )
        self.asset_reference: str = asset_reference
        self.resolved_path: Path = resolved_path


class PublishMediaPathEscapeError(PublishError):
    """A slide `asset_ref` resolved outside ARTIFACT_STORAGE_DIR."""

    def __init__(self, asset_reference: str) -> None:

        super().__init__(
            f"Publish media asset_ref escapes artifact store: {asset_reference!r}.",
        )
        self.asset_reference: str = asset_reference
