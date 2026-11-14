"""Mock publish adapter — deterministic fake platform ids (1.6b-ii)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.models import Account, Artifact, PostJob
from app.publish.adapter import PublishAdapter, PublishResult


MOCK_PUBLISH_LOGGER_NAME: str = "app.publish.mock"
EXAMPLE_INVALID_HOST: str = "example.invalid"


class MockPublishAdapter(PublishAdapter):
    """Always succeeds. Ids are derived from `post_job.id` + platform."""

    def __init__(self, logger: logging.Logger | None = None) -> None:

        if logger is None:
            resolved_logger: logging.Logger = logging.getLogger(MOCK_PUBLISH_LOGGER_NAME)
        else:
            resolved_logger = logger

        self._logger: logging.Logger = resolved_logger

    def publish(
        self,
        post_job: PostJob,
        artifact: Artifact,
        account: Account,
        media_paths: list[Path],
        media_urls: list[str] | None = None,
    ) -> PublishResult:
        """Return fake platform ids and log how many media files were passed.

        Args:
            post_job: Job being mock-published.
            artifact: Unused beyond the adapter contract (caption stays on the row).
            account: Supplies the platform segment of the fake id/URL.
            media_paths: Resolved slide files; counted in the log line.
            media_urls: Ignored. Mock does not open a client.

        Returns:
            Deterministic `mock-{platform}-{post_job.id}` id and example URL.
        """

        _ = artifact
        _ = media_urls
        media_path_count: int = len(media_paths)
        post_job_identifier: str = str(post_job.id)
        platform_name: str = account.platform.value
        fake_platform_post_id: str = f"mock-{platform_name}-{post_job_identifier}"
        fake_platform_post_url: str = (
            f"https://{EXAMPLE_INVALID_HOST}/{platform_name}/p/{post_job_identifier}"
        )
        self._logger.info(
            "MockPublishAdapter published post_job=%s platform=%s media_path_count=%s",
            post_job_identifier,
            platform_name,
            media_path_count,
        )
        publish_result: PublishResult = PublishResult(
            platform_post_id=fake_platform_post_id,
            platform_post_url=fake_platform_post_url,
        )

        return publish_result

    def publish_media(
        self,
        post_id: uuid.UUID,
        account: Account,
        media_paths: list[Path],
        caption: str,
        media_urls: list[str] | None = None,
    ) -> PublishResult:
        """Return fake platform ids for a campaign post and log the file count.

        Args:
            post_id: Campaign post being mock-published.
            account: Supplies the platform segment of the fake id and URL.
            media_paths: Resolved frame files. Counted in the log line.
            caption: Ignored. The fake id does not depend on the caption.
            media_urls: Ignored. Mock does not open a client.

        Returns:
            Deterministic `mock-{platform}-{post_id}` id and example URL.
        """

        _ = caption
        _ = media_urls
        media_path_count: int = len(media_paths)
        post_identifier: str = str(post_id)
        platform_name: str = account.platform.value
        fake_platform_post_id: str = f"mock-{platform_name}-{post_identifier}"
        fake_platform_post_url: str = (
            f"https://{EXAMPLE_INVALID_HOST}/{platform_name}/p/{post_identifier}"
        )
        self._logger.info(
            "MockPublishAdapter published post=%s platform=%s media_path_count=%s",
            post_identifier,
            platform_name,
            media_path_count,
        )
        publish_result: PublishResult = PublishResult(
            platform_post_id=fake_platform_post_id,
            platform_post_url=fake_platform_post_url,
        )

        return publish_result
