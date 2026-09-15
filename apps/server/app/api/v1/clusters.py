"""Cluster create/list/get routes."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_brand_by_id_or_raise, fetch_cluster_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import ClusterCreateRequest, ClusterReadResponse
from app.db import get_our_database_session
from app.models import Cluster


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

    cluster_read_response: ClusterReadResponse = ClusterReadResponse.model_validate(
        created_cluster,
    )

    return cluster_read_response


@clusters_router.get("", response_model=list[ClusterReadResponse])
def list_clusters(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[ClusterReadResponse]:
    """Return every Cluster, newest first."""

    cluster_selection = select(Cluster).order_by(Cluster.created_at.desc())
    cluster_scalars = our_database_session.scalars(cluster_selection)
    clusters: list[Cluster] = list(cluster_scalars.all())
    cluster_read_responses: list[ClusterReadResponse] = [
        ClusterReadResponse.model_validate(cluster) for cluster in clusters
    ]

    return cluster_read_responses


@clusters_router.get("/{cluster_id}", response_model=ClusterReadResponse)
def get_cluster_by_id(
    cluster_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ClusterReadResponse:
    """Return one Cluster by primary key."""

    found_cluster: Cluster = fetch_cluster_by_id_or_raise(
        cluster_id,
        our_database_session,
    )
    cluster_read_response: ClusterReadResponse = ClusterReadResponse.model_validate(
        found_cluster,
    )

    return cluster_read_response
