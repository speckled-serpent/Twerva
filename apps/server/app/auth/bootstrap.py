"""Create the first ops admin from environment variables.

Bootstrap runs when `ops_users` is empty **and** both `OPS_ADMIN_USERNAME`
and `OPS_ADMIN_PASSWORD` are set. It never updates an existing row and
never logs the password.

Run at API attach (non-test) or:

    python -m app.auth.bootstrap
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_plain_password
from app.models import OpsUser
from app.settings import Settings, get_settings


LOGGER: logging.Logger = logging.getLogger("twerva.auth.bootstrap")


@dataclass(frozen=True)
class OpsAdminBootstrapResult:
    """Outcome of one bootstrap attempt."""

    created: bool
    skipped_reason: str | None
    username: str | None


def bootstrap_admin_operator_if_needed(
    our_database_session: Session,
    settings: Settings,
) -> OpsAdminBootstrapResult:
    """Insert the first ops admin when the table is empty and env is set.

    Args:
        our_database_session: Open SQLAlchemy session. This function commits
            when a row is created.
        settings: Process settings (admin username/password, never logged).

    Returns:
        Whether a user was created and a skip reason when not.
    """

    existing_user_count: int = _count_ops_users(our_database_session)

    if existing_user_count > 0:
        skipped_when_users_exist: OpsAdminBootstrapResult = OpsAdminBootstrapResult(
            created=False,
            skipped_reason="ops_users already has at least one row",
            username=None,
        )

        return skipped_when_users_exist

    admin_username: str = settings.ops_admin_username.strip()
    admin_password: str = settings.ops_admin_password

    if admin_username == "" or admin_password == "":
        skipped_when_env_unset: OpsAdminBootstrapResult = OpsAdminBootstrapResult(
            created=False,
            skipped_reason="OPS_ADMIN_USERNAME or OPS_ADMIN_PASSWORD is unset",
            username=None,
        )

        return skipped_when_env_unset

    password_hash: str = hash_plain_password(admin_password)
    created_ops_user: OpsUser = OpsUser(
        username=admin_username,
        password_hash=password_hash,
    )
    our_database_session.add(created_ops_user)
    our_database_session.commit()
    our_database_session.refresh(created_ops_user)
    LOGGER.info("Created bootstrap ops admin username=%s", created_ops_user.username)
    created_result: OpsAdminBootstrapResult = OpsAdminBootstrapResult(
        created=True,
        skipped_reason=None,
        username=created_ops_user.username,
    )

    return created_result


def bootstrap_admin_operator_from_environment() -> OpsAdminBootstrapResult:
    """Open `SessionLocal` and run bootstrap with process settings."""

    from app.db import SessionLocal

    settings: Settings = get_settings()
    our_database_session: Session = SessionLocal()

    try:
        bootstrap_result: OpsAdminBootstrapResult = bootstrap_admin_operator_if_needed(
            our_database_session,
            settings,
        )
    finally:
        our_database_session.close()

    return bootstrap_result


def main() -> int:
    """CLI entry: bootstrap the first admin and print a password-free status."""

    bootstrap_result: OpsAdminBootstrapResult = bootstrap_admin_operator_from_environment()

    if bootstrap_result.created:
        print(f"Created bootstrap ops admin username={bootstrap_result.username}")

        return 0

    print(f"Skipped ops admin bootstrap ({bootstrap_result.skipped_reason})")

    return 0


def _count_ops_users(our_database_session: Session) -> int:
    """Return how many ops operator rows exist."""

    user_count_selection = select(func.count()).select_from(OpsUser)
    user_count_scalar = our_database_session.scalar(user_count_selection)
    user_count: int = int(user_count_scalar or 0)

    return user_count


if __name__ == "__main__":
    raise SystemExit(main())
