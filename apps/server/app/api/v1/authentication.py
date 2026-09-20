"""Public ops login, logout, and current-user routes."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.schemas import OpsLoginRequest, OpsLogoutResponse, OpsUserReadResponse
from app.auth.dependencies import require_authenticated_ops_operator
from app.auth.passwords import hash_plain_password, plain_password_matches_hash
from app.auth.sessions import issue_ops_session_token
from app.db import get_our_database_session
from app.models import OpsUser
from app.settings import Settings, get_settings


LOGIN_FAILED_DETAIL: str = "Invalid username or password."
LOGOUT_STATUS: str = "logged_out"
UNUSED_PASSWORD_HASH: str = hash_plain_password("unused-placeholder-password")

authentication_router: APIRouter = APIRouter(prefix="/auth", tags=["auth"])


@authentication_router.post("/login", response_model=OpsUserReadResponse)
def login_ops_operator(
    ops_login_request: OpsLoginRequest,
    response: Response,
    our_database_session: Session = Depends(get_our_database_session),
) -> OpsUserReadResponse:
    """Verify username/password, set the session cookie, and return the operator."""

    settings: Settings = get_settings()
    submitted_username: str = ops_login_request.username.strip()
    submitted_password: str = ops_login_request.password
    found_ops_user: OpsUser | None = _fetch_ops_user_by_username(
        submitted_username,
        our_database_session,
    )
    password_hash_to_check: str = (
        found_ops_user.password_hash if found_ops_user is not None else UNUSED_PASSWORD_HASH
    )
    password_accepted: bool = plain_password_matches_hash(
        submitted_password,
        password_hash_to_check,
    )

    if found_ops_user is None or not password_accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOGIN_FAILED_DETAIL,
        )

    session_token: str = issue_ops_session_token(found_ops_user.id, settings)
    _set_ops_session_cookie(response, session_token, settings)
    ops_user_read_response: OpsUserReadResponse = OpsUserReadResponse.model_validate(
        found_ops_user,
    )

    return ops_user_read_response


@authentication_router.post("/logout", response_model=OpsLogoutResponse)
def logout_ops_operator(response: Response) -> OpsLogoutResponse:
    """Clear the session cookie. Always succeeds."""

    settings: Settings = get_settings()
    _clear_ops_session_cookie(response, settings)
    logout_response: OpsLogoutResponse = OpsLogoutResponse(status=LOGOUT_STATUS)

    return logout_response


@authentication_router.get("/me", response_model=OpsUserReadResponse)
def get_current_ops_operator(
    current_ops_operator: OpsUser = Depends(require_authenticated_ops_operator),
) -> OpsUserReadResponse:
    """Return the signed-in ops operator, or 401 when the cookie is invalid."""

    ops_user_read_response: OpsUserReadResponse = OpsUserReadResponse.model_validate(
        current_ops_operator,
    )

    return ops_user_read_response


def _fetch_ops_user_by_username(
    username: str,
    our_database_session: Session,
) -> OpsUser | None:
    """Return the ops user with this username, or None."""

    if username == "":

        return None

    ops_user_selection = select(OpsUser).where(OpsUser.username == username)
    ops_user_scalar = our_database_session.scalars(ops_user_selection)
    found_ops_user: OpsUser | None = ops_user_scalar.first()

    return found_ops_user


def _set_ops_session_cookie(
    response: Response,
    session_token: str,
    settings: Settings,
) -> None:
    """Attach the signed session cookie with locked flags."""

    cookie_samesite: Literal["lax", "strict", "none"] = _cookie_samesite_literal(
        settings.session_cookie_samesite,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=cookie_samesite,
        path="/",
    )


def _clear_ops_session_cookie(response: Response, settings: Settings) -> None:
    """Expire the session cookie using the same flags as login."""

    cookie_samesite: Literal["lax", "strict", "none"] = _cookie_samesite_literal(
        settings.session_cookie_samesite,
    )
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=cookie_samesite,
        path="/",
    )


def _cookie_samesite_literal(
    session_cookie_samesite: str,
) -> Literal["lax", "strict", "none"]:
    """Coerce the setting to a Starlette SameSite literal."""

    if session_cookie_samesite == "strict":

        return "strict"

    if session_cookie_samesite == "none":

        return "none"

    return "lax"
