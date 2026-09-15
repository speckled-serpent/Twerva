"""Domain errors for artifact approve / reject / caption patch."""

from __future__ import annotations

import uuid

from app.models.enums import ArtifactStatus


class ApprovalError(Exception):
    """Base error for review-queue transitions."""


class ArtifactApprovalTransitionError(ApprovalError):
    """Requested status change is not in ARTIFACT_STATUS_TRANSITIONS."""

    def __init__(
        self,
        artifact_id: uuid.UUID | None,
        current_status: ArtifactStatus,
        target_status: ArtifactStatus,
    ) -> None:

        artifact_label: str = str(artifact_id) if artifact_id is not None else "unknown"
        super().__init__(
            (
                f"Artifact {artifact_label} cannot move from "
                f"{current_status.value} to {target_status.value}."
            ),
        )
        self.artifact_id: uuid.UUID | None = artifact_id
        self.current_status: ArtifactStatus = current_status
        self.target_status: ArtifactStatus = target_status


class ArtifactCaptionPatchNotAllowedError(ApprovalError):
    """Caption/cta_url may be patched only while draft or approved."""

    def __init__(
        self,
        artifact_id: uuid.UUID | None,
        current_status: ArtifactStatus,
    ) -> None:

        artifact_label: str = str(artifact_id) if artifact_id is not None else "unknown"
        super().__init__(
            (
                f"Artifact {artifact_label} caption cannot be patched while "
                f"status is {current_status.value}."
            ),
        )
        self.artifact_id: uuid.UUID | None = artifact_id
        self.current_status: ArtifactStatus = current_status
