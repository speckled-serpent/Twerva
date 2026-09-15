"""Mock PublishAdapter, factory, and Ayrshare stub (1.6b)."""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path

from app.models import Account, Artifact, PostJob
from app.models.enums import AccountStatus, ArtifactStatus, Platform, PostJobStatus
from app.publish.adapter import PublishResult
from app.publish.ayrshare import AyrsharePublishAdapter
from app.publish.errors import (
    AyrshareLivePublishNotWiredError,
    PublishAdapterNotConfiguredError,
    PublishAdapterUnknownError,
)
from app.publish.factory import get_publish_adapter
from app.publish.mock import MOCK_PUBLISH_LOGGER_NAME, MockPublishAdapter
from app.settings import Settings


FIXED_ACCOUNT_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-4444-444444444444")
FIXED_ARTIFACT_ID: uuid.UUID = uuid.UUID("55555555-5555-5555-5555-555555555555")
FIXED_POST_JOB_ID: uuid.UUID = uuid.UUID("66666666-6666-6666-6666-666666666666")
FIXED_CLUSTER_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _scheduled_post_job() -> PostJob:
    """Build an unbound scheduled PostJob with a stable id."""

    post_job: PostJob = PostJob(
        artifact_id=FIXED_ARTIFACT_ID,
        account_id=FIXED_ACCOUNT_ID,
        status=PostJobStatus.SCHEDULED,
    )
    post_job.id = FIXED_POST_JOB_ID

    return post_job


def _draft_artifact() -> Artifact:
    """Build an unbound draft Artifact with a stable id."""

    artifact: Artifact = Artifact(
        brand_id=FIXED_BRAND_ID,
        status=ArtifactStatus.DRAFT,
        format="carousel",
        caption="mock caption",
    )
    artifact.id = FIXED_ARTIFACT_ID

    return artifact


def _instagram_account() -> Account:
    """Build an unbound Instagram Account with a stable id."""

    account: Account = Account(
        cluster_id=FIXED_CLUSTER_ID,
        platform=Platform.INSTAGRAM,
        handle="mock_handle",
        status=AccountStatus.ACTIVE,
    )
    account.id = FIXED_ACCOUNT_ID

    return account


class MockPublishAdapterTests(unittest.TestCase):
    """1.6b-ii: deterministic fake ids; media path count is logged."""

    def test_publish_returns_deterministic_fake_ids(self) -> None:
        """Id and URL are derived from platform + post_job.id."""

        mock_publish_adapter: MockPublishAdapter = MockPublishAdapter()
        publish_result: PublishResult = mock_publish_adapter.publish(
            _scheduled_post_job(),
            _draft_artifact(),
            _instagram_account(),
            [Path("/tmp/unused.png")],
        )

        self.assertEqual(
            publish_result.platform_post_id,
            f"mock-instagram-{FIXED_POST_JOB_ID}",
        )
        self.assertEqual(
            publish_result.platform_post_url,
            f"https://example.invalid/instagram/p/{FIXED_POST_JOB_ID}",
        )

    def test_publish_logs_media_path_count(self) -> None:
        """INFO log includes the number of media files passed in."""

        mock_publish_adapter: MockPublishAdapter = MockPublishAdapter()
        media_paths: list[Path] = [Path("/tmp/a.png"), Path("/tmp/b.png")]

        with self.assertLogs(MOCK_PUBLISH_LOGGER_NAME, level="INFO") as log_context:
            mock_publish_adapter.publish(
                _scheduled_post_job(),
                _draft_artifact(),
                _instagram_account(),
                media_paths,
            )

        joined_log_output: str = "\n".join(log_context.output)

        self.assertIn("media_path_count=2", joined_log_output)
        self.assertIn(str(FIXED_POST_JOB_ID), joined_log_output)


class PublishAdapterFactoryTests(unittest.TestCase):
    """1.6b-iii: mock works without keys; ayrshare is opt-in."""

    def test_factory_defaults_to_mock_adapter(self) -> None:
        """PUBLISH_ADAPTER=mock returns MockPublishAdapter."""

        mock_settings: Settings = Settings(
            database_url="postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
            publish_adapter="mock",
        )
        publish_adapter = get_publish_adapter(mock_settings)

        self.assertIsInstance(publish_adapter, MockPublishAdapter)

    def test_factory_ayrshare_without_key_raises(self) -> None:
        """Ayrshare without AYRSHARE_API_KEY is not configured."""

        ayrshare_settings: Settings = Settings(
            database_url="postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
            publish_adapter="ayrshare",
            ayrshare_api_key="",
        )

        with self.assertRaises(PublishAdapterNotConfiguredError) as raised_missing:
            get_publish_adapter(ayrshare_settings)

        self.assertEqual(raised_missing.exception.adapter_name, "ayrshare")
        self.assertEqual(raised_missing.exception.missing_setting_name, "AYRSHARE_API_KEY")

    def test_factory_ayrshare_with_key_returns_stub(self) -> None:
        """Ayrshare with a key constructs the stub (live HTTP still not sent)."""

        ayrshare_settings: Settings = Settings(
            database_url="postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
            publish_adapter="ayrshare",
            ayrshare_api_key="test-key",
        )
        publish_adapter = get_publish_adapter(ayrshare_settings)

        self.assertIsInstance(publish_adapter, AyrsharePublishAdapter)

    def test_ayrshare_stub_publish_is_not_wired(self) -> None:
        """Calling the stub never hits the network."""

        ayrshare_publish_adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            "test-key",
        )

        with self.assertRaises(AyrshareLivePublishNotWiredError):
            ayrshare_publish_adapter.publish(
                _scheduled_post_job(),
                _draft_artifact(),
                _instagram_account(),
                [],
            )

    def test_factory_unknown_adapter_raises(self) -> None:
        """Unknown PUBLISH_ADAPTER names fail closed."""

        unknown_settings: Settings = Settings(
            database_url="postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
            publish_adapter="native",
        )

        with self.assertRaises(PublishAdapterUnknownError) as raised_unknown:
            get_publish_adapter(unknown_settings)

        self.assertEqual(raised_unknown.exception.adapter_name, "native")


if __name__ == "__main__":
    unittest.main()
