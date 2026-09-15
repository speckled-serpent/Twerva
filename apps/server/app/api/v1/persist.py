"""Shared commit helper for persist-proof writes."""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def commit_database_session_or_raise_conflict(
    our_database_session: Session,
    conflict_detail: str,
) -> None:
    """Commit the session, mapping uniqueness/FK failures to HTTP 409.

    Args:
        our_database_session: Session with pending writes.
        conflict_detail: Message returned when Postgres rejects the write.

    Raises:
        HTTPException: On `IntegrityError` after rollback.
    """

    try:
        our_database_session.commit()
    except IntegrityError as integrity_error:
        our_database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_detail,
        ) from integrity_error
