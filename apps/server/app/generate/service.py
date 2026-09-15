"""Persist a new carousel Artifact draft from a SourceItem (1.4d).

Each generate inserts a new row (history kept). This module does not
replace an existing draft.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.generate.carousel import (
    CarouselRenderResult,
    CarouselSourceFields,
    carousel_source_fields_from_values,
    render_carousel_from_source_fields,
)
from app.generate.errors import (
    CarouselClusterBrandMismatchError,
    CarouselClusterMissingError,
    CarouselSourceItemMissingError,
)
from app.models import Artifact, Cluster, SourceItem
from app.models.enums import ArtifactStatus
from app.storage.artifacts import resolve_configured_artifact_storage_directory


CAROUSEL_FORMAT: str = "carousel"


def generate_carousel_artifact_draft(
    source_item_id: uuid.UUID,
    our_database_session: Session,
    cluster_id: uuid.UUID | None = None,
    artifact_storage_directory: Path | None = None,
) -> Artifact:
    """Render slides and add a new `draft` Artifact (not committed).

    Args:
        source_item_id: Required SourceItem primary key.
        our_database_session: Open SQLAlchemy session.
        cluster_id: Optional Cluster to stamp on the Artifact.
        artifact_storage_directory: Override `ARTIFACT_STORAGE_DIR`.

    Returns:
        The flushed Artifact row (`status=draft`, `format=carousel`).

    Raises:
        CarouselSourceItemMissingError: Unknown source item.
        CarouselClusterMissingError: Unknown cluster.
        CarouselClusterBrandMismatchError: Cluster is a different brand.
    """

    source_item: SourceItem = _fetch_source_item_or_raise(
        source_item_id,
        our_database_session,
    )
    resolved_cluster_id: uuid.UUID | None = _resolve_cluster_id_or_raise(
        cluster_id,
        source_item,
        our_database_session,
    )
    resolved_storage_directory: Path

    if artifact_storage_directory is None:
        resolved_storage_directory = resolve_configured_artifact_storage_directory()
    else:
        resolved_storage_directory = artifact_storage_directory

    artifact_identifier: uuid.UUID = uuid.uuid4()
    source_fields: CarouselSourceFields = carousel_source_fields_from_values(
        source_item.title,
        source_item.interest_heading,
        source_item.overview_bullets,
        source_item.canonical_url,
        source_item.external_key,
    )
    render_result: CarouselRenderResult = render_carousel_from_source_fields(
        source_fields,
        artifact_identifier,
        resolved_storage_directory,
    )
    serialized_slides: list[dict[str, str]] = [
        {
            "role": rendered_slide.role,
            "text": rendered_slide.text,
            "asset_ref": rendered_slide.asset_ref,
        }
        for rendered_slide in render_result.slides
    ]
    created_artifact: Artifact = Artifact(
        id=artifact_identifier,
        brand_id=source_item.brand_id,
        source_item_id=source_item.id,
        cluster_id=resolved_cluster_id,
        status=ArtifactStatus.DRAFT,
        format=CAROUSEL_FORMAT,
        caption=render_result.caption,
        cta_url=render_result.cta_url,
        slides=serialized_slides,
    )
    our_database_session.add(created_artifact)
    our_database_session.flush()

    return created_artifact


def _fetch_source_item_or_raise(
    source_item_id: uuid.UUID,
    our_database_session: Session,
) -> SourceItem:
    """Load the SourceItem or raise a domain missing error."""

    found_source_item: SourceItem | None = our_database_session.get(
        SourceItem,
        source_item_id,
    )

    if found_source_item is None:
        raise CarouselSourceItemMissingError(source_item_id)

    return found_source_item


def _resolve_cluster_id_or_raise(
    cluster_id: uuid.UUID | None,
    source_item: SourceItem,
    our_database_session: Session,
) -> uuid.UUID | None:
    """Validate an optional cluster against the source item brand."""

    if cluster_id is None:

        return None

    found_cluster: Cluster | None = our_database_session.get(Cluster, cluster_id)

    if found_cluster is None:
        raise CarouselClusterMissingError(cluster_id)

    if found_cluster.brand_id != source_item.brand_id:
        raise CarouselClusterBrandMismatchError(cluster_id, source_item.id)

    return found_cluster.id
