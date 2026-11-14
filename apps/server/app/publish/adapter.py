"""PublishAdapter contract (1.6b-i)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.models import Account, Artifact, PostJob


@dataclass(frozen=True)
class PublishResult:
    """Platform identifiers returned by a successful adapter publish."""

    platform_post_id: str
    platform_post_url: str | None


@dataclass(frozen=True)
class ConnectionCheck:
    """Result of reading a publish account without posting."""

    adapter: str
    ok: bool
    detail: str


class PublishAdapter(ABC):
    """Vendor-agnostic pipe: media + caption → platform id/URL.

    Implementations must not commit the PostJob. The publish service
    records `platform_post_id` / `platform_post_url` on success.
    """

    @abstractmethod
    def publish(
        self,
        post_job: PostJob,
        artifact: Artifact,
        account: Account,
        media_paths: list[Path],
        media_urls: list[str] | None = None,
    ) -> PublishResult:
        """Publish one PostJob's artifact to the account's platform.

        Args:
            post_job: Row being published (status already `publishing`).
            artifact: Caption, CTA, and slide plan for the job.
            account: Target platform identity (`platform`, `handle`).
            media_paths: Absolute PNG (or other) files from `asset_ref`.
            media_urls: Public URLs in slide order. Paths are not rewritten
                into URLs.

        Returns:
            Fake or vendor platform post id and permalink URL.
        """

    @abstractmethod
    def publish_media(
        self,
        post_id: uuid.UUID,
        account: Account,
        media_paths: list[Path],
        caption: str,
        media_urls: list[str] | None = None,
    ) -> PublishResult:
        """Publish one campaign post's frame files to the account's platform.

        Args:
            post_id: Campaign post being published.
            account: Target platform identity (`platform`, `handle`).
            media_paths: Absolute frame files, in position order.
            caption: Caption sent to the platform. Mock ignores it.
        Returns:
            Fake or vendor platform post id and permalink URL.
        """

    @abstractmethod
    def check_connection(self, account: Account) -> ConnectionCheck:
        """Read whether the account can publish. Do not post.

        Args:
            account: Target account. The profile key is optional.

        Returns:
            Adapter name, whether the check succeeded, and a short sentence.
        """
