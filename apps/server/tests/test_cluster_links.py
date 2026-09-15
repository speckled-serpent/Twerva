"""Cluster read includes linked source item ids (1.3e-ii)."""

import unittest
import uuid
from datetime import datetime, timezone

from app.api.v1.clusters import build_cluster_read_response
from app.models import Cluster, SourceItem
from app.models.enums import SourceType


FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FIXED_CLUSTER_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FIXED_SOURCE_ITEM_ID: uuid.UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
FIXED_TIMESTAMP: datetime = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


class _LinkedSourceCollection(list[SourceItem]):
    """List stand-in so an unbound Cluster can expose ``source_items``."""


class ClusterLinkSchemaTests(unittest.TestCase):
    """1.3e: GET/list cluster payloads carry linked source item ids."""

    def test_build_cluster_read_response_includes_source_item_ids(self) -> None:
        """Linked ids are listed; empty collection serializes as []."""

        cluster: Cluster = Cluster(
            brand_id=FIXED_BRAND_ID,
            slug="spotmu-general",
            name="Spotmu general",
            description=None,
            is_active=True,
        )
        cluster.id = FIXED_CLUSTER_ID
        cluster.created_at = FIXED_TIMESTAMP
        cluster.updated_at = FIXED_TIMESTAMP
        cluster.source_items = _LinkedSourceCollection()
        empty_response = build_cluster_read_response(cluster)

        self.assertEqual(empty_response.source_item_ids, [])
        self.assertEqual(empty_response.slug, "spotmu-general")

        source_item: SourceItem = SourceItem(
            brand_id=FIXED_BRAND_ID,
            source_type=SourceType.SPOTMU_INTEREST,
            external_key="ai-agents",
            title="AI Agents",
            overview_bullets=["one"],
        )
        source_item.id = FIXED_SOURCE_ITEM_ID
        cluster.source_items.append(source_item)
        linked_response = build_cluster_read_response(cluster)

        self.assertEqual(linked_response.source_item_ids, [FIXED_SOURCE_ITEM_ID])


if __name__ == "__main__":
    unittest.main()
