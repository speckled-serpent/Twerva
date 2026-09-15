"""Account create/list/get routes. No OAuth token fields."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_account_by_id_or_raise, fetch_cluster_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import AccountCreateRequest, AccountReadResponse
from app.db import get_our_database_session
from app.models import Account


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
