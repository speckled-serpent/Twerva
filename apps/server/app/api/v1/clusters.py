"""Cluster create/list/get plus manual source-item attach/detach (1.3e)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.api.v1.lookups import (
    fetch_brand_by_id_or_raise,
    fetch_cluster_by_id_or_raise,
    fetch_source_item_by_id_or_raise,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import ClusterCreateRequest, ClusterReadResponse
from app.db import get_our_database_session
from app.models import Cluster, SourceItem


clusters_router: APIRouter = APIRouter(prefix="/clusters", tags=["clusters"])


@clusters_router.post(
    "",
    response_model=ClusterReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cluster(
    cluster_create_request: ClusterCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> ClusterReadResponse:
    """Persist a Cluster under an existing Brand."""

    fetch_brand_by_id_or_raise(
        cluster_create_request.brand_id,
        our_database_session,
    )
    created_cluster: Cluster = Cluster(
        brand_id=cluster_create_request.brand_id,
        slug=cluster_create_request.slug,
        name=cluster_create_request.name,
        description=cluster_create_request.description,
        is_active=cluster_create_request.is_active,
    )
    our_database_session.add(created_cluster)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Cluster slug already exists for this brand.",
    )
    our_database_session.refresh(created_cluster)
    cluster_read_response: ClusterReadResponse = build_cluster_read_response(
        created_cluster,
    )

    return cluster_read_response


@clusters_router.get("", response_model=list[ClusterReadResponse])
def list_clusters(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[ClusterReadResponse]:
    """Return every Cluster, newest first, with linked source item ids."""

    cluster_selection: Select[tuple[Cluster]] = select(Cluster)
    cluster_selection_with_source_items: Select[tuple[Cluster]] = (
        cluster_selection.options(selectinload(Cluster.source_items))
    )
    ordered_cluster_selection: Select[tuple[Cluster]] = (
        cluster_selection_with_source_items.order_by(Cluster.created_at.desc())
    )
    cluster_scalars = our_database_session.scalars(ordered_cluster_selection)
    clusters: list[Cluster] = list(cluster_scalars.all())
    cluster_read_responses: list[ClusterReadResponse] = [
        build_cluster_read_response(cluster) for cluster in clusters
    ]

    return cluster_read_responses


@clusters_router.get("/{cluster_id}", response_model=ClusterReadResponse)
def get_cluster_by_id(
    cluster_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ClusterReadResponse:
    """Return one Cluster by primary key, including linked source item ids."""

    found_cluster: Cluster = fetch_cluster_by_id_or_raise(
        cluster_id,
        our_database_session,
    )
    cluster_read_response: ClusterReadResponse = build_cluster_read_response(
        found_cluster,
    )

    return cluster_read_response


@clusters_router.post(
    "/{cluster_id}/source-items/{source_item_id}",
    response_model=ClusterReadResponse,
)
def attach_source_item_to_cluster(
    cluster_id: uuid.UUID,
    source_item_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ClusterReadResponse:
    """Attach a SourceItem to a Cluster via ``cluster_source_items``.

    Idempotent when the pair already exists. Both rows must share a brand.
    """

    found_cluster: Cluster = fetch_cluster_by_id_or_raise(
        cluster_id,
        our_database_session,
    )
    found_source_item: SourceItem = fetch_source_item_by_id_or_raise(
        source_item_id,
        our_database_session,
    )

    if found_cluster.brand_id != found_source_item.brand_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cluster and SourceItem belong to different brands; "
                "refusing the attach."
            ),
        )

    linked_source_items: list[SourceItem] = list(found_cluster.source_items)
    already_linked: bool = any(
        linked_source_item.id == found_source_item.id
        for linked_source_item in linked_source_items
    )

    if not already_linked:
        found_cluster.source_items.append(found_source_item)
        our_database_session.commit()
        our_database_session.refresh(found_cluster)

    cluster_read_response: ClusterReadResponse = build_cluster_read_response(
        found_cluster,
    )

    return cluster_read_response


@clusters_router.delete(
    "/{cluster_id}/source-items/{source_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_source_item_from_cluster(
    cluster_id: uuid.UUID,
    source_item_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> None:
    """Detach a SourceItem from a Cluster. 404 if the pair is not linked."""

    found_cluster: Cluster = fetch_cluster_by_id_or_raise(
        cluster_id,
        our_database_session,
    )
    found_source_item: SourceItem = fetch_source_item_by_id_or_raise(
        source_item_id,
        our_database_session,
    )
    linked_source_items: list[SourceItem] = list(found_cluster.source_items)
    matching_source_item: SourceItem | None = None

    for linked_source_item in linked_source_items:

        if linked_source_item.id == found_source_item.id:
            matching_source_item = linked_source_item
            break

    if matching_source_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"SourceItem {source_item_id} is not attached to "
                f"cluster {cluster_id}."
            ),
        )

    found_cluster.source_items.remove(matching_source_item)
    our_database_session.commit()


def build_cluster_read_response(cluster: Cluster) -> ClusterReadResponse:
    """Serialize a Cluster including linked source item ids.

    Args:
        cluster: Loaded Cluster row. ``source_items`` may lazy-load.

    Returns:
        Cluster read schema with ``source_item_ids``.
    """

    linked_source_items: list[SourceItem] = list(cluster.source_items)
    source_item_ids: list[uuid.UUID] = [
        linked_source_item.id for linked_source_item in linked_source_items
    ]
    cluster_read_response: ClusterReadResponse = ClusterReadResponse(
        id=cluster.id,
        brand_id=cluster.brand_id,
        slug=cluster.slug,
        name=cluster.name,
        description=cluster.description,
        is_active=cluster.is_active,
        source_item_ids=source_item_ids,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
    )

    return cluster_read_response
