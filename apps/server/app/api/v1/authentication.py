"""Public ops login, logout, current-user, password, and user-admin routes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    OpsChangePasswordRequest,
    OpsChangePasswordResponse,
    OpsLoginRequest,
    OpsLogoutResponse,
    OpsUserCreateRequest,
    OpsUserReadResponse,
    OpsUserResetPasswordRequest,
    OpsUserRolePatchRequest,
)
from app.auth.dependencies import (
    require_admin_ops_operator,
    require_authenticated_ops_operator,
)
from app.auth.passwords import hash_plain_password, plain_password_matches_hash
from app.auth.sessions import issue_ops_session_token
from app.db import get_our_database_session
from app.models import OpsUser, OpsUserRole
from app.settings import Settings, get_settings


LOGIN_FAILED_DETAIL: str = "Invalid username or password."
LOGOUT_STATUS: str = "logged_out"
PASSWORD_CHANGED_STATUS: str = "password_changed"
CURRENT_PASSWORD_INCORRECT_DETAIL: str = "Current password is incorrect."
NEW_PASSWORD_SAME_AS_CURRENT_DETAIL: str = "New password must differ from the current password."
USERNAME_ALREADY_EXISTS_DETAIL: str = "Username already exists."
OPS_USER_NOT_FOUND_DETAIL: str = "Ops user not found."
LAST_ADMIN_ROLE_CHANGE_DETAIL: str = "Cannot demote the last admin."
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


@authentication_router.post("/change-password", response_model=OpsChangePasswordResponse)
def change_own_ops_password(
    ops_change_password_request: OpsChangePasswordRequest,
    current_ops_operator: OpsUser = Depends(require_authenticated_ops_operator),
    our_database_session: Session = Depends(get_our_database_session),
) -> OpsChangePasswordResponse:
    """Replace the signed-in operator's password. Self only; never logged."""

    current_password_accepted: bool = plain_password_matches_hash(
        ops_change_password_request.current_password,
        current_ops_operator.password_hash,
    )

    if not current_password_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CURRENT_PASSWORD_INCORRECT_DETAIL,
        )

    if ops_change_password_request.new_password == ops_change_password_request.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NEW_PASSWORD_SAME_AS_CURRENT_DETAIL,
        )

    current_ops_operator.password_hash = hash_plain_password(
        ops_change_password_request.new_password,
    )
    our_database_session.add(current_ops_operator)
    our_database_session.commit()
    change_password_response: OpsChangePasswordResponse = OpsChangePasswordResponse(
        status=PASSWORD_CHANGED_STATUS,
    )

    return change_password_response


@authentication_router.get("/users", response_model=list[OpsUserReadResponse])
def list_ops_users(
    current_admin_operator: OpsUser = Depends(require_admin_ops_operator),
    our_database_session: Session = Depends(get_our_database_session),
) -> list[OpsUserReadResponse]:
    """List ops operators. Admin only. Never includes password hashes."""

    del current_admin_operator
    ops_user_selection = select(OpsUser).order_by(OpsUser.username)
    ops_user_scalars = our_database_session.scalars(ops_user_selection)
    found_ops_users: list[OpsUser] = list(ops_user_scalars.all())
    ops_user_read_responses: list[OpsUserReadResponse] = [
        OpsUserReadResponse.model_validate(found_ops_user)
        for found_ops_user in found_ops_users
    ]

    return ops_user_read_responses


@authentication_router.post(
    "/users",
    response_model=OpsUserReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ops_user(
    ops_user_create_request: OpsUserCreateRequest,
    current_admin_operator: OpsUser = Depends(require_admin_ops_operator),
    our_database_session: Session = Depends(get_our_database_session),
) -> OpsUserReadResponse:
    """Create an ops operator. Admin only. Password is hashed, never logged."""

    del current_admin_operator
    submitted_username: str = ops_user_create_request.username.strip()

    if submitted_username == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be blank.",
        )

    existing_ops_user: OpsUser | None = _fetch_ops_user_by_username(
        submitted_username,
        our_database_session,
    )

    if existing_ops_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=USERNAME_ALREADY_EXISTS_DETAIL,
        )

    created_ops_user: OpsUser = OpsUser(
        username=submitted_username,
        password_hash=hash_plain_password(ops_user_create_request.password),
        role=ops_user_create_request.role,
    )
    our_database_session.add(created_ops_user)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=USERNAME_ALREADY_EXISTS_DETAIL,
    )
    our_database_session.refresh(created_ops_user)
    ops_user_read_response: OpsUserReadResponse = OpsUserReadResponse.model_validate(
        created_ops_user,
    )

    return ops_user_read_response


@authentication_router.patch("/users/{ops_user_id}", response_model=OpsUserReadResponse)
def patch_ops_user_role(
    ops_user_id: uuid.UUID,
    ops_user_role_patch_request: OpsUserRolePatchRequest,
    current_admin_operator: OpsUser = Depends(require_admin_ops_operator),
    our_database_session: Session = Depends(get_our_database_session),
) -> OpsUserReadResponse:
    """Change an ops operator's role. Admin only. Last admin cannot be demoted."""

    del current_admin_operator
    found_ops_user: OpsUser = _fetch_ops_user_by_id_or_raise(
        ops_user_id,
        our_database_session,
    )

    if (
        found_ops_user.role == OpsUserRole.ADMIN
        and ops_user_role_patch_request.role != OpsUserRole.ADMIN
        and _count_admin_ops_users(our_database_session) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=LAST_ADMIN_ROLE_CHANGE_DETAIL,
        )

    found_ops_user.role = ops_user_role_patch_request.role
    our_database_session.add(found_ops_user)
    our_database_session.commit()
    our_database_session.refresh(found_ops_user)
    ops_user_read_response: OpsUserReadResponse = OpsUserReadResponse.model_validate(
        found_ops_user,
    )

    return ops_user_read_response


@authentication_router.post(
    "/users/{ops_user_id}/reset-password",
    response_model=OpsChangePasswordResponse,
)
def reset_ops_user_password(
    ops_user_id: uuid.UUID,
    ops_user_reset_password_request: OpsUserResetPasswordRequest,
    current_admin_operator: OpsUser = Depends(require_admin_ops_operator),
    our_database_session: Session = Depends(get_our_database_session),
) -> OpsChangePasswordResponse:
    """Set another operator's password. Admin only. Never logged."""

    del current_admin_operator
    found_ops_user: OpsUser = _fetch_ops_user_by_id_or_raise(
        ops_user_id,
        our_database_session,
    )
    found_ops_user.password_hash = hash_plain_password(
        ops_user_reset_password_request.new_password,
    )
    our_database_session.add(found_ops_user)
    our_database_session.commit()
    reset_password_response: OpsChangePasswordResponse = OpsChangePasswordResponse(
        status=PASSWORD_CHANGED_STATUS,
    )

    return reset_password_response


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


def _fetch_ops_user_by_id_or_raise(
    ops_user_id: uuid.UUID,
    our_database_session: Session,
) -> OpsUser:
    """Return the ops user with this id, or raise HTTP 404."""

    found_ops_user: OpsUser | None = our_database_session.get(OpsUser, ops_user_id)

    if found_ops_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=OPS_USER_NOT_FOUND_DETAIL,
        )

    return found_ops_user


def _count_admin_ops_users(our_database_session: Session) -> int:
    """Return how many ops operators currently have the admin role."""

    admin_count_selection = select(func.count()).select_from(OpsUser).where(
        OpsUser.role == OpsUserRole.ADMIN,
    )
    admin_count_scalar = our_database_session.scalar(admin_count_selection)
    admin_count: int = int(admin_count_scalar or 0)

    return admin_count
