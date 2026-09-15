"""Idempotent Phase 1 seed: Spotmu brand + one fake example SourceItem.

Run from `apps/server` with `DATABASE_URL` set:

    python -m app.seed

Not real Spotmu ingest (that is 1.3). Re-running converges on the same
slug / external_key rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Query, Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import Brand, SourceItem
from app.models.enums import SourceType


SPOTMU_BRAND_SLUG: str = "spotmu"
SPOTMU_BRAND_NAME: str = "Spotmu"
EXAMPLE_SOURCE_EXTERNAL_KEY: str = "example"
EXAMPLE_SOURCE_TITLE: str = "Example Spotmu interest"
EXAMPLE_SOURCE_INTEREST_HEADING: str = "What this example lane is about"
EXAMPLE_SOURCE_OVERVIEW_BULLETS: list[str] = [
    "A placeholder interest heading for Twerva persist proof.",
    "Three overview bullets stand in for a real Spotmu interest.",
    "Replace this row when 1.3 ingest lands — do not treat it as live content.",
]
EXAMPLE_SOURCE_CANONICAL_URL: str = "https://spotmu.com/interest/example"


@dataclass(frozen=True)
class SeedResult:
    """Outcome of one idempotent seed run."""

    brand: Brand
    source_item: SourceItem
    created_brand: bool
    created_source_item: bool


def seed_spotmu_example(our_database_session: Session) -> SeedResult:
    """Insert or converge the Spotmu brand and example SourceItem.

    Args:
        our_database_session: Open SQLAlchemy session. This function commits.

    Returns:
        The Brand and SourceItem rows plus whether each was newly inserted.
    """

    brand: Brand
    created_brand: bool
    brand, created_brand = _get_or_create_spotmu_brand(our_database_session)

    source_item: SourceItem
    created_source_item: bool
    source_item, created_source_item = _get_or_create_example_source_item(
        brand,
        our_database_session,
    )
    our_database_session.commit()
    our_database_session.refresh(brand)
    our_database_session.refresh(source_item)

    seed_result: SeedResult = SeedResult(
        brand=brand,
        source_item=source_item,
        created_brand=created_brand,
        created_source_item=created_source_item,
    )

    return seed_result


def main() -> int:
    """Load settings/engine, seed, and print the resulting ids."""

    from app.db import SessionLocal

    our_database_session: Session = SessionLocal()

    try:
        seed_result: SeedResult = seed_spotmu_example(our_database_session)
    finally:
        our_database_session.close()

    brand_id: uuid.UUID = seed_result.brand.id
    source_item_id: uuid.UUID = seed_result.source_item.id
    brand_verb: str = "created" if seed_result.created_brand else "already present"
    source_item_verb: str = (
        "created" if seed_result.created_source_item else "already present"
    )
    print(
        f"Brand slug={SPOTMU_BRAND_SLUG} id={brand_id} ({brand_verb})",
    )
    print(
        f"SourceItem external_key={EXAMPLE_SOURCE_EXTERNAL_KEY} "
        f"id={source_item_id} ({source_item_verb})",
    )

    return 0


def _get_or_create_spotmu_brand(
    our_database_session: Session,
) -> tuple[Brand, bool]:
    """Return the Spotmu brand, inserting it when the slug is missing."""

    brand_query: Query[Brand] = our_database_session.query(Brand)
    slug_filter: ColumnElement[bool] = Brand.slug == SPOTMU_BRAND_SLUG
    filtered_brand_query: Query[Brand] = brand_query.filter(slug_filter)
    existing_brand: Brand | None = filtered_brand_query.one_or_none()

    if existing_brand is not None:

        if existing_brand.name != SPOTMU_BRAND_NAME:
            existing_brand.name = SPOTMU_BRAND_NAME

        return existing_brand, False

    created_brand: Brand = Brand(
        slug=SPOTMU_BRAND_SLUG,
        name=SPOTMU_BRAND_NAME,
    )
    our_database_session.add(created_brand)
    our_database_session.flush()

    return created_brand, True


def _get_or_create_example_source_item(
    brand: Brand,
    our_database_session: Session,
) -> tuple[SourceItem, bool]:
    """Return the fake example SourceItem, inserting it when missing."""

    source_item_query: Query[SourceItem] = our_database_session.query(SourceItem)
    brand_filter: ColumnElement[bool] = SourceItem.brand_id == brand.id
    type_filter: ColumnElement[bool] = SourceItem.source_type == SourceType.SPOTMU_INTEREST
    key_filter: ColumnElement[bool] = SourceItem.external_key == EXAMPLE_SOURCE_EXTERNAL_KEY
    filtered_source_item_query: Query[SourceItem] = source_item_query.filter(
        brand_filter,
        type_filter,
        key_filter,
    )
    existing_source_item: SourceItem | None = filtered_source_item_query.one_or_none()

    if existing_source_item is not None:
        _apply_example_source_item_fields(existing_source_item)

        return existing_source_item, False

    created_source_item: SourceItem = SourceItem(
        brand_id=brand.id,
        source_type=SourceType.SPOTMU_INTEREST,
        external_key=EXAMPLE_SOURCE_EXTERNAL_KEY,
        title=EXAMPLE_SOURCE_TITLE,
        interest_heading=EXAMPLE_SOURCE_INTEREST_HEADING,
        overview_bullets=list(EXAMPLE_SOURCE_OVERVIEW_BULLETS),
        canonical_url=EXAMPLE_SOURCE_CANONICAL_URL,
    )
    our_database_session.add(created_source_item)
    our_database_session.flush()

    return created_source_item, True


def _apply_example_source_item_fields(source_item: SourceItem) -> None:
    """Converge an existing example row onto the documented fake shape."""

    source_item.title = EXAMPLE_SOURCE_TITLE
    source_item.interest_heading = EXAMPLE_SOURCE_INTEREST_HEADING
    source_item.overview_bullets = list(EXAMPLE_SOURCE_OVERVIEW_BULLETS)
    source_item.canonical_url = EXAMPLE_SOURCE_CANONICAL_URL


if __name__ == "__main__":
    raise SystemExit(main())
