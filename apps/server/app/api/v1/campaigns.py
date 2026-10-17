"""Campaign create/list/get plus start/pause/resume/finish status actions."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.lookups import (
    fetch_account_by_id_or_raise,
    fetch_campaign_by_id_or_raise,
    fetch_carousel_by_id_or_raise,
    fetch_skeleton_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    CampaignAccountReadResponse,
    CampaignCarouselRead,
    CampaignCarouselSlideRead,
    CampaignCreateRequest,
    CampaignInterestReadResponse,
    CampaignInterestWrite,
    CampaignReadResponse,
)
from app.auth.dependencies import (
    require_admin_ops_operator,
    require_authenticated_ops_operator,
)
from app.campaigns.assemble import assemble_carousels
from app.campaigns.errors import CampaignLifecycleError
from app.campaigns.lifecycle import (
    finish_campaign,
    pause_campaign,
    resume_campaign,
    start_campaign,
)
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
    CampaignCarousel,
    CampaignCarouselSlide,
    CampaignInterest,
    CampaignStatus,
    CampaignType,
    Carousel,
    OpsUser,
    Platform,
    Skeleton,
    Slide,
)
from app.carousels.editing import new_row_id
from app.carousels.slide_text_review import live_slides


CAMPAIGN_TYPE_OTHER_NOT_IMPLEMENTED: str = (
    "Other campaign types are not implemented yet. Coming soon."
)
CAMPAIGN_NAME_REQUIRED_DETAIL: str = "Campaign name is required."
CAMPAIGN_PLATFORMS_REQUIRED_DETAIL: str = "At least one platform is required."
CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL: str = "At least one account is required."
CAMPAIGN_INTERESTS_REQUIRED_DETAIL: str = (
    "At least one Spotmu interest is required."
)
DUPLICATE_ACCOUNT_PLATFORM_DETAIL: str = (
    "Account platform is not in the campaign platform list."
)
CAROUSEL_SKELETON_MISMATCH_DETAIL: str = "That carousel is not bound to this skeleton."
CAMPAIGN_RUN_REQUIRES_BINDING_DETAIL: str = (
    "Pick a skeleton and a carousel before running."
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
    """Persist a ready campaign definition. No ingest or generate."""

    if campaign_create_request.campaign_type == CampaignType.OTHER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_TYPE_OTHER_NOT_IMPLEMENTED,
        )

    stripped_name: str = campaign_create_request.name.strip()

    if stripped_name == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_NAME_REQUIRED_DETAIL,
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

    _raise_if_spotmu_create_collections_empty(
        campaign_create_request.campaign_type,
        platform_values,
        unique_account_ids,
        unique_interests,
    )

    selected_accounts: list[Account] = _load_accounts_or_raise(
        unique_account_ids,
        our_database_session,
    )
    _raise_if_account_platforms_mismatch(selected_accounts, platform_values)
    resolve_campaign_binding(
        campaign_create_request.skeleton_id,
        campaign_create_request.carousel_id,
        our_database_session,
    )

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
        status=CampaignStatus.READY,
        platforms=platform_values,
        created_by=None if current_ops_operator is None else current_ops_operator.id,
        skeleton_id=campaign_create_request.skeleton_id,
        carousel_id=campaign_create_request.carousel_id,
    )
    created_campaign.carousels = []
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
        .options(*_campaign_read_options())
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


@campaigns_router.post("/{campaign_id}/run", response_model=CampaignReadResponse)
def run_campaign(
    campaign_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CampaignReadResponse:
    """Assemble live slides from the campaign carousel into carousels.

    Draft slides stay out. Each carousel is a pick that
    ``assert_slide_pick_allowed`` accepts. The skeleton on the campaign
    is the frame. This does not call a text model.
    """

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )

    if found_campaign.skeleton_id is None or found_campaign.carousel_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_RUN_REQUIRES_BINDING_DETAIL,
        )

    bound_skeleton, bound_source = resolve_campaign_binding(
        found_campaign.skeleton_id,
        found_campaign.carousel_id,
        our_database_session,
    )
    _ = bound_skeleton
    _replace_campaign_carousels(found_campaign, bound_source, our_database_session)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Campaign run could not be saved.",
    )
    reloaded_campaign: Campaign = _load_campaign_with_joins(
        found_campaign.id,
        our_database_session,
    )
    campaign_read_response: CampaignReadResponse = serialize_campaign(
        reloaded_campaign,
    )

    return campaign_read_response


@campaigns_router.post("/{campaign_id}/start", response_model=CampaignReadResponse)
def start_campaign_by_id(
    campaign_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> CampaignReadResponse:
    """Move a ready campaign to running. Does not ingest or generate."""

    campaign_read_response: CampaignReadResponse = _apply_campaign_lifecycle_action_and_reload(
        campaign_id,
        our_database_session,
        start_campaign,
        "Campaign could not be started (conflict).",
    )

    return campaign_read_response


@campaigns_router.post("/{campaign_id}/pause", response_model=CampaignReadResponse)
def pause_campaign_by_id(
    campaign_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> CampaignReadResponse:
    """Move a running campaign to paused."""

    campaign_read_response: CampaignReadResponse = _apply_campaign_lifecycle_action_and_reload(
        campaign_id,
        our_database_session,
        pause_campaign,
        "Campaign could not be paused (conflict).",
    )

    return campaign_read_response


@campaigns_router.post("/{campaign_id}/resume", response_model=CampaignReadResponse)
def resume_campaign_by_id(
    campaign_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> CampaignReadResponse:
    """Move a paused campaign back to running."""

    campaign_read_response: CampaignReadResponse = _apply_campaign_lifecycle_action_and_reload(
        campaign_id,
        our_database_session,
        resume_campaign,
        "Campaign could not be resumed (conflict).",
    )

    return campaign_read_response


@campaigns_router.post("/{campaign_id}/finish", response_model=CampaignReadResponse)
def finish_campaign_by_id(
    campaign_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> CampaignReadResponse:
    """Move a running or paused campaign to finished."""

    campaign_read_response: CampaignReadResponse = _apply_campaign_lifecycle_action_and_reload(
        campaign_id,
        our_database_session,
        finish_campaign,
        "Campaign could not be finished (conflict).",
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
    skeleton_name: str | None = None if campaign.skeleton is None else campaign.skeleton.name
    carousel_name: str | None = None if campaign.carousel is None else campaign.carousel.name
    carousel_responses: list[CampaignCarouselRead] = [
        _serialize_carousel(carousel) for carousel in list(campaign.carousels)
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
        skeleton_id=campaign.skeleton_id,
        carousel_id=campaign.carousel_id,
        skeleton_name=skeleton_name,
        carousel_name=carousel_name,
        account_count=len(account_responses),
        interest_count=len(interest_responses),
        accounts=account_responses,
        interests=interest_responses,
        carousels=carousel_responses,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        created_by=campaign.created_by,
    )

    return campaign_read_response


def _apply_campaign_lifecycle_action_and_reload(
    campaign_id: uuid.UUID,
    our_database_session: Session,
    apply_lifecycle_action: Callable[[Campaign], Campaign],
    conflict_detail: str,
) -> CampaignReadResponse:
    """Load a campaign, apply a status action, commit, and reload joins.

    Args:
        campaign_id: Campaign primary key.
        our_database_session: Request-scoped SQLAlchemy session.
        apply_lifecycle_action: start / pause / resume / finish mutator.
        conflict_detail: Message if the commit hits an integrity error.

    Returns:
        Serialized campaign after the status change.

    Raises:
        HTTPException: 404 if missing; 400 on illegal or already-target status.
    """

    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )

    try:
        apply_lifecycle_action(found_campaign)
    except CampaignLifecycleError as lifecycle_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(lifecycle_error),
        ) from lifecycle_error

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=conflict_detail,
    )
    reloaded_campaign: Campaign = _load_campaign_with_joins(
        campaign_id,
        our_database_session,
    )
    campaign_read_response: CampaignReadResponse = serialize_campaign(
        reloaded_campaign,
    )

    return campaign_read_response


def _load_campaign_with_joins(
    campaign_id: uuid.UUID,
    our_database_session: Session,
) -> Campaign:
    """Reload a campaign with account and interest links."""

    campaign_selection = (
        select(Campaign)
        .options(*_campaign_read_options())
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


def resolve_campaign_binding(
    skeleton_id: uuid.UUID,
    carousel_id: uuid.UUID,
    our_database_session: Session,
) -> tuple[Skeleton, Carousel]:
    """Load the skeleton and the carousel, and require that carousel's skeleton.

    Args:
        skeleton_id: Skeleton the operator picked.
        carousel_id: Carousel the operator picked from that skeleton's list.
        our_database_session: Request-scoped SQLAlchemy session.

    Returns:
        The skeleton and the carousel.

    Raises:
        HTTPException: 404 when either row is missing. 400 when the
            carousel is bound to a different skeleton.
    """

    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(skeleton_id, our_database_session)
    found_source: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )

    if found_source.skeleton_id != found_skeleton.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAROUSEL_SKELETON_MISMATCH_DETAIL,
        )

    return found_skeleton, found_source


def _campaign_read_options() -> tuple[object, ...]:
    """Eager loads for a campaign read, including the latest carousels."""

    read_options: tuple[object, ...] = (
        selectinload(Campaign.account_links).selectinload(CampaignAccount.account),
        selectinload(Campaign.interest_links),
        selectinload(Campaign.skeleton),
        selectinload(Campaign.carousel),
        selectinload(Campaign.carousels)
        .selectinload(CampaignCarousel.slides)
        .selectinload(CampaignCarouselSlide.slide),
    )

    return read_options


def _replace_campaign_carousels(
    campaign: Campaign,
    carousel: Carousel,
    our_database_session: Session,
) -> None:
    """Replace the stored carousels with a fresh assembly of live slides."""

    for existing_carousel in list(campaign.carousels):
        our_database_session.delete(existing_carousel)

    campaign.carousels = []
    our_database_session.flush()
    ordered_live_slides: list[Slide] = sorted(
        live_slides(list(carousel.slides)),
        key=lambda slide: (slide.position, str(slide.id)),
    )
    exclusion_pairs: list[tuple[uuid.UUID, uuid.UUID]] = []

    for source_slide in list(carousel.slides):

        for exclusion in list(source_slide.exclusions):
            exclusion_pairs.append((exclusion.slide_id, exclusion.excluded_slide_id))

    live_slide_ids: list[uuid.UUID] = [slide.id for slide in ordered_live_slides]
    carousel_groups: list[list[uuid.UUID]] = assemble_carousels(
        live_slide_ids,
        exclusion_pairs,
    )
    slides_by_id: dict[uuid.UUID, Slide] = {slide.id: slide for slide in ordered_live_slides}

    for carousel_position, grouped_ids in enumerate(carousel_groups):
        created_carousel: CampaignCarousel = CampaignCarousel(
            id=new_row_id(),
            campaign_id=campaign.id,
            position=carousel_position,
        )
        created_slides: list[CampaignCarouselSlide] = []

        for slide_position, slide_id in enumerate(grouped_ids):
            created_slide: CampaignCarouselSlide = CampaignCarouselSlide(
                id=new_row_id(),
                carousel_id=created_carousel.id,
                slide_id=slide_id,
                position=slide_position,
            )
            created_slide.slide = slides_by_id[slide_id]
            created_slides.append(created_slide)
            our_database_session.add(created_slide)

        created_carousel.slides = created_slides
        campaign.carousels.append(created_carousel)
        our_database_session.add(created_carousel)


def _serialize_carousel(carousel: CampaignCarousel) -> CampaignCarouselRead:
    """Map one stored carousel to its slide names."""

    slide_reads: list[CampaignCarouselSlideRead] = [
        CampaignCarouselSlideRead(
            slide_id=slide.slide_id,
            name=slide.slide.name,
            position=slide.position,
        )
        for slide in list(carousel.slides)
    ]
    carousel_read: CampaignCarouselRead = CampaignCarouselRead(
        id=carousel.id,
        position=carousel.position,
        slides=slide_reads,
    )

    return carousel_read


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


def _raise_if_spotmu_create_collections_empty(
    campaign_type: CampaignType,
    platform_values: list[str],
    unique_account_ids: list[uuid.UUID],
    unique_interests: list[CampaignInterestWrite],
) -> None:
    """Reject Spotmu-family create when required lists are empty after dedupe.

    ``spotmu`` requires platforms, accounts, and interests. ``spotmu_test``
    waives accounts so throwaway campaigns can be saved without a linked
    social handle. Provided accounts are still loaded and platform-checked
    by the caller.
    """

    if len(platform_values) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
        )

    if campaign_type == CampaignType.SPOTMU and len(unique_account_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL,
        )

    if len(unique_interests) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_INTERESTS_REQUIRED_DETAIL,
        )


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
