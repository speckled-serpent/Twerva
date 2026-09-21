"""Campaign create validation that does not need Postgres."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.v1.campaigns import (
    CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL,
    CAMPAIGN_INTERESTS_REQUIRED_DETAIL,
    CAMPAIGN_NAME_REQUIRED_DETAIL,
    CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
    create_campaign,
)
from app.api.v1.schemas import (
    CampaignCreateRequest,
    CampaignInterestWrite,
    CampaignReadResponse,
)
from app.models.enums import (
    AdvertisementType,
    CampaignStatus,
    CampaignType,
    Platform,
)


class CampaignCreateValidationTests(unittest.TestCase):
    """Spotmu create rejects incomplete bodies before any write."""

    def test_other_campaign_type_is_rejected(self) -> None:
        """POST body with `other` returns HTTP 400 and does not persist."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = CampaignCreateRequest(
            name="Later",
            campaign_type=CampaignType.OTHER,
            advertisement_type=AdvertisementType.CAROUSEL,
        )

        with self.assertRaises(HTTPException) as raised_http:
            create_campaign(
                campaign_create_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertIn("not implemented", str(raised_http.exception.detail).lower())
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()

    def test_blank_campaign_name_is_rejected(self) -> None:
        """Whitespace-only name returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            name="   ",
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_NAME_REQUIRED_DETAIL,
        )

    def test_empty_platforms_are_rejected(self) -> None:
        """Spotmu create with no platforms returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            platforms=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
        )

    def test_empty_account_ids_are_rejected(self) -> None:
        """Spotmu create with no accounts returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            account_ids=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL,
        )

    def test_spotmu_test_empty_account_ids_succeeds(self) -> None:
        """Spotmu-test create with no accounts persists a ready campaign."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            campaign_type=CampaignType.SPOTMU_TEST,
            account_ids=[],
        )
        reloaded_campaign: MagicMock = _campaign_reload_double(
            CampaignType.SPOTMU_TEST,
            campaign_create_request,
        )

        with patch(
            "app.api.v1.campaigns._load_taken_campaign_slugs",
            return_value=set(),
        ), patch(
            "app.api.v1.campaigns.commit_database_session_or_raise_conflict",
        ), patch(
            "app.api.v1.campaigns._load_campaign_with_joins",
            return_value=reloaded_campaign,
        ):
            campaign_read_response: CampaignReadResponse = create_campaign(
                campaign_create_request,
                fake_session,
                None,
            )

        self.assertEqual(campaign_read_response.campaign_type, CampaignType.SPOTMU_TEST)
        self.assertEqual(campaign_read_response.status, CampaignStatus.READY)
        self.assertEqual(campaign_read_response.account_count, 0)
        self.assertEqual(campaign_read_response.interest_count, 1)
        fake_session.add.assert_called()
        fake_session.flush.assert_called_once()

    def test_spotmu_test_blank_name_is_rejected(self) -> None:
        """Spotmu-test still requires a non-empty name."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            name="   ",
            campaign_type=CampaignType.SPOTMU_TEST,
            account_ids=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_NAME_REQUIRED_DETAIL,
        )

    def test_spotmu_test_empty_platforms_are_rejected(self) -> None:
        """Spotmu-test create with no platforms returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            campaign_type=CampaignType.SPOTMU_TEST,
            platforms=[],
            account_ids=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
        )

    def test_spotmu_test_empty_interests_are_rejected(self) -> None:
        """Spotmu-test create with no interests returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            campaign_type=CampaignType.SPOTMU_TEST,
            account_ids=[],
            interests=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_INTERESTS_REQUIRED_DETAIL,
        )

    def test_empty_interests_are_rejected(self) -> None:
        """Spotmu create with no interests returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            interests=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_INTERESTS_REQUIRED_DETAIL,
        )

    def test_blank_interest_slugs_are_rejected_after_strip(self) -> None:
        """Interests that become empty after strip/dedupe return HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            interests=[
                CampaignInterestWrite(slug="   ", title="Blank"),
                CampaignInterestWrite(slug="", title="Empty"),
            ],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_INTERESTS_REQUIRED_DETAIL,
        )

    def _assert_create_rejected(
        self,
        campaign_create_request: CampaignCreateRequest,
        fake_session: MagicMock,
        expected_detail: str,
    ) -> None:
        """Assert create raises 400 with the given detail and does not persist."""

        with self.assertRaises(HTTPException) as raised_http:
            create_campaign(
                campaign_create_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, expected_detail)
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()


def _spotmu_create_request(
    name: str = "Spring Launch",
    campaign_type: CampaignType = CampaignType.SPOTMU,
    platforms: list[Platform] | None = None,
    account_ids: list[uuid.UUID] | None = None,
    interests: list[CampaignInterestWrite] | None = None,
) -> CampaignCreateRequest:
    """Build a Spotmu-family create body with complete defaults unless overridden."""

    selected_platforms: list[Platform] = (
        [Platform.INSTAGRAM] if platforms is None else platforms
    )
    selected_account_ids: list[uuid.UUID] = (
        [uuid.uuid4()] if account_ids is None else account_ids
    )
    selected_interests: list[CampaignInterestWrite] = (
        [CampaignInterestWrite(slug="ai-agents", title="AI Agents")]
        if interests is None
        else interests
    )
    campaign_create_request: CampaignCreateRequest = CampaignCreateRequest(
        name=name,
        campaign_type=campaign_type,
        advertisement_type=AdvertisementType.CAROUSEL,
        platforms=selected_platforms,
        account_ids=selected_account_ids,
        interests=selected_interests,
    )

    return campaign_create_request


def _campaign_reload_double(
    campaign_type: CampaignType,
    campaign_create_request: CampaignCreateRequest,
) -> MagicMock:
    """Build a join-loaded campaign stand-in for serialize after a mocked write."""

    interest_links: list[MagicMock] = []

    for interest_write in campaign_create_request.interests:
        interest_link: MagicMock = MagicMock()
        interest_link.spotmu_slug = interest_write.slug
        interest_link.title = interest_write.title
        interest_link.spotmu_interest_id = interest_write.spotmu_interest_id
        interest_links.append(interest_link)

    now_timestamp: datetime = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    reloaded_campaign: MagicMock = MagicMock()
    reloaded_campaign.id = uuid.uuid4()
    reloaded_campaign.name = campaign_create_request.name.strip()
    reloaded_campaign.slug = "spring-launch"
    reloaded_campaign.hashtag = "#spring-launch"
    reloaded_campaign.campaign_type = campaign_type
    reloaded_campaign.advertisement_type = AdvertisementType.CAROUSEL
    reloaded_campaign.status = CampaignStatus.READY
    reloaded_campaign.platforms = [
        platform.value for platform in campaign_create_request.platforms
    ]
    reloaded_campaign.account_links = []
    reloaded_campaign.interest_links = interest_links
    reloaded_campaign.created_at = now_timestamp
    reloaded_campaign.updated_at = now_timestamp
    reloaded_campaign.created_by = None

    return reloaded_campaign


if __name__ == "__main__":
    unittest.main()
