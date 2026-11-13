"""Assemble a carousel's live slides into review rows."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_skeleton_by_id_or_raise
from app.api.v1.schemas import CarouselReadResponse
from app.auth.dependencies import require_admin_ops_operator
from app.carousels.final_assembly import assemble_carousel_final
from app.db import get_our_database_session
from app.models.carousel import Carousel
from app.models.ops_user import OpsUser
from app.models.skeleton import Skeleton


def register_carousel_assembly_routes(carousels_router: APIRouter) -> None:
    """Attach the Final assembly route.

    Args:
        carousels_router: Router mounted at ``/carousels``.
    """

    carousels_router.add_api_route(
        "/{carousel_id}/assemble",
        assemble_carousel,
        methods=["POST"],
        response_model=CarouselReadResponse,
    )


def assemble_carousel(
    carousel_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> CarouselReadResponse:
    """Draw the live slides and return the carousel detail.

    Readers cannot call this. The body is empty.
    """

    _ = current_ops_operator
    carousel: Carousel = assemble_carousel_final(carousel_id, our_database_session)
    skeleton: Skeleton = fetch_skeleton_by_id_or_raise(
        carousel.skeleton_id,
        our_database_session,
    )

    from app.api.v1.carousels import serialize_carousel

    detail: CarouselReadResponse = serialize_carousel(carousel, skeleton)

    return detail
