"""Campaign create/list/get routes. Persist definition only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.lookups import fetch_account_by_id_or_raise, fetch_campaign_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    CampaignAccountReadResponse,
    CampaignCreateRequest,
    CampaignInterestReadResponse,
    CampaignInterestWrite,
    CampaignReadResponse,
)
from app.auth.dependencies import require_authenticated_ops_operator
from app.campaigns.slug import (
    allocate_unique_campaign_slug,
    hashtag_from_campaign_slug,
    slugify_campaign_name,
)
from app.db import get_our_database_session
from app.models import (
    Account,
    Campaign,
    CampaignAccount,
    CampaignInterest,
    CampaignStatus,
    CampaignType,
    OpsUser,
    Platform,
)


CAMPAIGN_TYPE_OTHER_NOT_IMPLEMENTED: str = (
    "Other campaign types are not implemented yet. Coming soon."
)
DUPLICATE_ACCOUNT_PLATFORM_DETAIL: str = (
    "Account platform is not in the campaign platform list."
)

campaigns_router: APIRouter = APIRouter(prefix="/campaigns", tags=["campaigns"])


@campaigns_router.post(
    "",
    response_model=CampaignReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_campaign(
    campaign_create_request: CampaignCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> CampaignReadResponse:
    """Persist a not-started campaign definition. No ingest or generate."""

    if campaign_create_request.campaign_type == CampaignType.OTHER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_TYPE_OTHER_NOT_IMPLEMENTED,
        )

    stripped_name: str = campaign_create_request.name.strip()

    if stripped_name == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign name is required.",
        )

    platform_values: list[str] = _unique_platform_values(
        campaign_create_request.platforms,
    )
    unique_account_ids: list[uuid.UUID] = _unique_account_ids(
        campaign_create_request.account_ids,
    )
    unique_interests: list[CampaignInterestWrite] = _unique_interests(
        campaign_create_request.interests,
    )
    selected_accounts: list[Account] = _load_accounts_or_raise(
        unique_account_ids,
        our_database_session,
    )
    _raise_if_account_platforms_mismatch(selected_accounts, platform_values)

    requested_slug: str = slugify_campaign_name(stripped_name)
    taken_slugs: set[str] = _load_taken_campaign_slugs(our_database_session)
    campaign_slug: str = allocate_unique_campaign_slug(requested_slug, taken_slugs)
    campaign_hashtag: str = hashtag_from_campaign_slug(campaign_slug)

    created_campaign: Campaign = Campaign(
        name=stripped_name,
        slug=campaign_slug,
        hashtag=campaign_hashtag,
        campaign_type=campaign_create_request.campaign_type,
        advertisement_type=campaign_create_request.advertisement_type,
        status=CampaignStatus.NOT_STARTED,
        platforms=platform_values,
        created_by=None if current_ops_operator is None else current_ops_operator.id,
    )
    our_database_session.add(created_campaign)
    our_database_session.flush()

    for selected_account in selected_accounts:
        account_link: CampaignAccount = CampaignAccount(
            campaign_id=created_campaign.id,
            account_id=selected_account.id,
        )
        our_database_session.add(account_link)

    for interest_write in unique_interests:
        interest_link: CampaignInterest = CampaignInterest(
            campaign_id=created_campaign.id,
            spotmu_slug=interest_write.slug.strip(),
            spotmu_interest_id=_optional_stripped_text(
                interest_write.spotmu_interest_id,
            ),
            title=_optional_stripped_text(interest_write.title),
        )
        our_database_session.add(interest_link)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Campaign slug or interest already exists.",
    )
    reloaded_campaign: Campaign = _load_campaign_with_joins(
        created_campaign.id,
        our_database_session,
    )
    campaign_read_response: CampaignReadResponse = serialize_campaign(
        reloaded_campaign,
    )

    return campaign_read_response


@campaigns_router.get("", response_model=list[CampaignReadResponse])
def list_campaigns(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[CampaignReadResponse]:
    """Return every Campaign, newest first."""

    campaign_selection = (
        select(Campaign)
        .options(
            selectinload(Campaign.account_links).selectinload(CampaignAccount.account),
            selectinload(Campaign.interest_links),
        )
        .order_by(Campaign.created_at.desc())
    )
    campaign_scalars = our_database_session.scalars(campaign_selection)
    campaigns: list[Campaign] = list(campaign_scalars.all())
    campaign_read_responses: list[CampaignReadResponse] = [
        serialize_campaign(campaign) for campaign in campaigns
    ]

    return campaign_read_responses


@campaigns_router.get("/{campaign_id}", response_model=CampaignReadResponse)
def get_campaign_by_id(
    campaign_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> CampaignReadResponse:
    """Return one Campaign by primary key."""

    fetch_campaign_by_id_or_raise(campaign_id, our_database_session)
    found_campaign: Campaign = _load_campaign_with_joins(
        campaign_id,
        our_database_session,
    )
    campaign_read_response: CampaignReadResponse = serialize_campaign(
        found_campaign,
    )

    return campaign_read_response


def serialize_campaign(campaign: Campaign) -> CampaignReadResponse:
    """Map a Campaign row plus joins to the read schema.

    Args:
        campaign: Loaded campaign with account and interest links.

    Returns:
        API response including counts and snapshots.
    """

    account_responses: list[CampaignAccountReadResponse] = []

    for account_link in campaign.account_links:
        linked_account: Account = account_link.account
        account_responses.append(
            CampaignAccountReadResponse(
                id=linked_account.id,
                platform=linked_account.platform,
                handle=linked_account.handle,
            ),
        )

    interest_responses: list[CampaignInterestReadResponse] = []

    for interest_link in campaign.interest_links:
        interest_responses.append(
            CampaignInterestReadResponse(
                slug=interest_link.spotmu_slug,
                title=interest_link.title,
                spotmu_interest_id=interest_link.spotmu_interest_id,
            ),
        )

    platform_values: list[Platform] = [
        Platform(platform_value) for platform_value in campaign.platforms
    ]
    campaign_read_response: CampaignReadResponse = CampaignReadResponse(
        id=campaign.id,
        name=campaign.name,
        slug=campaign.slug,
        hashtag=campaign.hashtag,
        campaign_type=campaign.campaign_type,
        advertisement_type=campaign.advertisement_type,
        status=campaign.status,
        platforms=platform_values,
        account_count=len(account_responses),
        interest_count=len(interest_responses),
        accounts=account_responses,
        interests=interest_responses,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        created_by=campaign.created_by,
    )

    return campaign_read_response


def _load_campaign_with_joins(
    campaign_id: uuid.UUID,
    our_database_session: Session,
) -> Campaign:
    """Reload a campaign with account and interest links."""

    campaign_selection = (
        select(Campaign)
        .options(
            selectinload(Campaign.account_links).selectinload(CampaignAccount.account),
            selectinload(Campaign.interest_links),
        )
        .where(Campaign.id == campaign_id)
    )
    found_campaign: Campaign | None = our_database_session.scalars(
        campaign_selection,
    ).first()

    if found_campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign not found: {campaign_id}",
        )

    return found_campaign


def _load_taken_campaign_slugs(our_database_session: Session) -> set[str]:
    """Return every existing campaign slug."""

    slug_selection = select(Campaign.slug)
    slug_scalars = our_database_session.scalars(slug_selection)
    taken_slugs: set[str] = set(slug_scalars.all())

    return taken_slugs


def _load_accounts_or_raise(
    account_ids: list[uuid.UUID],
    our_database_session: Session,
) -> list[Account]:
    """Load each account id or raise 404."""

    selected_accounts: list[Account] = []

    for account_id in account_ids:
        found_account: Account = fetch_account_by_id_or_raise(
            account_id,
            our_database_session,
        )
        selected_accounts.append(found_account)

    return selected_accounts


def _raise_if_account_platforms_mismatch(
    selected_accounts: list[Account],
    platform_values: list[str],
) -> None:
    """Reject accounts whose platform is not on the campaign."""

    if not platform_values:

        return

    allowed_platforms: set[str] = set(platform_values)

    for selected_account in selected_accounts:

        if selected_account.platform.value not in allowed_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=DUPLICATE_ACCOUNT_PLATFORM_DETAIL,
            )


def _unique_platform_values(platforms: list[Platform]) -> list[str]:
    """Preserve order and drop duplicate platforms."""

    unique_platforms: list[str] = []
    seen_platforms: set[str] = set()

    for platform in platforms:
        platform_value: str = platform.value

        if platform_value in seen_platforms:
            continue

        seen_platforms.add(platform_value)
        unique_platforms.append(platform_value)

    return unique_platforms


def _unique_account_ids(account_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Preserve order and drop duplicate account ids."""

    unique_ids: list[uuid.UUID] = []
    seen_ids: set[uuid.UUID] = set()

    for account_id in account_ids:

        if account_id in seen_ids:
            continue

        seen_ids.add(account_id)
        unique_ids.append(account_id)

    return unique_ids


def _unique_interests(
    interests: list[CampaignInterestWrite],
) -> list[CampaignInterestWrite]:
    """Keep the first write per non-empty slug."""

    unique_interests: list[CampaignInterestWrite] = []
    seen_slugs: set[str] = set()

    for interest_write in interests:
        stripped_slug: str = interest_write.slug.strip()

        if stripped_slug == "" or stripped_slug in seen_slugs:
            continue

        seen_slugs.add(stripped_slug)
        unique_interests.append(
            CampaignInterestWrite(
                slug=stripped_slug,
                title=interest_write.title,
                spotmu_interest_id=interest_write.spotmu_interest_id,
            ),
        )

    return unique_interests


def _optional_stripped_text(raw_value: str | None) -> str | None:
    """Return a stripped string or None when blank."""

    if raw_value is None:

        return None

    stripped_value: str = raw_value.strip()

    if stripped_value == "":

        return None

    return stripped_value
