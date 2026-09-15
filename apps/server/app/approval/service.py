"""Apply ArtifactStatus transitions and caption edits (1.5a).

Reject is terminal for MVP (`ARTIFACT_STATUS_TRANSITIONS`). A rejected
row cannot be re-approved; generate a new Artifact instead.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.approval.errors import (
    ArtifactApprovalTransitionError,
    ArtifactCaptionPatchNotAllowedError,
)
from app.models import Artifact
from app.models.enums import ARTIFACT_STATUS_TRANSITIONS, ArtifactStatus


PATCHABLE_ARTIFACT_STATUSES: frozenset[ArtifactStatus] = frozenset(
    {ArtifactStatus.DRAFT, ArtifactStatus.APPROVED},
)


def approve_artifact(
    artifact: Artifact,
    caption: str | None = None,
    approved_at: datetime | None = None,
) -> Artifact:
    """Move a draft Artifact to `approved` and stamp `approved_at`.

    Args:
        artifact: Row to mutate (not committed).
        caption: When not None, replaces the stored caption at approve.
        approved_at: Override for tests; default is UTC now.

    Returns:
        The same Artifact instance after the transition.

    Raises:
        ArtifactApprovalTransitionError: Status is not `draft`.
    """

    _require_artifact_status_transition(artifact, ArtifactStatus.APPROVED)

    if caption is not None:
        artifact.caption = caption

    resolved_approved_at: datetime

    if approved_at is None:
        resolved_approved_at = datetime.now(timezone.utc)
    else:
        resolved_approved_at = approved_at

    artifact.status = ArtifactStatus.APPROVED
    artifact.approved_at = resolved_approved_at

    return artifact


def reject_artifact(artifact: Artifact) -> Artifact:
    """Move a draft or approved Artifact to terminal `rejected`.

    Args:
        artifact: Row to mutate (not committed).

    Returns:
        The same Artifact instance after the transition.

    Raises:
        ArtifactApprovalTransitionError: Status is already `rejected`.
    """

    _require_artifact_status_transition(artifact, ArtifactStatus.REJECTED)
    artifact.status = ArtifactStatus.REJECTED

    return artifact


def patch_artifact_caption_and_cta_url(
    artifact: Artifact,
    caption: str | None = None,
    cta_url: str | None = None,
    caption_is_set: bool = False,
    cta_url_is_set: bool = False,
) -> Artifact:
    """Edit caption and/or cta_url while the Artifact is draft or approved.

    Args:
        artifact: Row to mutate (not committed).
        caption: New caption when `caption_is_set` is True.
        cta_url: New CTA URL when `cta_url_is_set` is True.
        caption_is_set: Whether the caller supplied `caption` (including null).
        cta_url_is_set: Whether the caller supplied `cta_url` (including null).

    Returns:
        The same Artifact instance after the patch.

    Raises:
        ArtifactCaptionPatchNotAllowedError: Status is `rejected`.
    """

    if artifact.status not in PATCHABLE_ARTIFACT_STATUSES:
        raise ArtifactCaptionPatchNotAllowedError(artifact.id, artifact.status)

    if caption_is_set:
        artifact.caption = caption

    if cta_url_is_set:
        artifact.cta_url = cta_url

    return artifact


def _require_artifact_status_transition(
    artifact: Artifact,
    target_status: ArtifactStatus,
) -> None:
    """Raise when `ARTIFACT_STATUS_TRANSITIONS` does not allow the move."""

    allowed_targets: frozenset[ArtifactStatus] = ARTIFACT_STATUS_TRANSITIONS.get(
        artifact.status,
        frozenset(),
    )

    if target_status not in allowed_targets:
        raise ArtifactApprovalTransitionError(
            artifact.id,
            artifact.status,
            target_status,
        )
