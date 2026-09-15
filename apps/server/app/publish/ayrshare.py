"""Ayrshare stub — selected via env, live HTTP not wired in 1.6."""

from __future__ import annotations

from pathlib import Path

from app.models import Account, Artifact, PostJob
from app.publish.adapter import PublishAdapter, PublishResult
from app.publish.errors import AyrshareLivePublishNotWiredError


AYRSHARE_POST_ENDPOINT: str = "https://api.ayrshare.com/api/post"


class AyrsharePublishAdapter(PublishAdapter):
    """Placeholder for the locked first live vendor.

    1.6 does not call Ayrshare. `publish` always raises
    `AyrshareLivePublishNotWiredError` so CI never needs a real key.
    The constructor still records the API key shape for the follow-up.

    Expected later call (not sent here): `POST {AYRSHARE_POST_ENDPOINT}`
    with Bearer `AYRSHARE_API_KEY`, body `post` / `platforms` /
    `mediaUrls`. Media URLs must be publicly fetchable — local
    `ARTIFACT_STORAGE_DIR` is not.
    """

    def __init__(self, api_key: str) -> None:

        self.api_key: str = api_key

    def publish(
        self,
        post_job: PostJob,
        artifact: Artifact,
        account: Account,
        media_paths: list[Path],
    ) -> PublishResult:
        """Refuse live HTTP until the Ayrshare follow-up lands.

        Args:
            post_job: Unused; kept for the adapter contract.
            artifact: Unused; kept for the adapter contract.
            account: Unused; kept for the adapter contract.
            media_paths: Unused; kept for the adapter contract.

        Returns:
            Never returns in 1.6.

        Raises:
            AyrshareLivePublishNotWiredError: Always.
        """

        _ = post_job
        _ = artifact
        _ = account
        _ = media_paths

        raise AyrshareLivePublishNotWiredError()
