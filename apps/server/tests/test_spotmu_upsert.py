"""Idempotent Spotmu interest upsert without opening Postgres (1.3c-iv)."""

import unittest
import uuid
from datetime import datetime, timezone

from app.ingest.spotmu import SpotmuInterestFetch
from app.ingest.upsert import upsert_spotmu_interest_source_item
from app.models import Brand, SourceItem
from app.models.enums import SourceType
from app.seed import SPOTMU_BRAND_NAME, SPOTMU_BRAND_SLUG


FIRST_FETCH: SpotmuInterestFetch = SpotmuInterestFetch(
    slug="ai-agents",
    title="AI Agents",
    interest_heading="First heading",
    overview_bullets=["one", "two"],
    canonical_url="https://spotmu.com/interest/ai-agents",
    brand_kit_refs=None,
    raw_payload={"slug": "ai-agents", "title": "AI Agents", "pass": 1},
)
UPDATED_FETCH: SpotmuInterestFetch = SpotmuInterestFetch(
    slug="ai-agents",
    title="AI Agents (updated)",
    interest_heading="Second heading",
    overview_bullets=["one", "two", "three"],
    canonical_url="https://spotmu.com/interest/ai-agents",
    brand_kit_refs=None,
    raw_payload={"slug": "ai-agents", "title": "AI Agents (updated)", "pass": 2},
)


class _FilterableQuery:
    """Minimal query stand-in for `session.query(...).filter(...).one_or_none()`."""

    def __init__(self, result: object | None) -> None:

        self._result: object | None = result

    def filter(self, *arguments: object) -> "_FilterableQuery":

        return self

    def one_or_none(self) -> object | None:

        return self._result


class _FakeUpsertSession:
    """In-memory session used to prove insert vs same-id update."""

    def __init__(
        self,
        existing_brand: Brand | None = None,
        existing_source_item: SourceItem | None = None,
    ) -> None:

        self.existing_brand: Brand | None = existing_brand
        self.existing_source_item: SourceItem | None = existing_source_item
        self.added_rows: list[object] = []
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
        _assign_row_defaults(self.added_rows[-1] if self.added_rows else None)


class SpotmuUpsertIdempotencyTests(unittest.TestCase):
    """Second pull updates fields and keeps the same SourceItem id."""

    def test_upsert_inserts_spotmu_brand_and_source_item(self) -> None:
        """First pull creates Brand spotmu and the interest row."""

        fake_session: _FakeUpsertSession = _FakeUpsertSession()
        upsert_result = upsert_spotmu_interest_source_item(
            FIRST_FETCH,
            fake_session,  # type: ignore[arg-type]
        )

        self.assertTrue(upsert_result.created)
        self.assertEqual(upsert_result.brand.slug, SPOTMU_BRAND_SLUG)
        self.assertEqual(upsert_result.brand.name, SPOTMU_BRAND_NAME)
        self.assertEqual(upsert_result.source_item.external_key, "ai-agents")
        self.assertEqual(
            upsert_result.source_item.source_type,
            SourceType.SPOTMU_INTEREST,
        )
        self.assertEqual(upsert_result.source_item.title, "AI Agents")
        self.assertEqual(upsert_result.source_item.overview_bullets, ["one", "two"])
        self.assertEqual(upsert_result.source_item.raw_payload["pass"], 1)

    def test_second_upsert_updates_fields_and_keeps_the_same_id(self) -> None:
        """Re-pull converges title/heading/bullets/raw_payload; id is stable."""

        existing_brand: Brand = Brand(slug=SPOTMU_BRAND_SLUG, name=SPOTMU_BRAND_NAME)
        existing_brand.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        existing_source_item: SourceItem = SourceItem(
            brand_id=existing_brand.id,
            source_type=SourceType.SPOTMU_INTEREST,
            external_key="ai-agents",
            title="stale",
            interest_heading="stale",
            overview_bullets=["old"],
            canonical_url="https://example.invalid/old",
            raw_payload={"pass": 0},
        )
        existing_source_item.id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        fake_session: _FakeUpsertSession = _FakeUpsertSession(
            existing_brand=existing_brand,
            existing_source_item=existing_source_item,
        )
        first_result = upsert_spotmu_interest_source_item(
            FIRST_FETCH,
            fake_session,  # type: ignore[arg-type]
        )
        second_result = upsert_spotmu_interest_source_item(
            UPDATED_FETCH,
            fake_session,  # type: ignore[arg-type]
        )

        self.assertFalse(first_result.created)
        self.assertFalse(second_result.created)
        self.assertEqual(first_result.source_item.id, existing_source_item.id)
        self.assertEqual(second_result.source_item.id, existing_source_item.id)
        self.assertEqual(second_result.source_item.title, "AI Agents (updated)")
        self.assertEqual(second_result.source_item.interest_heading, "Second heading")
        self.assertEqual(
            second_result.source_item.overview_bullets,
            ["one", "two", "three"],
        )
        self.assertEqual(second_result.source_item.raw_payload["pass"], 2)
        self.assertEqual(len(fake_session.added_rows), 0)


def _assign_row_defaults(row: object | None) -> None:
    """Fill server-default fields the fake session cannot emit."""

    if row is None:

        return

    now_timestamp: datetime = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()

    if getattr(row, "created_at", None) is None:
        row.created_at = now_timestamp

    if getattr(row, "updated_at", None) is None:
        row.updated_at = now_timestamp


if __name__ == "__main__":
    unittest.main()
