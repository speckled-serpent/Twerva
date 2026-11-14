"""Account create/list/get/patch routes. No OAuth token fields."""

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_account_by_id_or_raise, fetch_cluster_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    AccountConnectionReadResponse,
    AccountCreateRequest,
    AccountProfileKeyPatchRequest,
    AccountReadResponse,
)
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models import Account, OpsUser
from app.publish.errors import PublishAdapterNotConfiguredError, PublishError
from app.publish.factory import get_publish_adapter


accounts_router: APIRouter = APIRouter(prefix="/accounts", tags=["accounts"])


@accounts_router.post(
    "",
    response_model=AccountReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    account_create_request: AccountCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> AccountReadResponse:
    """Persist an Account under an existing Cluster."""

    fetch_cluster_by_id_or_raise(
        account_create_request.cluster_id,
        our_database_session,
    )
    created_account: Account = Account(
        cluster_id=account_create_request.cluster_id,
        platform=account_create_request.platform,
        handle=account_create_request.handle,
        external_account_id=account_create_request.external_account_id,
        status=account_create_request.status,
        cadence_cap_per_day=account_create_request.cadence_cap_per_day,
    )
    our_database_session.add(created_account)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Account handle already exists on this platform.",
    )
    our_database_session.refresh(created_account)

    account_read_response: AccountReadResponse = AccountReadResponse.model_validate(
        created_account,
    )

    return account_read_response


@accounts_router.patch("/{account_id}", response_model=AccountReadResponse)
def patch_account_profile_key(
    account_id: uuid.UUID,
    profile_key_patch_request: AccountProfileKeyPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
) -> AccountReadResponse:
    """Store the Ayrshare profile key. This route does not call Ayrshare.

    Null, or a string that strips to empty, stores null. Any other
    string stores the stripped value. The API key is not accepted.
    """

    found_account: Account = fetch_account_by_id_or_raise(
        account_id,
        our_database_session,
    )
    found_account.external_account_id = _stored_profile_key(
        profile_key_patch_request.external_account_id,
    )
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Account profile key could not be saved.",
    )
    our_database_session.refresh(found_account)
    account_read_response: AccountReadResponse = AccountReadResponse.model_validate(
        found_account,
    )

    return account_read_response


def _stored_profile_key(raw_profile_key: str | None) -> str | None:
    """Return the stripped profile key, or null when it is blank."""

    if raw_profile_key is None:

        return None

    stripped_profile_key: str = raw_profile_key.strip()

    if stripped_profile_key == "":

        return None

    return stripped_profile_key


ACCOUNT_CONNECTION_NOT_CONFIGURED_DETAIL: str = (
    "The Ayrshare adapter is not configured. Leave the publish adapter on mock."
)


@accounts_router.get(
    "/{account_id}/connection",
    response_model=AccountConnectionReadResponse,
)
def read_account_connection(
    account_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> AccountConnectionReadResponse | JSONResponse:
    """Read the linked platforms. This does not post or change the account.

    A missing adapter key is HTTP 409 with ``ok`` false. A vendor refusal
    is ``ok`` false and the error sentence. Neither response includes the
    API key or the profile key.
    """

    _ = current_ops_operator
    found_account: Account = fetch_account_by_id_or_raise(
        account_id,
        our_database_session,
    )

    try:
        connection_check = get_publish_adapter().check_connection(found_account)
    except PublishAdapterNotConfiguredError:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "adapter": "ayrshare",
                "ok": False,
                "detail": ACCOUNT_CONNECTION_NOT_CONFIGURED_DETAIL,
            },
        )
    except PublishError as publish_error:
        safe_detail: str = str(publish_error).replace(
            "AYRSHARE_API_KEY",
            "the server API key setting",
        )
        connection_read = AccountConnectionReadResponse(
            adapter="ayrshare",
            ok=False,
            detail=safe_detail,
        )

        return connection_read

    connection_read = AccountConnectionReadResponse(
        adapter=connection_check.adapter,
        ok=connection_check.ok,
        detail=connection_check.detail,
    )

    return connection_read


@accounts_router.get("", response_model=list[AccountReadResponse])
def list_accounts(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[AccountReadResponse]:
    """Return every Account, newest first."""

    account_selection = select(Account).order_by(Account.created_at.desc())
    account_scalars = our_database_session.scalars(account_selection)
    accounts: list[Account] = list(account_scalars.all())
    account_read_responses: list[AccountReadResponse] = [
        AccountReadResponse.model_validate(account) for account in accounts
    ]

    return account_read_responses


@accounts_router.get("/{account_id}", response_model=AccountReadResponse)
def get_account_by_id(
    account_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> AccountReadResponse:
    """Return one Account by primary key."""

    found_account: Account = fetch_account_by_id_or_raise(
        account_id,
        our_database_session,
    )
    account_read_response: AccountReadResponse = AccountReadResponse.model_validate(
        found_account,
    )

    return account_read_response
