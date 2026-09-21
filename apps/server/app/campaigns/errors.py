"""Domain errors for campaign lifecycle status transitions."""

from __future__ import annotations

import uuid

from app.models.enums import CampaignStatus


class CampaignLifecycleError(Exception):
    """Base error for campaign start / pause / resume / finish."""


class CampaignIllegalStatusTransitionError(CampaignLifecycleError):
    """Requested status change is not in CAMPAIGN_STATUS_TRANSITIONS."""

    def __init__(
        self,
        campaign_id: uuid.UUID | None,
        current_status: CampaignStatus,
        target_status: CampaignStatus,
    ) -> None:

        campaign_label: str = str(campaign_id) if campaign_id is not None else "unknown"
        super().__init__(
            (
                f"Campaign {campaign_label} cannot move from "
                f"{current_status.value} to {target_status.value}."
            ),
        )
        self.campaign_id: uuid.UUID | None = campaign_id
        self.current_status: CampaignStatus = current_status
        self.target_status: CampaignStatus = target_status


class CampaignAlreadyInTargetStatusError(CampaignLifecycleError):
    """Operator asked for a status the campaign already has."""

    def __init__(
        self,
        campaign_id: uuid.UUID | None,
        current_status: CampaignStatus,
    ) -> None:

        campaign_label: str = str(campaign_id) if campaign_id is not None else "unknown"
        super().__init__(
            f"Campaign {campaign_label} is already {current_status.value}.",
        )
        self.campaign_id: uuid.UUID | None = campaign_id
        self.current_status: CampaignStatus = current_status
