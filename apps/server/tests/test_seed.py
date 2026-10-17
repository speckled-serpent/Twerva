"""Idempotent Spotmu seed without opening Postgres."""

import unittest
import uuid
from datetime import datetime, timezone

from app.models import Brand, SourceItem
from app.models.enums import SourceType
from app.seed import (
    EXAMPLE_SOURCE_CANONICAL_URL,
    EXAMPLE_SOURCE_EXTERNAL_KEY,
    EXAMPLE_SOURCE_INTEREST_HEADING,
    EXAMPLE_SOURCE_OVERVIEW_BULLETS,
    EXAMPLE_SOURCE_TITLE,
    SPOTMU_BRAND_NAME,
    SPOTMU_BRAND_SLUG,
    seed_spotmu_example,
)


class _FilterableQuery:
    """Minimal query stand-in for `session.query(...).filter(...).one_or_none()`."""

    def __init__(self, result: object | None) -> None:

        self._result: object | None = result

    def filter(self, *arguments: object) -> "_FilterableQuery":

        return self

    def one_or_none(self) -> object | None:

        return self._result


class _FakeSeedSession:
    """In-memory session used to prove seed insert vs converge."""

    def __init__(
        self,
        existing_brand: Brand | None = None,
        existing_source_item: SourceItem | None = None,
    ) -> None:

        self.existing_brand: Brand | None = existing_brand
        self.existing_source_item: SourceItem | None = existing_source_item
        self.added_rows: list[object] = []
        self.commit_count: int = 0
        self.flush_count: int = 0

    def query(self, model_class: type[object]) -> _FilterableQuery:

        if model_class is Brand:

            return _FilterableQuery(self.existing_brand)

        if model_class is SourceItem:

            return _FilterableQuery(self.existing_source_item)

        return _FilterableQuery(None)

    def add(self, row: object) -> None:

        self.added_rows.append(row)

        if isinstance(row, Brand):
            self.existing_brand = row

        if isinstance(row, SourceItem):
            self.existing_source_item = row

    def flush(self) -> None:

        self.flush_count += 1
        _assign_row_defaults(self.added_rows[-1])

    def commit(self) -> None:

        self.commit_count += 1

    def refresh(self, row: object) -> None:

        _assign_row_defaults(row)


class SeedIdempotencyTests(unittest.TestCase):
    """1.2m: Brand `spotmu` + one fake example SourceItem."""

    def test_seed_inserts_spotmu_brand_and_example_source_item(self) -> None:
        """First run creates both rows with the documented fake shape."""

        fake_session: _FakeSeedSession = _FakeSeedSession()
        seed_result = seed_spotmu_example(fake_session)

        self.assertTrue(seed_result.created_brand)
        self.assertTrue(seed_result.created_source_item)
        self.assertEqual(seed_result.brand.slug, SPOTMU_BRAND_SLUG)
        self.assertEqual(seed_result.brand.name, SPOTMU_BRAND_NAME)
        self.assertEqual(seed_result.source_item.title, EXAMPLE_SOURCE_TITLE)
        self.assertEqual(
            seed_result.source_item.interest_heading,
            EXAMPLE_SOURCE_INTEREST_HEADING,
        )
        self.assertEqual(
            seed_result.source_item.overview_bullets,
            EXAMPLE_SOURCE_OVERVIEW_BULLETS,
        )
        self.assertEqual(
            seed_result.source_item.canonical_url,
            EXAMPLE_SOURCE_CANONICAL_URL,
        )
        self.assertEqual(
            seed_result.source_item.external_key,
            EXAMPLE_SOURCE_EXTERNAL_KEY,
        )
        self.assertEqual(
            seed_result.source_item.source_type,
            SourceType.SPOTMU_INTEREST,
        )
        self.assertEqual(fake_session.commit_count, 1)

    def test_seed_is_idempotent_when_rows_already_exist(self) -> None:
        """Second run does not insert; it converges name and carousel fields."""

        existing_brand: Brand = Brand(slug=SPOTMU_BRAND_SLUG, name="Old name")
        existing_brand.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        existing_source_item: SourceItem = SourceItem(
            brand_id=existing_brand.id,
            source_type=SourceType.SPOTMU_INTEREST,
            external_key=EXAMPLE_SOURCE_EXTERNAL_KEY,
            title="stale",
            interest_heading="stale",
            overview_bullets=["old"],
            canonical_url="https://example.invalid/old",
        )
        existing_source_item.id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        fake_session: _FakeSeedSession = _FakeSeedSession(
            existing_brand=existing_brand,
            existing_source_item=existing_source_item,
        )
        seed_result = seed_spotmu_example(fake_session)

        self.assertFalse(seed_result.created_brand)
        self.assertFalse(seed_result.created_source_item)
        self.assertEqual(seed_result.brand.name, SPOTMU_BRAND_NAME)
        self.assertEqual(seed_result.source_item.title, EXAMPLE_SOURCE_TITLE)
        self.assertEqual(len(fake_session.added_rows), 0)
        self.assertEqual(fake_session.commit_count, 1)


def _assign_row_defaults(row: object) -> None:
    """Fill server-default fields the fake session cannot emit."""

    now_timestamp: datetime = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()

    if getattr(row, "created_at", None) is None:
        row.created_at = now_timestamp

    if getattr(row, "updated_at", None) is None:
        row.updated_at = now_timestamp


if __name__ == "__main__":
    unittest.main()
