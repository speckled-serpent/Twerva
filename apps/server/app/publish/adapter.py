"""PublishAdapter contract (1.6b-i)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.models import Account, Artifact, PostJob


@dataclass(frozen=True)
class PublishResult:
    """Platform identifiers returned by a successful adapter publish."""

    platform_post_id: str
    platform_post_url: str


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
    ) -> PublishResult:
        """Publish one PostJob's artifact to the account's platform.

        Args:
            post_job: Row being published (status already `publishing`).
            artifact: Caption, CTA, and slide plan for the job.
            account: Target platform identity (`platform`, `handle`).
            media_paths: Absolute PNG (or other) files from `asset_ref`.

        Returns:
            Fake or vendor platform post id and permalink URL.
        """
