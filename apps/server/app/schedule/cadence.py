"""UTC-day cadence caps against `accounts.cadence_cap_per_day` (1.5b).

Cadence day is the **UTC calendar day** of `scheduled_for` (not account-local).
Naive datetimes are treated as UTC. `cadence_cap_per_day` null means no cap.

Counted jobs: existing `post_jobs` for the account whose `scheduled_for`
falls in that UTC day and whose status is **not** `failed`. Failed rows
do not consume the cap so a retry can take the slot.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models import Account, PostJob
from app.models.enums import PostJobStatus
from app.schedule.errors import CadenceCapExceededError


def as_utc_datetime(scheduled_for: datetime) -> datetime:
    """Return an aware UTC datetime; naive values are assumed UTC."""

    if scheduled_for.tzinfo is None:
        utc_datetime: datetime = scheduled_for.replace(tzinfo=timezone.utc)

        return utc_datetime

    utc_datetime = scheduled_for.astimezone(timezone.utc)

    return utc_datetime


def utc_calendar_day_bounds(scheduled_for: datetime) -> tuple[datetime, datetime]:
    """Return `[day_start, day_end)` for the UTC calendar day of `scheduled_for`."""

    scheduled_for_utc: datetime = as_utc_datetime(scheduled_for)
    day_start: datetime = datetime(
        scheduled_for_utc.year,
        scheduled_for_utc.month,
        scheduled_for_utc.day,
        tzinfo=timezone.utc,
    )
    day_end: datetime = day_start + timedelta(days=1)

    return day_start, day_end


def cadence_cap_blocks_additional_schedule(
    existing_non_failed_count: int,
    cadence_cap_per_day: int | None,
) -> bool:
    """Return True when an additional job would exceed or already meet the cap.

    Under cap (`count < cap`): False (schedule allowed).
    At cap (`count == cap`): True (409).
    Over cap (`count > cap`): True (409).
    Null cap: False (no limit).
    """

    if cadence_cap_per_day is None:

        return False

    cap_is_reached: bool = existing_non_failed_count >= cadence_cap_per_day

    return cap_is_reached


def count_non_failed_post_jobs_for_account_on_utc_day(
    account_id: uuid.UUID,
    scheduled_for: datetime,
    our_database_session: Session,
) -> int:
    """Count non-failed post_jobs for `account_id` on the UTC day of `scheduled_for`."""

    day_start: datetime
    day_end: datetime
    day_start, day_end = utc_calendar_day_bounds(scheduled_for)
    post_job_count_selection: Select[tuple[int]] = select(func.count()).select_from(
        PostJob,
    )
    account_filter = PostJob.account_id == account_id
    not_failed_filter = PostJob.status != PostJobStatus.FAILED
    day_start_filter = PostJob.scheduled_for >= day_start
    day_end_filter = PostJob.scheduled_for < day_end
    filtered_count_selection: Select[tuple[int]] = post_job_count_selection.where(
        account_filter,
        not_failed_filter,
        day_start_filter,
        day_end_filter,
    )
    counted_jobs: int | None = our_database_session.scalar(filtered_count_selection)
    existing_non_failed_count: int

    if counted_jobs is None:
        existing_non_failed_count = 0
    else:
        existing_non_failed_count = counted_jobs

    return existing_non_failed_count


def raise_if_cadence_cap_exceeded(
    account: Account,
    scheduled_for: datetime,
    our_database_session: Session,
) -> None:
    """Raise CadenceCapExceededError when the UTC-day cap would be exceeded.

    Args:
        account: Account whose `cadence_cap_per_day` is consulted (null = no cap).
        scheduled_for: Proposed schedule time (UTC day derived from this).
        our_database_session: Open SQLAlchemy session.

    Raises:
        CadenceCapExceededError: Existing non-failed jobs already meet/exceed cap.
    """

    cadence_cap_per_day: int | None = account.cadence_cap_per_day

    if cadence_cap_per_day is None:

        return

    existing_non_failed_count: int = count_non_failed_post_jobs_for_account_on_utc_day(
        account.id,
        scheduled_for,
        our_database_session,
    )
    cap_blocks_schedule: bool = cadence_cap_blocks_additional_schedule(
        existing_non_failed_count,
        cadence_cap_per_day,
    )

    if not cap_blocks_schedule:

        return

    day_start: datetime
    day_start, _day_end = utc_calendar_day_bounds(scheduled_for)

    raise CadenceCapExceededError(
        account.id,
        day_start.date(),
        existing_non_failed_count,
        cadence_cap_per_day,
    )
