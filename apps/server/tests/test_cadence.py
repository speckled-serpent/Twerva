"""UTC-day cadence cap helper (1.5b) — no Postgres required."""

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from app.models import Account, Artifact, Cluster
from app.models.enums import AccountStatus, ArtifactStatus, Platform
from app.schedule.cadence import (
    cadence_cap_blocks_additional_schedule,
    utc_calendar_day_bounds,
)
from app.schedule.errors import (
    ArtifactNotApprovedError,
    ScheduleBrandMismatchError,
    ScheduleClusterMismatchError,
)
from app.schedule.service import (
    require_artifact_is_approved,
    require_schedule_brand_and_cluster_coherence,
)


FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_BRAND_ID: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
FIXED_CLUSTER_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
OTHER_CLUSTER_ID: uuid.UUID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
FIXED_ACCOUNT_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-4444-444444444444")
FIXED_ARTIFACT_ID: uuid.UUID = uuid.UUID("55555555-5555-5555-5555-555555555555")


class CadenceCapUnitTests(unittest.TestCase):
    """1.5b-iii: under / at / over cap, plus null cap and UTC day bounds."""

    def test_null_cap_never_blocks(self) -> None:
        """`cadence_cap_per_day` null means no limit."""

        self.assertFalse(cadence_cap_blocks_additional_schedule(0, None))
        self.assertFalse(cadence_cap_blocks_additional_schedule(99, None))

    def test_under_cap_allows_schedule(self) -> None:
        """Count strictly below the cap is allowed."""

        self.assertFalse(cadence_cap_blocks_additional_schedule(0, 2))
        self.assertFalse(cadence_cap_blocks_additional_schedule(1, 2))

    def test_at_cap_blocks_schedule(self) -> None:
        """Count equal to the cap is a 409 (no remaining slot)."""

        self.assertTrue(cadence_cap_blocks_additional_schedule(2, 2))
        self.assertTrue(cadence_cap_blocks_additional_schedule(1, 1))
        self.assertTrue(cadence_cap_blocks_additional_schedule(0, 0))

    def test_over_cap_blocks_schedule(self) -> None:
        """Count already above the cap still blocks."""

        self.assertTrue(cadence_cap_blocks_additional_schedule(3, 2))

    def test_utc_calendar_day_bounds_use_utc_not_offset_local(self) -> None:
        """A +04:00 morning can still fall on the previous UTC day."""

        offset_morning: datetime = datetime(
            2026,
            9,
            16,
            1,
            0,
            tzinfo=timezone(timedelta(hours=4)),
        )
        day_start: datetime
        day_end: datetime
        day_start, day_end = utc_calendar_day_bounds(offset_morning)

        self.assertEqual(day_start, datetime(2026, 9, 15, tzinfo=timezone.utc))
        self.assertEqual(day_end, datetime(2026, 9, 16, tzinfo=timezone.utc))

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        """Naive scheduled_for is assumed UTC."""

        naive_scheduled_for: datetime = datetime(2026, 9, 15, 23, 30)
        day_start: datetime
        day_end: datetime
        day_start, day_end = utc_calendar_day_bounds(naive_scheduled_for)

        self.assertEqual(day_start, datetime(2026, 9, 15, tzinfo=timezone.utc))
        self.assertEqual(day_end, datetime(2026, 9, 16, tzinfo=timezone.utc))


class ScheduleCoherenceUnitTests(unittest.TestCase):
    """1.5c-ii: brand always; cluster when the Artifact has one."""

    def test_draft_artifact_cannot_be_scheduled(self) -> None:
        """Only approved artifacts pass the schedule gate."""

        artifact: Artifact = Artifact(
            brand_id=FIXED_BRAND_ID,
            status=ArtifactStatus.DRAFT,
            format="carousel",
        )
        artifact.id = FIXED_ARTIFACT_ID

        with self.assertRaises(ArtifactNotApprovedError):
            require_artifact_is_approved(artifact)

    def test_brand_mismatch_is_rejected(self) -> None:
        """Account cluster brand must match the Artifact brand."""

        artifact: Artifact
        account: Account
        account_cluster: Cluster
        artifact, account, account_cluster = _approved_artifact_and_account(
            artifact_cluster_id=None,
            account_cluster_id=OTHER_CLUSTER_ID,
            account_brand_id=OTHER_BRAND_ID,
        )

        with self.assertRaises(ScheduleBrandMismatchError):
            require_schedule_brand_and_cluster_coherence(
                artifact,
                account,
                account_cluster,
            )

    def test_cluster_mismatch_when_artifact_cluster_is_set(self) -> None:
        """When Artifact.cluster_id is set, Account must match it."""

        artifact: Artifact
        account: Account
        account_cluster: Cluster
        artifact, account, account_cluster = _approved_artifact_and_account(
            artifact_cluster_id=FIXED_CLUSTER_ID,
            account_cluster_id=OTHER_CLUSTER_ID,
            account_brand_id=FIXED_BRAND_ID,
        )

        with self.assertRaises(ScheduleClusterMismatchError):
            require_schedule_brand_and_cluster_coherence(
                artifact,
                account,
                account_cluster,
            )

    def test_same_brand_any_account_when_artifact_cluster_is_null(self) -> None:
        """Null Artifact cluster allows any Account under the same brand."""

        artifact: Artifact
        account: Account
        account_cluster: Cluster
        artifact, account, account_cluster = _approved_artifact_and_account(
            artifact_cluster_id=None,
            account_cluster_id=OTHER_CLUSTER_ID,
            account_brand_id=FIXED_BRAND_ID,
        )
        require_schedule_brand_and_cluster_coherence(
            artifact,
            account,
            account_cluster,
        )


def _approved_artifact_and_account(
    artifact_cluster_id: uuid.UUID | None,
    account_cluster_id: uuid.UUID,
    account_brand_id: uuid.UUID,
) -> tuple[Artifact, Account, Cluster]:
    """Build unbound Artifact / Account / Cluster for coherence checks."""

    artifact: Artifact = Artifact(
        brand_id=FIXED_BRAND_ID,
        cluster_id=artifact_cluster_id,
        status=ArtifactStatus.APPROVED,
        format="carousel",
    )
    artifact.id = FIXED_ARTIFACT_ID
    account: Account = Account(
        cluster_id=account_cluster_id,
        platform=Platform.INSTAGRAM,
        handle="spotmu_example",
        status=AccountStatus.ACTIVE,
    )
    account.id = FIXED_ACCOUNT_ID
    account_cluster: Cluster = Cluster(
        brand_id=account_brand_id,
        slug="lane",
        name="Lane",
    )
    account_cluster.id = account_cluster_id

    return artifact, account, account_cluster


if __name__ == "__main__":
    unittest.main()
