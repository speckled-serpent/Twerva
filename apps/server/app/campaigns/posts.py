"""Place one assembled carousel on a campaign timeline."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.account import Account
from app.models.campaign import (
    CAMPAIGN_POST_UPCOMING_STATUS,
    Campaign,
    CampaignAccount,
    CampaignPost,
)
from app.models.carousel import AssembledCarousel, AssembledCarouselFrame, CarouselAssembly
from app.schedule.cadence import raise_if_cadence_cap_exceeded


CAMPAIGN_POST_NEEDS_CAROUSEL_DETAIL: str = (
    "Pick a carousel before scheduling a post."
)
CAMPAIGN_POST_ACCOUNT_DETAIL: str = "That account is not on this campaign."
CAMPAIGN_POST_BLOCKED_DETAIL: str = (
    "This carousel is blocked. Assemble again before posting it."
)
CAMPAIGN_POST_DUPLICATE_DETAIL: str = (
    "This carousel is already scheduled on that account."
)
ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL: str = "Assembled carousel not found."


def place_campaign_post(
    campaign: Campaign,
    assembled_carousel_id: uuid.UUID,
    account_id: uuid.UUID,
    scheduled_for: datetime,
    our_database_session: Session,
) -> CampaignPost:
    """Store an upcoming post for one assembled carousel and linked account.

    The campaign status is not consulted. Nothing is added when a check
    fails. The caller commits.

    Args:
        campaign: Campaign that will own the post.
        assembled_carousel_id: Reviewed carousel to place.
        account_id: Linked account that will carry the post.
        scheduled_for: Clock time the operator chose.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The flushed upcoming post, with its carousel, frames, and account
        loaded.

    Raises:
        HTTPException: The carousel is missing, the account is not linked,
            a frame is blocked, or this pair is already scheduled.
        CadenceCapExceededError: The account cap is already met.
    """

    if campaign.carousel_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_NEEDS_CAROUSEL_DETAIL,
        )

    assembled_carousel: AssembledCarousel | None = our_database_session.scalars(
        select(AssembledCarousel)
        .where(AssembledCarousel.id == assembled_carousel_id)
        .options(
            selectinload(AssembledCarousel.frames),
            selectinload(AssembledCarousel.assembly),
        ),
    ).first()

    if assembled_carousel is None or assembled_carousel.assembly.carousel_id != campaign.carousel_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL,
        )

    account_link: CampaignAccount | None = our_database_session.scalars(
        select(CampaignAccount).where(
            CampaignAccount.campaign_id == campaign.id,
            CampaignAccount.account_id == account_id,
        ),
    ).first()

    if account_link is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_ACCOUNT_DETAIL,
        )

    if _assembled_carousel_is_blocked(assembled_carousel):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_BLOCKED_DETAIL,
        )

    existing_post: CampaignPost | None = our_database_session.scalars(
        select(CampaignPost).where(
            CampaignPost.assembled_carousel_id == assembled_carousel.id,
            CampaignPost.account_id == account_id,
        ),
    ).first()

    if existing_post is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CAMPAIGN_POST_DUPLICATE_DETAIL,
        )

    linked_account: Account | None = our_database_session.get(Account, account_id)

    if linked_account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CAMPAIGN_POST_ACCOUNT_DETAIL,
        )

    raise_if_cadence_cap_exceeded(
        linked_account,
        scheduled_for,
        our_database_session,
    )
    created_post: CampaignPost = CampaignPost(
        campaign_id=campaign.id,
        assembled_carousel_id=assembled_carousel.id,
        account_id=account_id,
        status=CAMPAIGN_POST_UPCOMING_STATUS,
        scheduled_for=scheduled_for,
        published_at=None,
        platform_post_id=None,
        platform_post_url=None,
        last_error=None,
    )
    our_database_session.add(created_post)
    our_database_session.flush()
    loaded_post: CampaignPost = _load_campaign_post(
        created_post.id,
        our_database_session,
    )

    return loaded_post


def _assembled_carousel_is_blocked(assembled_carousel: AssembledCarousel) -> bool:
    """Return whether any frozen frame is blocked."""

    frame_is_blocked: bool = any(
        frame.blocked for frame in assembled_carousel.frames
    )

    return frame_is_blocked


def _load_campaign_post(
    campaign_post_id: uuid.UUID,
    our_database_session: Session,
) -> CampaignPost:
    """Return one post with the rows the read model needs."""

    loaded_post: CampaignPost | None = our_database_session.scalars(
        select(CampaignPost)
        .where(CampaignPost.id == campaign_post_id)
        .options(
            selectinload(CampaignPost.assembled_carousel).selectinload(
                AssembledCarousel.frames,
            ),
            selectinload(CampaignPost.assembled_carousel).selectinload(
                AssembledCarousel.assembly,
            ),
            selectinload(CampaignPost.account),
        ),
    ).first()

    if loaded_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL,
        )

    return loaded_post


def ordered_frames(
    assembled_carousel: AssembledCarousel,
) -> list[AssembledCarouselFrame]:
    """Return frames in position order."""

    ordered: list[AssembledCarouselFrame] = sorted(
        list(assembled_carousel.frames),
        key=lambda frame: frame.position,
    )

    return ordered


def assembly_for_post(post: CampaignPost) -> CarouselAssembly:
    """Return the assembly that owns this post's carousel."""

    assembly: CarouselAssembly = post.assembled_carousel.assembly

    return assembly
