"""Artifact status transitions for the 1.5a review queue (no Postgres)."""

import unittest
import uuid
from datetime import datetime, timezone

from app.approval.errors import (
    ArtifactApprovalTransitionError,
    ArtifactCaptionPatchNotAllowedError,
)
from app.approval.service import (
    approve_artifact,
    patch_artifact_caption_and_cta_url,
    reject_artifact,
)
from app.models import Artifact
from app.models.enums import ArtifactStatus


FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FIXED_ARTIFACT_ID: uuid.UUID = uuid.UUID("55555555-5555-5555-5555-555555555555")
FIXED_APPROVED_AT: datetime = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)


def _draft_artifact(caption: str | None = "original caption") -> Artifact:
    """Build an unbound draft Artifact for transition tests."""

    artifact: Artifact = Artifact(
        brand_id=FIXED_BRAND_ID,
        status=ArtifactStatus.DRAFT,
        format="carousel",
        caption=caption,
        cta_url="https://spotmu.com/interest/example",
    )
    artifact.id = FIXED_ARTIFACT_ID

    return artifact


class ArtifactTransitionTests(unittest.TestCase):
    """1.5a-v: draft → approved/rejected; rejected cannot re-approve."""

    def test_approve_draft_sets_status_and_approved_at(self) -> None:
        """Draft becomes approved with a stamped approved_at."""

        artifact: Artifact = _draft_artifact()
        approved_artifact: Artifact = approve_artifact(
            artifact,
            approved_at=FIXED_APPROVED_AT,
        )

        self.assertEqual(approved_artifact.status, ArtifactStatus.APPROVED)
        self.assertEqual(approved_artifact.approved_at, FIXED_APPROVED_AT)
        self.assertEqual(approved_artifact.caption, "original caption")

    def test_approve_replaces_caption_when_provided(self) -> None:
        """Optional caption at approve overwrites the stored caption."""

        artifact: Artifact = _draft_artifact()
        approved_artifact: Artifact = approve_artifact(
            artifact,
            caption="edited at approve",
            approved_at=FIXED_APPROVED_AT,
        )

        self.assertEqual(approved_artifact.caption, "edited at approve")
        self.assertEqual(approved_artifact.status, ArtifactStatus.APPROVED)

    def test_reject_draft_is_terminal(self) -> None:
        """Draft → rejected; a second approve is not allowed."""

        artifact: Artifact = _draft_artifact()
        rejected_artifact: Artifact = reject_artifact(artifact)

        self.assertEqual(rejected_artifact.status, ArtifactStatus.REJECTED)

        with self.assertRaises(ArtifactApprovalTransitionError) as raised_approve:
            approve_artifact(rejected_artifact, approved_at=FIXED_APPROVED_AT)

        self.assertEqual(
            raised_approve.exception.current_status,
            ArtifactStatus.REJECTED,
        )
        self.assertEqual(
            raised_approve.exception.target_status,
            ArtifactStatus.APPROVED,
        )

    def test_reject_approved_is_allowed(self) -> None:
        """Approved may still be rejected; reject stays terminal."""

        artifact: Artifact = _draft_artifact()
        approve_artifact(artifact, approved_at=FIXED_APPROVED_AT)
        rejected_artifact: Artifact = reject_artifact(artifact)

        self.assertEqual(rejected_artifact.status, ArtifactStatus.REJECTED)

        with self.assertRaises(ArtifactApprovalTransitionError):
            reject_artifact(rejected_artifact)

    def test_cannot_approve_already_approved(self) -> None:
        """There is no approved → approved edge."""

        artifact: Artifact = _draft_artifact()
        approve_artifact(artifact, approved_at=FIXED_APPROVED_AT)

        with self.assertRaises(ArtifactApprovalTransitionError) as raised_approve:
            approve_artifact(artifact, approved_at=FIXED_APPROVED_AT)

        self.assertEqual(
            raised_approve.exception.current_status,
            ArtifactStatus.APPROVED,
        )

    def test_patch_caption_and_cta_url_while_draft_or_approved(self) -> None:
        """PATCH is allowed on draft and approved, not rejected."""

        artifact: Artifact = _draft_artifact()
        patch_artifact_caption_and_cta_url(
            artifact,
            caption="patched caption",
            caption_is_set=True,
        )

        self.assertEqual(artifact.caption, "patched caption")
        self.assertEqual(artifact.cta_url, "https://spotmu.com/interest/example")

        approve_artifact(artifact, approved_at=FIXED_APPROVED_AT)
        patch_artifact_caption_and_cta_url(
            artifact,
            cta_url="https://spotmu.com/interest/patched",
            cta_url_is_set=True,
        )

        self.assertEqual(artifact.cta_url, "https://spotmu.com/interest/patched")

        reject_artifact(artifact)

        with self.assertRaises(ArtifactCaptionPatchNotAllowedError):
            patch_artifact_caption_and_cta_url(
                artifact,
                caption="too late",
                caption_is_set=True,
            )


if __name__ == "__main__":
    unittest.main()
