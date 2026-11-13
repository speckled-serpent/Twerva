"""Place an assembled carousel on a campaign timeline."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_campaign_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    CampaignPostCreateRequest,
    CampaignPostFrameRead,
    CampaignPostRead,
)
from app.auth.dependencies import require_admin_ops_operator
from app.campaigns.posts import assembly_for_post, ordered_frames, place_campaign_post
from app.db import get_our_database_session
from app.models.campaign import Campaign, CampaignPost
from app.models.carousel import AssembledCarouselFrame, CarouselAssembly
from app.models.ops_user import OpsUser
from app.schedule.errors import CadenceCapExceededError


def register_campaign_post_routes(campaigns_router: APIRouter) -> None:
    """Attach the campaign timeline routes.

    Args:
        campaigns_router: Router mounted at ``/campaigns``.
    """

    campaigns_router.add_api_route(
        "/{campaign_id}/posts",
        place_campaign_post_by_id,
        methods=["POST"],
        response_model=CampaignPostRead,
        status_code=status.HTTP_201_CREATED,
    )


def place_campaign_post_by_id(
    campaign_id: uuid.UUID,
    campaign_post_create_request: CampaignPostCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CampaignPostRead:
    """Place one assembled carousel on the campaign timeline.

    Readers cannot call this. The campaign status is not consulted.
    """

    _ = current_ops_operator
    found_campaign: Campaign = fetch_campaign_by_id_or_raise(
        campaign_id,
        our_database_session,
    )
    created_post: CampaignPost

    try:
        created_post = place_campaign_post(
            found_campaign,
            campaign_post_create_request.assembled_carousel_id,
            campaign_post_create_request.account_id,
            campaign_post_create_request.scheduled_for,
            our_database_session,
        )
    except CadenceCapExceededError as cadence_error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(cadence_error),
        ) from cadence_error

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Campaign post could not be saved.",
    )
    campaign_post_read: CampaignPostRead = serialize_campaign_post(created_post)

    return campaign_post_read


def serialize_campaign_post(post: CampaignPost) -> CampaignPostRead:
    """Map one stored post to the read model."""

    assembly: CarouselAssembly = assembly_for_post(post)
    frames: list[AssembledCarouselFrame] = ordered_frames(post.assembled_carousel)
    frame_reads: list[CampaignPostFrameRead] = [
        CampaignPostFrameRead(
            id=frame.id,
            position=frame.position,
            blocked=frame.blocked,
            block_reason=frame.block_reason,
            block_detail=frame.block_detail,
        )
        for frame in frames
    ]
    post_is_blocked: bool = any(frame.blocked for frame in frames)
    campaign_post_read: CampaignPostRead = CampaignPostRead(
        id=post.id,
        campaign_id=post.campaign_id,
        carousel_id=assembly.carousel_id,
        generation_number=assembly.generation_number,
        assembled_carousel_id=post.assembled_carousel_id,
        account_id=post.account_id,
        platform=post.account.platform,
        handle=post.account.handle,
        status=post.status,
        scheduled_for=post.scheduled_for,
        published_at=post.published_at,
        platform_post_id=post.platform_post_id,
        platform_post_url=post.platform_post_url,
        last_error=post.last_error,
        caption=post.assembled_carousel.caption,
        cta_url=post.assembled_carousel.cta_url,
        blocked=post_is_blocked,
        frames=frame_reads,
    )

    return campaign_post_read
