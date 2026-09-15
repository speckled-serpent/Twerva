"""Idempotent upsert of a fetched Spotmu interest into ``source_items``."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Query, Session
from sqlalchemy.sql.elements import ColumnElement

from app.ingest.spotmu import SpotmuInterestFetch
from app.models import Brand, SourceItem
from app.models.enums import SourceType
from app.seed import SPOTMU_BRAND_NAME, SPOTMU_BRAND_SLUG


@dataclass
class UpsertSpotmuInterestResult:
    """Outcome of one fetch-mapped upsert."""

    source_item: SourceItem
    brand: Brand
    created: bool


def upsert_spotmu_interest_source_item(
    fetched_interest: SpotmuInterestFetch,
    our_database_session: Session,
) -> UpsertSpotmuInterestResult:
    """Insert or update Brand ``spotmu`` + the interest ``SourceItem``.

    ``external_key`` is the slug. The full public JSON is stored on
    ``raw_payload``. This function flushes; the caller commits.

    Args:
        fetched_interest: Mapped public interest.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The Brand, SourceItem, and whether the source row was inserted.
    """

    brand: Brand = _get_or_create_spotmu_brand(our_database_session)
    source_item: SourceItem
    created_source_item: bool
    source_item, created_source_item = _get_or_update_spotmu_source_item(
        brand,
        fetched_interest,
        our_database_session,
    )
    upsert_result: UpsertSpotmuInterestResult = UpsertSpotmuInterestResult(
        source_item=source_item,
        brand=brand,
        created=created_source_item,
    )

    return upsert_result


def _get_or_create_spotmu_brand(our_database_session: Session) -> Brand:
    """Return Brand ``slug=spotmu``, inserting it when missing."""

    brand_query: Query[Brand] = our_database_session.query(Brand)
    slug_filter: ColumnElement[bool] = Brand.slug == SPOTMU_BRAND_SLUG
    filtered_brand_query: Query[Brand] = brand_query.filter(slug_filter)
    existing_brand: Brand | None = filtered_brand_query.one_or_none()

    if existing_brand is not None:

        return existing_brand

    created_brand: Brand = Brand(
        slug=SPOTMU_BRAND_SLUG,
        name=SPOTMU_BRAND_NAME,
    )
    our_database_session.add(created_brand)
    our_database_session.flush()

    return created_brand


def _get_or_update_spotmu_source_item(
    brand: Brand,
    fetched_interest: SpotmuInterestFetch,
    our_database_session: Session,
) -> tuple[SourceItem, bool]:
    """Return the interest row, inserting or converging mapped fields."""

    source_item_query: Query[SourceItem] = our_database_session.query(SourceItem)
    brand_filter: ColumnElement[bool] = SourceItem.brand_id == brand.id
    type_filter: ColumnElement[bool] = (
        SourceItem.source_type == SourceType.SPOTMU_INTEREST
    )
    key_filter: ColumnElement[bool] = (
        SourceItem.external_key == fetched_interest.slug
    )
    filtered_source_item_query: Query[SourceItem] = source_item_query.filter(
        brand_filter,
        type_filter,
        key_filter,
    )
    existing_source_item: SourceItem | None = (
        filtered_source_item_query.one_or_none()
    )

    if existing_source_item is not None:
        _apply_fetched_interest_fields(existing_source_item, fetched_interest)
        our_database_session.flush()

        return existing_source_item, False

    created_source_item: SourceItem = SourceItem(
        brand_id=brand.id,
        source_type=SourceType.SPOTMU_INTEREST,
        external_key=fetched_interest.slug,
        title=fetched_interest.title,
        interest_heading=fetched_interest.interest_heading,
        overview_bullets=list(fetched_interest.overview_bullets),
        canonical_url=fetched_interest.canonical_url,
        brand_kit_refs=fetched_interest.brand_kit_refs,
        raw_payload=fetched_interest.raw_payload,
    )
    our_database_session.add(created_source_item)
    our_database_session.flush()

    return created_source_item, True


def _apply_fetched_interest_fields(
    source_item: SourceItem,
    fetched_interest: SpotmuInterestFetch,
) -> None:
    """Copy mapped public fields onto an existing SourceItem."""

    source_item.title = fetched_interest.title
    source_item.interest_heading = fetched_interest.interest_heading
    source_item.overview_bullets = list(fetched_interest.overview_bullets)
    source_item.canonical_url = fetched_interest.canonical_url
    source_item.brand_kit_refs = fetched_interest.brand_kit_refs
    source_item.raw_payload = fetched_interest.raw_payload
