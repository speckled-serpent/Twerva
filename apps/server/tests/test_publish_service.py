"""Publish service status transitions with the mock adapter (no Postgres)."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import Account, Artifact, PostJob
from app.models.enums import AccountStatus, ArtifactStatus, Platform, PostJobStatus
from app.publish.adapter import PublishAdapter, PublishResult
from app.publish.errors import PostJobNotPublishableError
from app.publish.mock import MockPublishAdapter
from app.publish.service import publish_post_job
from app.storage.artifacts import write_artifact_slide_png_bytes


FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FIXED_CLUSTER_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FIXED_ACCOUNT_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-4444-444444444444")
FIXED_ARTIFACT_ID: uuid.UUID = uuid.UUID("55555555-5555-5555-5555-555555555555")
FIXED_POST_JOB_ID: uuid.UUID = uuid.UUID("66666666-6666-6666-6666-666666666666")
FIXED_PUBLISHED_AT: datetime = datetime(2026, 9, 15, 16, 0, tzinfo=timezone.utc)
MINIMAL_PNG_BYTES: bytes = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FailingPublishAdapter(PublishAdapter):
    """Test double that always raises."""

    def publish(
        self,
        post_job: PostJob,
        artifact: Artifact,
        account: Account,
        media_paths: list[Path],
    ) -> PublishResult:

        _ = post_job
        _ = artifact
        _ = account
        _ = media_paths

        raise RuntimeError("forced adapter failure")


def _post_job(status: PostJobStatus, last_error: str | None = None) -> PostJob:
    """Build an unbound PostJob with a stable id."""

    post_job: PostJob = PostJob(
        artifact_id=FIXED_ARTIFACT_ID,
        account_id=FIXED_ACCOUNT_ID,
        status=status,
        last_error=last_error,
    )
    post_job.id = FIXED_POST_JOB_ID

    return post_job


def _account() -> Account:
    """Build an unbound TikTok Account (distinct fake-id prefix from IG tests)."""

    account: Account = Account(
        cluster_id=FIXED_CLUSTER_ID,
        platform=Platform.TIKTOK,
        handle="mock_tiktok",
        status=AccountStatus.ACTIVE,
    )
    account.id = FIXED_ACCOUNT_ID

    return account


def _artifact_with_cover(storage_directory: Path) -> Artifact:
    """Approved Artifact whose cover PNG exists under the tmp store."""

    asset_reference: str = write_artifact_slide_png_bytes(
        FIXED_ARTIFACT_ID,
        0,
        "cover",
        MINIMAL_PNG_BYTES,
        storage_directory,
    )
    artifact: Artifact = Artifact(
        brand_id=FIXED_BRAND_ID,
        status=ArtifactStatus.APPROVED,
        format="carousel",
        caption="publish me",
        slides=[{"role": "cover", "text": "Cover", "asset_ref": asset_reference}],
    )
    artifact.id = FIXED_ARTIFACT_ID

    return artifact


class PublishServiceTests(unittest.TestCase):
    """1.6c: scheduled → published; failed retry; adapter error → failed."""

    def test_mock_publish_sets_published_fields(self) -> None:
        """Happy path records fake ids, URL, and published_at."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            published_post_job: PostJob = publish_post_job(
                _post_job(PostJobStatus.SCHEDULED),
                _artifact_with_cover(storage_directory),
                _account(),
                MockPublishAdapter(),
                storage_directory,
                published_at=FIXED_PUBLISHED_AT,
            )

            self.assertEqual(published_post_job.status, PostJobStatus.PUBLISHED)
            self.assertEqual(
                published_post_job.platform_post_id,
                f"mock-tiktok-{FIXED_POST_JOB_ID}",
            )
            self.assertEqual(
                published_post_job.platform_post_url,
                f"https://example.invalid/tiktok/p/{FIXED_POST_JOB_ID}",
            )
            self.assertEqual(published_post_job.published_at, FIXED_PUBLISHED_AT)
            self.assertIsNone(published_post_job.last_error)

    def test_adapter_failure_marks_failed_and_sets_last_error(self) -> None:
        """Adapter exceptions become failed + last_error, not a raised HTTP."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            failed_post_job: PostJob = publish_post_job(
                _post_job(PostJobStatus.SCHEDULED),
                _artifact_with_cover(storage_directory),
                _account(),
                FailingPublishAdapter(),
                storage_directory,
            )

            self.assertEqual(failed_post_job.status, PostJobStatus.FAILED)
            self.assertEqual(failed_post_job.last_error, "forced adapter failure")
            self.assertIsNone(failed_post_job.platform_post_id)
            self.assertIsNone(failed_post_job.published_at)

    def test_failed_job_can_be_retried_to_published(self) -> None:
        """Manual re-run: failed → publishing → published; last_error cleared."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            retried_post_job: PostJob = publish_post_job(
                _post_job(PostJobStatus.FAILED, last_error="previous boom"),
                _artifact_with_cover(storage_directory),
                _account(),
                MockPublishAdapter(),
                storage_directory,
                published_at=FIXED_PUBLISHED_AT,
            )

            self.assertEqual(retried_post_job.status, PostJobStatus.PUBLISHED)
            self.assertIsNone(retried_post_job.last_error)
            self.assertEqual(retried_post_job.published_at, FIXED_PUBLISHED_AT)

    def test_already_published_job_is_not_publishable(self) -> None:
        """Published jobs must not run again (HTTP 409 at the route)."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)

            with self.assertRaises(PostJobNotPublishableError) as raised_published:
                publish_post_job(
                    _post_job(PostJobStatus.PUBLISHED),
                    _artifact_with_cover(storage_directory),
                    _account(),
                    MockPublishAdapter(),
                    storage_directory,
                )

            self.assertEqual(
                raised_published.exception.current_status,
                PostJobStatus.PUBLISHED,
            )

    def test_missing_media_marks_failed(self) -> None:
        """A broken asset_ref fails the job instead of raising out of the service."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            artifact: Artifact = Artifact(
                brand_id=FIXED_BRAND_ID,
                status=ArtifactStatus.APPROVED,
                format="carousel",
                slides=[
                    {
                        "role": "cover",
                        "text": "gone",
                        "asset_ref": "missing/0_cover.png",
                    },
                ],
            )
            artifact.id = FIXED_ARTIFACT_ID
            failed_post_job: PostJob = publish_post_job(
                _post_job(PostJobStatus.SCHEDULED),
                artifact,
                _account(),
                MockPublishAdapter(),
                storage_directory,
            )

            self.assertEqual(failed_post_job.status, PostJobStatus.FAILED)
            self.assertIsNotNone(failed_post_job.last_error)
            self.assertIn("missing/0_cover.png", str(failed_post_job.last_error))


if __name__ == "__main__":
    unittest.main()
