"""Ops proxy for live Spotmu interest search. No ingest."""

from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.schemas import SpotmuInterestSearchHitResponse
from app.ingest.spotmu import (
    DEFAULT_INTEREST_SEARCH_LIMIT,
    MAXIMUM_INTEREST_SEARCH_LIMIT,
    SpotmuInterestNotJsonError,
    SpotmuInterestRequestError,
    SpotmuInterestSearchHit,
    SpotmuInterestTimeoutError,
    search_spotmu_interests,
)
from app.settings import Settings, get_settings


spotmu_router: APIRouter = APIRouter(prefix="/spotmu", tags=["spotmu"])


@spotmu_router.get(
    "/interests/search",
    response_model=list[SpotmuInterestSearchHitResponse],
)
def search_spotmu_interests_for_ops(
    q: str = Query(default="", max_length=200),
    limit: int = Query(
        default=DEFAULT_INTEREST_SEARCH_LIMIT,
        ge=1,
        le=MAXIMUM_INTEREST_SEARCH_LIMIT,
    ),
) -> list[SpotmuInterestSearchHitResponse]:
    """Proxy guest Spotmu interest search for the campaign form.

    Calls ``GET {SPOTMU_API_BASE_URL}/api/v1/interests/search?q=``
    server-side. Blank ``q`` returns an empty list without HTTP.
    """

    settings: Settings = get_settings()

    try:
        search_hits: list[SpotmuInterestSearchHit] = search_spotmu_interests(
            q,
            api_base_url=settings.spotmu_api_base_url,
            limit=limit,
        )
    except (
        SpotmuInterestNotJsonError,
        SpotmuInterestTimeoutError,
        SpotmuInterestRequestError,
    ) as fetch_error:
        _raise_http_exception_for_spotmu_search_error(fetch_error)

    search_hit_responses: list[SpotmuInterestSearchHitResponse] = [
        SpotmuInterestSearchHitResponse(
            slug=search_hit.slug,
            title=search_hit.title,
            spotmu_interest_id=search_hit.spotmu_interest_id,
            interest_heading=search_hit.interest_heading,
        )
        for search_hit in search_hits
    ]

    return search_hit_responses


def _raise_http_exception_for_spotmu_search_error(fetch_error: Exception) -> NoReturn:
    """Map Spotmu search client errors to HTTP status codes.

    Args:
        fetch_error: Client exception.

    Raises:
        HTTPException: Always.
    """

    if isinstance(fetch_error, SpotmuInterestTimeoutError):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(fetch_error),
        ) from fetch_error

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(fetch_error),
    ) from fetch_error
