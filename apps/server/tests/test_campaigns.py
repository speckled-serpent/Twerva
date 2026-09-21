"""Campaign create validation that does not need Postgres."""

import unittest
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.v1.campaigns import (
    CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL,
    CAMPAIGN_INTERESTS_REQUIRED_DETAIL,
    CAMPAIGN_NAME_REQUIRED_DETAIL,
    CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
    create_campaign,
)
from app.api.v1.schemas import CampaignCreateRequest, CampaignInterestWrite
from app.models.enums import AdvertisementType, CampaignType, Platform


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
    platforms: list[Platform] | None = None,
    account_ids: list[uuid.UUID] | None = None,
    interests: list[CampaignInterestWrite] | None = None,
) -> CampaignCreateRequest:
    """Build a Spotmu create body with complete defaults unless overridden."""

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
        campaign_type=CampaignType.SPOTMU,
        advertisement_type=AdvertisementType.CAROUSEL,
        platforms=selected_platforms,
        account_ids=selected_account_ids,
        interests=selected_interests,
    )

    return campaign_create_request


if __name__ == "__main__":
    unittest.main()
