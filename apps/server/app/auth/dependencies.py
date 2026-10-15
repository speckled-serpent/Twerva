"""FastAPI dependencies for ops session cookies and basic RBAC."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.sessions import InvalidOpsSessionError, read_ops_user_id_from_session_token
from app.db import get_our_database_session
from app.models import OpsUser, OpsUserRole
from app.settings import Settings, get_settings


UNAUTHENTICATED_DETAIL: str = "Not authenticated."
ADMIN_ROLE_REQUIRED_DETAIL: str = "Admin role required."
READER_WRITE_DENIED_DETAIL: str = (
    "Reader accounts are read-only. Ask an admin to perform this change."
)
READER_SAFE_HTTP_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})
READER_ALLOWED_MUTATION_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
        "/api/v1/themes/preview",
    },
)


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


def require_admin_ops_operator(
    current_ops_operator: OpsUser = Depends(require_authenticated_ops_operator),
) -> OpsUser:
    """Return the signed-in admin, or raise HTTP 403 for readers.

    Args:
        current_ops_operator: Authenticated ops operator from the session cookie.

    Returns:
        The same operator when `role` is `admin`.

    Raises:
        HTTPException: 403 when the operator is not an admin.
    """

    if current_ops_operator.role != OpsUserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ADMIN_ROLE_REQUIRED_DETAIL,
        )

    return current_ops_operator


def require_ops_operator_allowed_for_request(
    request: Request,
    current_ops_operator: OpsUser = Depends(require_authenticated_ops_operator),
) -> OpsUser:
    """Allow admins fully; readers may GET (and a few self-service POSTs).

    Args:
        request: Incoming request (method + path).
        current_ops_operator: Authenticated ops operator.

    Returns:
        The operator when the method is permitted for their role.

    Raises:
        HTTPException: 403 when a reader attempts a denied mutation.
    """

    if ops_operator_may_perform_request(current_ops_operator, request):

        return current_ops_operator

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=READER_WRITE_DENIED_DETAIL,
    )


def ops_operator_may_perform_request(ops_operator: OpsUser, request: Request,
) -> bool:
    """Return True when this operator may perform the HTTP method/path.

    Args:
        ops_operator: Signed-in `ops_users` row.
        request: Incoming request.

    Returns:
        True for admins, safe reader methods, and allowed reader mutations.
    """

    if ops_operator.role == OpsUserRole.ADMIN:

        return True

    request_method: str = request.method.upper()

    if request_method in READER_SAFE_HTTP_METHODS:

        return True

    request_path: str = request.url.path

    if request_method == "POST" and request_path in READER_ALLOWED_MUTATION_PATHS:

        return True

    if request_method == "POST" and _is_unit_preview_path(request_path):

        return True

    return False


def _is_unit_preview_path(request_path: str) -> bool:
    """True for the in-source unit preview. It writes nothing."""

    path_parts: list[str] = [part for part in request_path.split("/") if part != ""]

    if len(path_parts) != 6:

        return False

    is_preview: bool = (
        path_parts[0] == "api"
        and path_parts[1] == "v1"
        and path_parts[2] == "sources"
        and path_parts[4] == "units"
        and path_parts[5] == "preview"
    )

    return is_preview
