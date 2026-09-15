"""Domain errors for carousel generate (mapped to HTTP in the API)."""

from __future__ import annotations

import uuid


class CarouselGenerateError(Exception):
    """Base error for carousel generate."""


class CarouselSourceItemMissingError(CarouselGenerateError):
    """No SourceItem exists for the requested id."""

    def __init__(self, source_item_id: uuid.UUID) -> None:

        super().__init__(f"SourceItem not found: {source_item_id}")
        self.source_item_id: uuid.UUID = source_item_id


class CarouselClusterMissingError(CarouselGenerateError):
    """No Cluster exists for the requested id."""

    def __init__(self, cluster_id: uuid.UUID) -> None:

        super().__init__(f"Cluster not found: {cluster_id}")
        self.cluster_id: uuid.UUID = cluster_id


class CarouselClusterBrandMismatchError(CarouselGenerateError):
    """Cluster and SourceItem belong to different brands."""

    def __init__(self, cluster_id: uuid.UUID, source_item_id: uuid.UUID) -> None:

        super().__init__(
            f"Cluster {cluster_id} brand does not match SourceItem {source_item_id}.",
        )
        self.cluster_id: uuid.UUID = cluster_id
        self.source_item_id: uuid.UUID = source_item_id
