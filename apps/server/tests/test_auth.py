"""Ops operator login, session cookie, and route protection."""

import os
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone

os.environ.setdefault("TWERVA_ENV", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.router import api_v1_router
from app.auth.bootstrap import (
    OpsAdminBootstrapResult,
    bootstrap_admin_operator_if_needed,
)
from app.auth.passwords import hash_plain_password, plain_password_matches_hash
from app.auth.sessions import (
    InvalidOpsSessionError,
    issue_ops_session_token,
    read_ops_user_id_from_session_token,
)
from app.db import get_our_database_session
from app.main import application, get_health_status
from app.models import OpsUser
from app.settings import (
    TEST_PLACEHOLDER_SESSION_SECRET,
    Settings,
    clear_settings_cache,
    get_settings,
)


CORRECT_PASSWORD: str = "correct-horse-battery"
WRONG_PASSWORD: str = "wrong-password"
ADMIN_USERNAME: str = "admin"
SESSION_COOKIE_NAME: str = "twerva_ops_session"


class _FakeScalarResult:
    """Stand-in for `session.scalars(...).first()`."""

    def __init__(self, ops_user: OpsUser | None) -> None:

        self.ops_user: OpsUser | None = ops_user

    def first(self) -> OpsUser | None:

        return self.ops_user


class _FakeOpsDatabaseSession:
    """In-memory session that can serve one ops user for HTTP tests."""

    def __init__(self, ops_user: OpsUser | None) -> None:

        self.ops_user: OpsUser | None = ops_user
        self.added_ops_user: OpsUser | None = None
        self.commit_count: int = 0

    def scalars(self, statement: object) -> _FakeScalarResult:

        if self.ops_user is None:
            empty_result: _FakeScalarResult = _FakeScalarResult(None)

            return empty_result

        compiled_parameters: dict[str, object] = {}

        if hasattr(statement, "compile"):
            compiled_statement = statement.compile()
            compiled_parameters = dict(getattr(compiled_statement, "params", {}) or {})

        parameter_values: list[object] = list(compiled_parameters.values())

        if self.ops_user.username not in parameter_values:
            unmatched_result: _FakeScalarResult = _FakeScalarResult(None)

            return unmatched_result

        matching_result: _FakeScalarResult = _FakeScalarResult(self.ops_user)

        return matching_result

    def get(self, model: object, ops_user_id: uuid.UUID) -> OpsUser | None:

        if self.ops_user is None:

            return None

        if model is not OpsUser:

            return None

        if self.ops_user.id != ops_user_id:

            return None

        return self.ops_user

    def scalar(self, statement: object) -> int:

        del statement

        if self.ops_user is None:

            return 0

        return 1

    def add(self, ops_user: OpsUser) -> None:

        self.added_ops_user = ops_user
        self.ops_user = ops_user

    def commit(self) -> None:

        self.commit_count += 1

    def refresh(self, ops_user: OpsUser) -> None:

        if ops_user.id is None:
            ops_user.id = uuid.uuid4()

        if ops_user.created_at is None:
            ops_user.created_at = datetime.now(timezone.utc)

        if ops_user.updated_at is None:
            ops_user.updated_at = datetime.now(timezone.utc)


def _build_ops_user(username: str = ADMIN_USERNAME, password: str = CORRECT_PASSWORD,
) -> OpsUser:
    """Return an `OpsUser` instance that is not attached to Postgres."""

    now: datetime = datetime.now(timezone.utc)
    ops_user: OpsUser = OpsUser(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_plain_password(password),
        created_at=now,
        updated_at=now,
    )

    return ops_user


def _build_auth_test_client(fake_session: _FakeOpsDatabaseSession) -> TestClient:
    """Mount `/api/v1` with the fake session dependency."""

    test_application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield fake_session  # type: ignore[misc]

    test_application.dependency_overrides[get_our_database_session] = (
        override_database_session
    )
    test_application.include_router(api_v1_router)
    test_client: TestClient = TestClient(test_application)

    return test_client


class PasswordHashTests(unittest.TestCase):
    """bcrypt hash/verify does not echo the plaintext."""

    def test_plain_password_matches_its_hash(self) -> None:
        """A hash verifies the password that produced it."""

        password_hash: str = hash_plain_password(CORRECT_PASSWORD)
        passwords_match: bool = plain_password_matches_hash(
            CORRECT_PASSWORD,
            password_hash,
        )

        self.assertTrue(passwords_match)
        self.assertNotIn(CORRECT_PASSWORD, password_hash)

    def test_wrong_password_does_not_match(self) -> None:
        """A different password fails verification."""

        password_hash: str = hash_plain_password(CORRECT_PASSWORD)
        passwords_match: bool = plain_password_matches_hash(
            WRONG_PASSWORD,
            password_hash,
        )

        self.assertFalse(passwords_match)


class SignedSessionCookieTests(unittest.TestCase):
    """itsdangerous cookie payload is the ops user id."""

    def setUp(self) -> None:
        """Load test settings."""

        clear_settings_cache()
        self.settings: Settings = get_settings()

    def tearDown(self) -> None:
        """Drop the settings cache."""

        clear_settings_cache()

    def test_issued_token_round_trips_user_id(self) -> None:
        """Sign and verify returns the same UUID."""

        ops_user_id: uuid.UUID = uuid.uuid4()
        session_token: str = issue_ops_session_token(ops_user_id, self.settings)
        read_ops_user_id: uuid.UUID = read_ops_user_id_from_session_token(
            session_token,
            self.settings,
        )

        self.assertEqual(read_ops_user_id, ops_user_id)

    def test_forged_token_is_rejected(self) -> None:
        """A garbage cookie value raises InvalidOpsSessionError."""

        with self.assertRaises(InvalidOpsSessionError):
            read_ops_user_id_from_session_token("not-a-signed-token", self.settings)


class AuthHttpTests(unittest.TestCase):
    """Login / me / logout / protected routes against a fake session."""

    def setUp(self) -> None:
        """Build one ops user and a TestClient."""

        clear_settings_cache()
        self.ops_user: OpsUser = _build_ops_user()
        self.fake_session: _FakeOpsDatabaseSession = _FakeOpsDatabaseSession(
            self.ops_user,
        )
        self.test_client: TestClient = _build_auth_test_client(self.fake_session)

    def tearDown(self) -> None:
        """Close the client and drop settings."""

        self.test_client.close()
        clear_settings_cache()

    def test_login_success_sets_cookie_and_returns_user(self) -> None:
        """POST /auth/login with good credentials sets the session cookie."""

        login_response = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": ADMIN_USERNAME, "password": CORRECT_PASSWORD},
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["username"], ADMIN_USERNAME)
        self.assertEqual(login_response.json()["id"], str(self.ops_user.id))
        self.assertNotIn("password", login_response.json())
        self.assertNotIn("password_hash", login_response.json())
        self.assertIn(SESSION_COOKIE_NAME, login_response.cookies)

        session_cookie = login_response.cookies[SESSION_COOKIE_NAME]
        set_cookie_header: str = login_response.headers.get("set-cookie", "")

        self.assertNotEqual(session_cookie, "")
        self.assertIn("HttpOnly", set_cookie_header)
        self.assertIn("samesite=lax", set_cookie_header.lower())

    def test_login_failure_does_not_set_cookie(self) -> None:
        """Wrong password returns 401 and no session cookie."""

        login_response = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": ADMIN_USERNAME, "password": WRONG_PASSWORD},
        )

        self.assertEqual(login_response.status_code, 401)
        self.assertNotIn(SESSION_COOKIE_NAME, login_response.cookies)

    def test_me_returns_current_user_with_cookie(self) -> None:
        """GET /auth/me after login returns the operator."""

        self.test_client.post(
            "/api/v1/auth/login",
            json={"username": ADMIN_USERNAME, "password": CORRECT_PASSWORD},
        )
        me_response = self.test_client.get("/api/v1/auth/me")

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["username"], ADMIN_USERNAME)

    def test_me_without_cookie_returns_401(self) -> None:
        """GET /auth/me with no cookie is 401."""

        me_response = self.test_client.get("/api/v1/auth/me")

        self.assertEqual(me_response.status_code, 401)

    def test_protected_route_without_cookie_returns_401(self) -> None:
        """GET /api/v1/brands without a session cookie is 401."""

        brands_response = self.test_client.get("/api/v1/brands")

        self.assertEqual(brands_response.status_code, 401)

    def test_logout_clears_cookie(self) -> None:
        """POST /auth/logout then GET /me is 401."""

        self.test_client.post(
            "/api/v1/auth/login",
            json={"username": ADMIN_USERNAME, "password": CORRECT_PASSWORD},
        )
        logout_response = self.test_client.post("/api/v1/auth/logout")

        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json()["status"], "logged_out")

        me_response = self.test_client.get("/api/v1/auth/me")

        self.assertEqual(me_response.status_code, 401)


class HealthWithoutDatabaseUrlTests(unittest.TestCase):
    """Health stays public and does not need DATABASE_URL."""

    def test_process_health_endpoint_returns_ok(self) -> None:
        """GET /health on the process app is 200 without a session cookie."""

        test_client: TestClient = TestClient(application)
        health_response = test_client.get("/health")

        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json(), {"status": "ok"})

    def test_get_health_status_still_works_without_database_url(self) -> None:
        """Direct handler works when DATABASE_URL is unset."""

        import asyncio

        previous_database_url: str | None = os.environ.pop("DATABASE_URL", None)

        try:
            health_status_response = asyncio.run(get_health_status())
        finally:

            if previous_database_url is not None:
                os.environ["DATABASE_URL"] = previous_database_url

        self.assertEqual(health_status_response.status, "ok")


class BootstrapAdminTests(unittest.TestCase):
    """First admin is created only when the table is empty and env is set."""

    def test_bootstrap_creates_admin_when_table_is_empty(self) -> None:
        """Insert one ops user from settings; do not log the password."""

        fake_session: _FakeOpsDatabaseSession = _FakeOpsDatabaseSession(None)
        settings: Settings = Settings(
            database_url="postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
            ops_admin_username="bootstrap-admin",
            ops_admin_password="bootstrap-secret",
            session_secret=TEST_PLACEHOLDER_SESSION_SECRET,
            session_cookie_secure=False,
        )

        with self.assertLogs("twerva.auth.bootstrap", level="INFO") as log_capture:
            bootstrap_result: OpsAdminBootstrapResult = (
                bootstrap_admin_operator_if_needed(fake_session, settings)  # type: ignore[arg-type]
            )

        self.assertTrue(bootstrap_result.created)
        self.assertEqual(bootstrap_result.username, "bootstrap-admin")
        self.assertEqual(fake_session.commit_count, 1)
        self.assertIsNotNone(fake_session.added_ops_user)
        joined_logs: str = "\n".join(log_capture.output)

        self.assertIn("bootstrap-admin", joined_logs)
        self.assertNotIn("bootstrap-secret", joined_logs)

    def test_bootstrap_skips_when_users_exist(self) -> None:
        """Existing rows are left alone even if admin env is set."""

        existing_ops_user: OpsUser = _build_ops_user()
        fake_session: _FakeOpsDatabaseSession = _FakeOpsDatabaseSession(
            existing_ops_user,
        )
        settings: Settings = Settings(
            database_url="postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
            ops_admin_username="other-admin",
            ops_admin_password="other-secret",
            session_secret=TEST_PLACEHOLDER_SESSION_SECRET,
            session_cookie_secure=False,
        )
        bootstrap_result: OpsAdminBootstrapResult = bootstrap_admin_operator_if_needed(
            fake_session,  # type: ignore[arg-type]
            settings,
        )

        self.assertFalse(bootstrap_result.created)
        self.assertEqual(fake_session.commit_count, 0)
        self.assertIn("already has", bootstrap_result.skipped_reason or "")


if __name__ == "__main__":
    unittest.main()
