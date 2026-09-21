"""Campaign create validation that does not need Postgres."""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.v1.campaigns import create_campaign
from app.api.v1.schemas import CampaignCreateRequest
from app.models.enums import AdvertisementType, CampaignType


class CampaignCreateValidationTests(unittest.TestCase):
    """Other campaigns are rejected before any write."""

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


if __name__ == "__main__":
    unittest.main()
