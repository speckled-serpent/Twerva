"""Campaign status transitions without Postgres."""

import unittest
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.v1.campaigns import start_campaign_by_id
from app.campaigns.errors import (
    CampaignAlreadyInTargetStatusError,
    CampaignIllegalStatusTransitionError,
)
from app.campaigns.lifecycle import (
    finish_campaign,
    pause_campaign,
    resume_campaign,
    start_campaign,
)
from app.models import Campaign
from app.models.enums import AdvertisementType, CampaignStatus, CampaignType


FIXED_CAMPAIGN_ID: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _campaign_with_status(campaign_status: CampaignStatus) -> Campaign:
    """Build an unbound Campaign at a given status."""

    campaign: Campaign = Campaign(
        name="Spring Launch",
        slug="spring-launch",
        hashtag="#spring-launch",
        campaign_type=CampaignType.SPOTMU,
        advertisement_type=AdvertisementType.CAROUSEL,
        status=campaign_status,
        platforms=["instagram"],
    )
    campaign.id = FIXED_CAMPAIGN_ID

    return campaign


class CampaignLifecycleTests(unittest.TestCase):
    """ready → running ↔ paused; finish from running or paused."""

    def test_start_moves_ready_to_running(self) -> None:
        """Start is the ready → running edge."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.READY)
        started_campaign: Campaign = start_campaign(campaign)

        self.assertEqual(started_campaign.status, CampaignStatus.RUNNING)

    def test_pause_moves_running_to_paused(self) -> None:
        """Pause is the running → paused edge."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.RUNNING)
        paused_campaign: Campaign = pause_campaign(campaign)

        self.assertEqual(paused_campaign.status, CampaignStatus.PAUSED)

    def test_resume_moves_paused_to_running(self) -> None:
        """Resume is the paused → running edge."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.PAUSED)
        resumed_campaign: Campaign = resume_campaign(campaign)

        self.assertEqual(resumed_campaign.status, CampaignStatus.RUNNING)

    def test_finish_moves_running_to_finished(self) -> None:
        """Finish is allowed from running."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.RUNNING)
        finished_campaign: Campaign = finish_campaign(campaign)

        self.assertEqual(finished_campaign.status, CampaignStatus.FINISHED)

    def test_finish_moves_paused_to_finished(self) -> None:
        """Finish is allowed from paused."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.PAUSED)
        finished_campaign: Campaign = finish_campaign(campaign)

        self.assertEqual(finished_campaign.status, CampaignStatus.FINISHED)

    def test_cannot_finish_from_ready(self) -> None:
        """Ready must go through running (or pause after start) before finish."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.READY)

        with self.assertRaises(CampaignIllegalStatusTransitionError) as raised_finish:
            finish_campaign(campaign)

        self.assertEqual(raised_finish.exception.current_status, CampaignStatus.READY)
        self.assertEqual(raised_finish.exception.target_status, CampaignStatus.FINISHED)
        self.assertEqual(campaign.status, CampaignStatus.READY)

    def test_cannot_start_from_paused(self) -> None:
        """Start is not a resume; paused must use resume."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.PAUSED)

        with self.assertRaises(CampaignIllegalStatusTransitionError) as raised_start:
            start_campaign(campaign)

        self.assertEqual(raised_start.exception.current_status, CampaignStatus.PAUSED)
        self.assertEqual(raised_start.exception.target_status, CampaignStatus.RUNNING)

    def test_cannot_pause_from_ready(self) -> None:
        """Pause is only legal from running."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.READY)

        with self.assertRaises(CampaignIllegalStatusTransitionError) as raised_pause:
            pause_campaign(campaign)

        self.assertEqual(raised_pause.exception.current_status, CampaignStatus.READY)
        self.assertEqual(raised_pause.exception.target_status, CampaignStatus.PAUSED)

    def test_cannot_resume_from_ready(self) -> None:
        """Resume is only legal from paused."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.READY)

        with self.assertRaises(CampaignIllegalStatusTransitionError) as raised_resume:
            resume_campaign(campaign)

        self.assertEqual(raised_resume.exception.current_status, CampaignStatus.READY)
        self.assertEqual(raised_resume.exception.target_status, CampaignStatus.RUNNING)

    def test_start_when_already_running_is_a_clear_error(self) -> None:
        """Already-running start does not no-op."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.RUNNING)

        with self.assertRaises(CampaignAlreadyInTargetStatusError) as raised_start:
            start_campaign(campaign)

        self.assertEqual(raised_start.exception.current_status, CampaignStatus.RUNNING)
        self.assertIn("already running", str(raised_start.exception))

    def test_pause_when_already_paused_is_a_clear_error(self) -> None:
        """Already-paused pause does not no-op."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.PAUSED)

        with self.assertRaises(CampaignAlreadyInTargetStatusError) as raised_pause:
            pause_campaign(campaign)

        self.assertEqual(raised_pause.exception.current_status, CampaignStatus.PAUSED)

    def test_resume_when_already_running_is_a_clear_error(self) -> None:
        """Resume on a running campaign is already-in-target, not a start."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.RUNNING)

        with self.assertRaises(CampaignAlreadyInTargetStatusError) as raised_resume:
            resume_campaign(campaign)

        self.assertEqual(raised_resume.exception.current_status, CampaignStatus.RUNNING)

    def test_finish_when_already_finished_is_a_clear_error(self) -> None:
        """Finished is terminal."""

        campaign: Campaign = _campaign_with_status(CampaignStatus.FINISHED)

        with self.assertRaises(CampaignAlreadyInTargetStatusError) as raised_finish:
            finish_campaign(campaign)

        self.assertEqual(raised_finish.exception.current_status, CampaignStatus.FINISHED)

        with self.assertRaises(CampaignIllegalStatusTransitionError):
            start_campaign(campaign)


class CampaignLifecycleHttpTests(unittest.TestCase):
    """Action routes map domain errors to HTTP 400."""

    def test_start_from_paused_returns_http_400(self) -> None:
        """Illegal start is 400, not 409, and does not commit."""

        fake_session: MagicMock = MagicMock()
        paused_campaign: Campaign = _campaign_with_status(CampaignStatus.PAUSED)
        fake_session.get.return_value = paused_campaign

        with self.assertRaises(HTTPException) as raised_http:
            start_campaign_by_id(FIXED_CAMPAIGN_ID, fake_session)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertIn("cannot move from paused to running", str(raised_http.exception.detail))
        fake_session.commit.assert_not_called()

    def test_start_when_already_running_returns_http_400(self) -> None:
        """Already-running start is a clear 400."""

        fake_session: MagicMock = MagicMock()
        running_campaign: Campaign = _campaign_with_status(CampaignStatus.RUNNING)
        fake_session.get.return_value = running_campaign

        with self.assertRaises(HTTPException) as raised_http:
            start_campaign_by_id(FIXED_CAMPAIGN_ID, fake_session)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertIn("already running", str(raised_http.exception.detail))
        fake_session.commit.assert_not_called()

    def test_start_missing_campaign_returns_http_404(self) -> None:
        """Unknown campaign id is 404."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None

        with self.assertRaises(HTTPException) as raised_http:
            start_campaign_by_id(FIXED_CAMPAIGN_ID, fake_session)

        self.assertEqual(raised_http.exception.status_code, 404)
        fake_session.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
