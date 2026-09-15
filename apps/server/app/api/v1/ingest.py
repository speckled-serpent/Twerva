"""On-demand Spotmu ingest routes (1.3c / 1.3d). No scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.schemas import (
    SourceItemReadResponse,
    SpotmuIngestSlugError,
    SpotmuSyncRequest,
    SpotmuSyncResponse,
)
from app.db import get_our_database_session
from app.ingest.spotmu import (
    SpotmuInterestFetch,
    SpotmuInterestNotFoundError,
    SpotmuInterestNotJsonError,
    SpotmuInterestRequestError,
    SpotmuInterestTimeoutError,
    fetch_spotmu_interest_by_slug,
    list_spotmu_interest_slugs_from_sitemap,
)
from app.ingest.upsert import (
    UpsertSpotmuInterestResult,
    upsert_spotmu_interest_source_item,
)


@dataclass
class _SyncSlugOutcome:
    """One slug from an on-demand sync: success flag or an error."""

    created: bool | None
    error: SpotmuIngestSlugError | None


ingest_router: APIRouter = APIRouter(
    prefix="/ingest/spotmu",
    tags=["ingest"],
)


@ingest_router.post(
    "/interests/{slug}",
    response_model=SourceItemReadResponse,
)
def ingest_spotmu_interest_by_slug(
    slug: str,
    our_database_session: Session = Depends(get_our_database_session),
) -> SourceItemReadResponse:
    """Fetch one public Spotmu interest and upsert it under Brand spotmu."""

    fetched_interest: SpotmuInterestFetch

    try:
        fetched_interest = fetch_spotmu_interest_by_slug(slug)
    except (
        SpotmuInterestNotFoundError,
        SpotmuInterestNotJsonError,
        SpotmuInterestTimeoutError,
        SpotmuInterestRequestError,
    ) as fetch_error:
        _raise_http_exception_for_spotmu_fetch_error(fetch_error)

    upsert_result: UpsertSpotmuInterestResult = upsert_spotmu_interest_source_item(
        fetched_interest,
        our_database_session,
    )
    our_database_session.commit()
    our_database_session.refresh(upsert_result.source_item)
    source_item_read_response: SourceItemReadResponse = (
        SourceItemReadResponse.model_validate(upsert_result.source_item)
    )

    return source_item_read_response


@ingest_router.post("/sync", response_model=SpotmuSyncResponse)
def sync_spotmu_interests(
    spotmu_sync_request: SpotmuSyncRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> SpotmuSyncResponse:
    """Upsert a slug list or a capped sitemap window. On-demand only."""

    candidate_slugs: list[str] = _resolve_sync_candidate_slugs(spotmu_sync_request)
    created_count: int = 0
    updated_count: int = 0
    sync_errors: list[SpotmuIngestSlugError] = []

    for interest_slug in candidate_slugs:
        slug_outcome: _SyncSlugOutcome = _upsert_one_sync_slug(
            interest_slug,
            our_database_session,
        )

        if slug_outcome.error is not None:
            sync_errors.append(slug_outcome.error)
            continue

        if slug_outcome.created:
            created_count += 1
        else:
            updated_count += 1

    spotmu_sync_response: SpotmuSyncResponse = SpotmuSyncResponse(
        created_count=created_count,
        updated_count=updated_count,
        failed_count=len(sync_errors),
        errors=sync_errors,
    )

    return spotmu_sync_response


def _resolve_sync_candidate_slugs(
    spotmu_sync_request: SpotmuSyncRequest,
) -> list[str]:
    """Use explicit slugs when provided; otherwise read the sitemap.

    Args:
        spotmu_sync_request: Optional slugs and limit.

    Returns:
        Slugs to fetch, already capped.

    Raises:
        HTTPException: When sitemap discovery fails.
    """

    request_limit: int = spotmu_sync_request.limit
    provided_slugs: list[str] | None = spotmu_sync_request.slugs

    if provided_slugs is not None:
        stripped_slugs: list[str] = [
            slug_value.strip()
            for slug_value in provided_slugs
            if slug_value.strip() != ""
        ]
        limited_provided_slugs: list[str] = stripped_slugs[:request_limit]

        return limited_provided_slugs

    try:
        sitemap_slugs: list[str] = list_spotmu_interest_slugs_from_sitemap(
            limit=request_limit,
        )
    except (
        SpotmuInterestNotJsonError,
        SpotmuInterestTimeoutError,
        SpotmuInterestRequestError,
    ) as sitemap_error:
        _raise_http_exception_for_spotmu_fetch_error(sitemap_error)

    return sitemap_slugs


def _upsert_one_sync_slug(
    interest_slug: str,
    our_database_session: Session,
) -> _SyncSlugOutcome:
    """Fetch+upsert one slug; commit on success, rollback on failure.

    Args:
        interest_slug: Spotmu interest slug.
        our_database_session: Open session.

    Returns:
        Created flag on success, or a per-slug error on failure.
    """

    try:
        fetched_interest: SpotmuInterestFetch = fetch_spotmu_interest_by_slug(
            interest_slug,
        )
        upsert_result: UpsertSpotmuInterestResult = (
            upsert_spotmu_interest_source_item(
                fetched_interest,
                our_database_session,
            )
        )
        our_database_session.commit()
        success_outcome: _SyncSlugOutcome = _SyncSlugOutcome(
            created=upsert_result.created,
            error=None,
        )

        return success_outcome
    except (
        SpotmuInterestNotFoundError,
        SpotmuInterestNotJsonError,
        SpotmuInterestTimeoutError,
        SpotmuInterestRequestError,
    ) as fetch_error:
        our_database_session.rollback()
        slug_error: SpotmuIngestSlugError = SpotmuIngestSlugError(
            slug=interest_slug,
            error=str(fetch_error),
        )
        failed_outcome: _SyncSlugOutcome = _SyncSlugOutcome(
            created=None,
            error=slug_error,
        )

        return failed_outcome


def _raise_http_exception_for_spotmu_fetch_error(fetch_error: Exception) -> NoReturn:
    """Map Spotmu client errors to HTTP status codes.

    Args:
        fetch_error: Client exception.

    Raises:
        HTTPException: Always.
    """

    if isinstance(fetch_error, SpotmuInterestNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(fetch_error),
        ) from fetch_error

    if isinstance(fetch_error, SpotmuInterestTimeoutError):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(fetch_error),
        ) from fetch_error

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(fetch_error),
    ) from fetch_error
