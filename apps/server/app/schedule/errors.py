"""Domain errors for cadence caps and post-job scheduling."""

from __future__ import annotations

import uuid
from datetime import date

from app.models.enums import ArtifactStatus


class ScheduleError(Exception):
    """Base error for schedule and cadence checks."""


class ArtifactNotApprovedError(ScheduleError):
    """Only `approved` artifacts may be scheduled."""

    def __init__(
        self,
        artifact_id: uuid.UUID,
        current_status: ArtifactStatus,
    ) -> None:

        super().__init__(
            (
                f"Artifact {artifact_id} must be approved to schedule "
                f"(status is {current_status.value})."
            ),
        )
        self.artifact_id: uuid.UUID = artifact_id
        self.current_status: ArtifactStatus = current_status


class ScheduleBrandMismatchError(ScheduleError):
    """Account cluster brand does not match the Artifact brand."""

    def __init__(
        self,
        artifact_id: uuid.UUID,
        account_id: uuid.UUID,
        artifact_brand_id: uuid.UUID,
        account_brand_id: uuid.UUID,
    ) -> None:

        super().__init__(
            (
                f"Account {account_id} brand {account_brand_id} does not match "
                f"Artifact {artifact_id} brand {artifact_brand_id}."
            ),
        )
        self.artifact_id: uuid.UUID = artifact_id
        self.account_id: uuid.UUID = account_id
        self.artifact_brand_id: uuid.UUID = artifact_brand_id
        self.account_brand_id: uuid.UUID = account_brand_id


class ScheduleClusterMismatchError(ScheduleError):
    """Account cluster does not match the Artifact cluster when one is set."""

    def __init__(
        self,
        artifact_id: uuid.UUID,
        account_id: uuid.UUID,
        artifact_cluster_id: uuid.UUID,
        account_cluster_id: uuid.UUID,
    ) -> None:

        super().__init__(
            (
                f"Account {account_id} cluster {account_cluster_id} does not match "
                f"Artifact {artifact_id} cluster {artifact_cluster_id}."
            ),
        )
        self.artifact_id: uuid.UUID = artifact_id
        self.account_id: uuid.UUID = account_id
        self.artifact_cluster_id: uuid.UUID = artifact_cluster_id
        self.account_cluster_id: uuid.UUID = account_cluster_id


class CadenceCapExceededError(ScheduleError):
    """Non-failed post_jobs on the UTC day already meet the account cap."""

    def __init__(
        self,
        account_id: uuid.UUID,
        utc_day: date,
        existing_non_failed_count: int,
        cadence_cap_per_day: int,
    ) -> None:

        super().__init__(
            (
                f"Cadence cap exceeded for account {account_id} on UTC day "
                f"{utc_day.isoformat()}: {existing_non_failed_count} existing "
                f"non-failed post_jobs, cap {cadence_cap_per_day}."
            ),
        )
        self.account_id: uuid.UUID = account_id
        self.utc_day: date = utc_day
        self.existing_non_failed_count: int = existing_non_failed_count
        self.cadence_cap_per_day: int = cadence_cap_per_day
