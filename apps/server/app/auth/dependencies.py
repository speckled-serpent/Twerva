"""FastAPI dependency that requires a valid ops session cookie."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.sessions import InvalidOpsSessionError, read_ops_user_id_from_session_token
from app.db import get_our_database_session
from app.models import OpsUser
from app.settings import Settings, get_settings


UNAUTHENTICATED_DETAIL: str = "Not authenticated."


def require_authenticated_ops_operator(
    request: Request,
    our_database_session: Session = Depends(get_our_database_session),
) -> OpsUser:
    """Return the signed-in ops operator, or raise HTTP 401.

    Args:
        request: Incoming request (session cookie).
        our_database_session: Request-scoped SQLAlchemy session.

    Returns:
        The `OpsUser` row for the signed cookie.

    Raises:
        HTTPException: 401 when the cookie is missing, invalid, or the user is gone.
    """

    settings: Settings = get_settings()
    session_cookie_value: str | None = request.cookies.get(settings.session_cookie_name)

    if session_cookie_value is None or session_cookie_value.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHENTICATED_DETAIL,
        )

    try:
        ops_user_id: uuid.UUID = read_ops_user_id_from_session_token(
            session_cookie_value,
            settings,
        )
    except InvalidOpsSessionError as invalid_session_error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHENTICATED_DETAIL,
        ) from invalid_session_error

    found_ops_user: OpsUser | None = our_database_session.get(OpsUser, ops_user_id)

    if found_ops_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHENTICATED_DETAIL,
        )

    return found_ops_user
