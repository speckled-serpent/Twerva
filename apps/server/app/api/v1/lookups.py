"""Fetch-or-404 helpers for persist-proof routes."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Account, Artifact, Brand, Cluster, PostJob, SourceItem


def fetch_brand_by_id_or_raise(
    brand_id: uuid.UUID,
    our_database_session: Session,
) -> Brand:
    """Return a Brand or raise HTTP 404.

    Args:
        brand_id: Primary key to load.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The matching Brand row.

    Raises:
        HTTPException: If no Brand exists for `brand_id`.
    """

    found_brand: Brand | None = our_database_session.get(Brand, brand_id)

    if found_brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand not found: {brand_id}",
        )

    return found_brand


def fetch_source_item_by_id_or_raise(
    source_item_id: uuid.UUID,
    our_database_session: Session,
) -> SourceItem:
    """Return a SourceItem or raise HTTP 404.

    Args:
        source_item_id: Primary key to load.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The matching SourceItem row.

    Raises:
        HTTPException: If no SourceItem exists for `source_item_id`.
    """

    found_source_item: SourceItem | None = our_database_session.get(
        SourceItem,
        source_item_id,
    )

    if found_source_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SourceItem not found: {source_item_id}",
        )

    return found_source_item


def fetch_cluster_by_id_or_raise(
    cluster_id: uuid.UUID,
    our_database_session: Session,
) -> Cluster:
    """Return a Cluster or raise HTTP 404.

    Args:
        cluster_id: Primary key to load.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The matching Cluster row.

    Raises:
        HTTPException: If no Cluster exists for `cluster_id`.
    """

    found_cluster: Cluster | None = our_database_session.get(Cluster, cluster_id)

    if found_cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster not found: {cluster_id}",
        )

    return found_cluster


def fetch_account_by_id_or_raise(
    account_id: uuid.UUID,
    our_database_session: Session,
) -> Account:
    """Return an Account or raise HTTP 404.

    Args:
        account_id: Primary key to load.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The matching Account row.

    Raises:
        HTTPException: If no Account exists for `account_id`.
    """

    found_account: Account | None = our_database_session.get(Account, account_id)

    if found_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account not found: {account_id}",
        )

    return found_account


def fetch_artifact_by_id_or_raise(
    artifact_id: uuid.UUID,
    our_database_session: Session,
) -> Artifact:
    """Return an Artifact or raise HTTP 404.

    Args:
        artifact_id: Primary key to load.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The matching Artifact row.

    Raises:
        HTTPException: If no Artifact exists for `artifact_id`.
    """

    found_artifact: Artifact | None = our_database_session.get(Artifact, artifact_id)

    if found_artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact not found: {artifact_id}",
        )

    return found_artifact


def fetch_post_job_by_id_or_raise(
    post_job_id: uuid.UUID,
    our_database_session: Session,
) -> PostJob:
    """Return a PostJob or raise HTTP 404.

    Args:
        post_job_id: Primary key to load.
        our_database_session: Open SQLAlchemy session.

    Returns:
        The matching PostJob row.

    Raises:
        HTTPException: If no PostJob exists for `post_job_id`.
    """

    found_post_job: PostJob | None = our_database_session.get(PostJob, post_job_id)

    if found_post_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PostJob not found: {post_job_id}",
        )

    return found_post_job
