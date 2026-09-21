"""Apply CampaignStatus transitions (status flip only; no ingest/generate).

Operator actions:

- start: ``ready`` → ``running``
- pause: ``running`` → ``paused``
- resume: ``paused`` → ``running``
- finish: ``running`` or ``paused`` → ``finished``

Already-in-target and illegal edges raise distinct errors (HTTP 400).
"""

from __future__ import annotations

from app.campaigns.errors import (
    CampaignAlreadyInTargetStatusError,
    CampaignIllegalStatusTransitionError,
)
from app.models import Campaign
from app.models.enums import CampaignStatus


START_SOURCE_STATUSES: frozenset[CampaignStatus] = frozenset({CampaignStatus.READY})
PAUSE_SOURCE_STATUSES: frozenset[CampaignStatus] = frozenset({CampaignStatus.RUNNING})
RESUME_SOURCE_STATUSES: frozenset[CampaignStatus] = frozenset({CampaignStatus.PAUSED})
FINISH_SOURCE_STATUSES: frozenset[CampaignStatus] = frozenset(
    {CampaignStatus.RUNNING, CampaignStatus.PAUSED},
)


def start_campaign(campaign: Campaign) -> Campaign:
    """Move a ready Campaign to ``running``.

    Args:
        campaign: Row to mutate (not committed).

    Returns:
        The same Campaign instance after the transition.

    Raises:
        CampaignAlreadyInTargetStatusError: Status is already ``running``.
        CampaignIllegalStatusTransitionError: Status is not ``ready``.
    """

    applied_campaign: Campaign = _apply_campaign_lifecycle_action(
        campaign,
        START_SOURCE_STATUSES,
        CampaignStatus.RUNNING,
    )

    return applied_campaign


def pause_campaign(campaign: Campaign) -> Campaign:
    """Move a running Campaign to ``paused``.

    Args:
        campaign: Row to mutate (not committed).

    Returns:
        The same Campaign instance after the transition.

    Raises:
        CampaignAlreadyInTargetStatusError: Status is already ``paused``.
        CampaignIllegalStatusTransitionError: Status is not ``running``.
    """

    applied_campaign: Campaign = _apply_campaign_lifecycle_action(
        campaign,
        PAUSE_SOURCE_STATUSES,
        CampaignStatus.PAUSED,
    )

    return applied_campaign


def resume_campaign(campaign: Campaign) -> Campaign:
    """Move a paused Campaign back to ``running``.

    Args:
        campaign: Row to mutate (not committed).

    Returns:
        The same Campaign instance after the transition.

    Raises:
        CampaignAlreadyInTargetStatusError: Status is already ``running``.
        CampaignIllegalStatusTransitionError: Status is not ``paused``.
    """

    applied_campaign: Campaign = _apply_campaign_lifecycle_action(
        campaign,
        RESUME_SOURCE_STATUSES,
        CampaignStatus.RUNNING,
    )

    return applied_campaign


def finish_campaign(campaign: Campaign) -> Campaign:
    """Move a running or paused Campaign to terminal ``finished``.

    Args:
        campaign: Row to mutate (not committed).

    Returns:
        The same Campaign instance after the transition.

    Raises:
        CampaignAlreadyInTargetStatusError: Status is already ``finished``.
        CampaignIllegalStatusTransitionError: Status is ``ready`` or otherwise illegal.
    """

    applied_campaign: Campaign = _apply_campaign_lifecycle_action(
        campaign,
        FINISH_SOURCE_STATUSES,
        CampaignStatus.FINISHED,
    )

    return applied_campaign


def _apply_campaign_lifecycle_action(
    campaign: Campaign,
    allowed_source_statuses: frozenset[CampaignStatus],
    target_status: CampaignStatus,
) -> Campaign:
    """Flip status when the current value is an allowed source.

    Args:
        campaign: Row to mutate.
        allowed_source_statuses: Legal starting statuses for this action.
        target_status: Status to store when the transition is legal.

    Returns:
        The same Campaign instance after the transition.

    Raises:
        CampaignAlreadyInTargetStatusError: Current status is already the target.
        CampaignIllegalStatusTransitionError: Current status is not allowed.
    """

    current_status: CampaignStatus = campaign.status

    if current_status == target_status:
        raise CampaignAlreadyInTargetStatusError(campaign.id, current_status)

    if current_status not in allowed_source_statuses:
        raise CampaignIllegalStatusTransitionError(
            campaign.id,
            current_status,
            target_status,
        )

    campaign.status = target_status

    return campaign
