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
from app.models import OpsUser, OpsUserRole
from app.settings import (
    TEST_PLACEHOLDER_SESSION_SECRET,
    Settings,
    clear_settings_cache,
    get_settings,
)


CORRECT_PASSWORD: str = "correct-horse-battery"
WRONG_PASSWORD: str = "wrong-password"
NEW_PASSWORD: str = "new-correct-horse"
ADMIN_USERNAME: str = "admin"
READER_USERNAME: str = "reader-agent"
SESSION_COOKIE_NAME: str = "twerva_ops_session"


class _FakeScalarResult:
    """Stand-in for `session.scalars(...).first()` / `.all()`."""

    def __init__(self, ops_users: list[OpsUser]) -> None:

        self.ops_users: list[OpsUser] = ops_users

    def first(self) -> OpsUser | None:

        if not self.ops_users:

            return None

        return self.ops_users[0]

    def all(self) -> list[OpsUser]:

        return list(self.ops_users)


class _FakeOpsDatabaseSession:
    """In-memory session that can serve one or more ops users for HTTP tests."""

    def __init__(self, ops_user: OpsUser | None) -> None:

        self.ops_users: list[OpsUser] = [] if ops_user is None else [ops_user]
        self.added_ops_user: OpsUser | None = None
        self.commit_count: int = 0

    @property
    def ops_user(self) -> OpsUser | None:
        """First stored operator, matching the single-user constructor."""

        if not self.ops_users:

            return None

        return self.ops_users[0]

    def scalars(self, statement: object) -> _FakeScalarResult:

        compiled_sql: str = ""
        compiled_parameters: dict[str, object] = {}

        if hasattr(statement, "compile"):
            compiled_statement = statement.compile()
            compiled_sql = str(compiled_statement).lower()
            compiled_parameters = dict(getattr(compiled_statement, "params", {}) or {})

        is_ops_user_query: bool = (
            "ops_users" in compiled_sql or "opsuser" in compiled_sql
        )

        if compiled_sql != "" and not is_ops_user_query:
            empty_non_user_result: _FakeScalarResult = _FakeScalarResult([])

            return empty_non_user_result

        parameter_values: list[object] = list(compiled_parameters.values())
        matching_ops_users: list[OpsUser] = list(self.ops_users)

        if parameter_values:
            username_matches: list[OpsUser] = [
                stored_ops_user
                for stored_ops_user in self.ops_users
                if stored_ops_user.username in parameter_values
            ]

            if username_matches:
                matching_ops_users = username_matches
            elif any(isinstance(parameter_value, str) for parameter_value in parameter_values):
                matching_ops_users = []

        matching_ops_users.sort(key=lambda stored_ops_user: stored_ops_user.username)

        return _FakeScalarResult(matching_ops_users)

    def get(self, model: object, ops_user_id: uuid.UUID) -> OpsUser | None:

        if model is not OpsUser:

            return None

        for stored_ops_user in self.ops_users:

            if stored_ops_user.id == ops_user_id:

                return stored_ops_user

        return None

    def scalar(self, statement: object) -> int:

        compiled_parameters: dict[str, object] = {}

        if hasattr(statement, "compile"):
            compiled_statement = statement.compile()
            compiled_parameters = dict(getattr(compiled_statement, "params", {}) or {})

        parameter_values: list[object] = list(compiled_parameters.values())

        if (
            OpsUserRole.ADMIN in parameter_values
            or OpsUserRole.ADMIN.value in parameter_values
        ):
            admin_count: int = sum(
                1
                for stored_ops_user in self.ops_users
                if stored_ops_user.role == OpsUserRole.ADMIN
            )

            return admin_count

        return len(self.ops_users)

    def add(self, ops_user: OpsUser) -> None:

        self.added_ops_user = ops_user

        for user_index, stored_ops_user in enumerate(self.ops_users):

            if stored_ops_user.id is not None and stored_ops_user.id == ops_user.id:
                self.ops_users[user_index] = ops_user

                return

        self.ops_users.append(ops_user)

    def commit(self) -> None:

        self.commit_count += 1

    def rollback(self) -> None:

        return

    def refresh(self, ops_user: OpsUser) -> None:

        if ops_user.id is None:
            ops_user.id = uuid.uuid4()

        if ops_user.created_at is None:
            ops_user.created_at = datetime.now(timezone.utc)

        if ops_user.updated_at is None:
            ops_user.updated_at = datetime.now(timezone.utc)

        if getattr(ops_user, "role", None) is None:
            ops_user.role = OpsUserRole.READER


def _build_ops_user(
    username: str = ADMIN_USERNAME,
    password: str = CORRECT_PASSWORD,
    role: OpsUserRole = OpsUserRole.ADMIN,
) -> OpsUser:
    """Return an `OpsUser` instance that is not attached to Postgres."""

    now: datetime = datetime.now(timezone.utc)
    ops_user: OpsUser = OpsUser(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_plain_password(password),
        role=role,
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
        self.assertEqual(login_response.json()["role"], OpsUserRole.ADMIN.value)
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
        self.assertEqual(me_response.json()["role"], OpsUserRole.ADMIN.value)

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

    def test_bootstrap_created_user_is_admin(self) -> None:
        """The first seeded operator is role=admin."""

        fake_session: _FakeOpsDatabaseSession = _FakeOpsDatabaseSession(None)
        settings: Settings = Settings(
            database_url="postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
            ops_admin_username="bootstrap-admin",
            ops_admin_password="bootstrap-secret",
            session_secret=TEST_PLACEHOLDER_SESSION_SECRET,
            session_cookie_secure=False,
        )
        bootstrap_result: OpsAdminBootstrapResult = bootstrap_admin_operator_if_needed(
            fake_session,  # type: ignore[arg-type]
            settings,
        )

        self.assertTrue(bootstrap_result.created)
        self.assertIsNotNone(fake_session.added_ops_user)
        self.assertEqual(fake_session.added_ops_user.role, OpsUserRole.ADMIN)


class ChangePasswordHttpTests(unittest.TestCase):
    """Self-service password change for any signed-in operator."""

    def setUp(self) -> None:
        """Build one admin and a TestClient."""

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

    def test_change_password_success_then_old_password_fails(self) -> None:
        """Correct current password updates the hash; old password no longer logs in."""

        self._login(ADMIN_USERNAME, CORRECT_PASSWORD)
        change_response = self.test_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": CORRECT_PASSWORD, "new_password": NEW_PASSWORD},
        )

        self.assertEqual(change_response.status_code, 200)
        self.assertEqual(change_response.json()["status"], "password_changed")
        self.assertTrue(
            plain_password_matches_hash(NEW_PASSWORD, self.ops_user.password_hash),
        )
        self.assertFalse(
            plain_password_matches_hash(CORRECT_PASSWORD, self.ops_user.password_hash),
        )

        self.test_client.post("/api/v1/auth/logout")
        old_password_login = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": ADMIN_USERNAME, "password": CORRECT_PASSWORD},
        )
        new_password_login = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": ADMIN_USERNAME, "password": NEW_PASSWORD},
        )

        self.assertEqual(old_password_login.status_code, 401)
        self.assertEqual(new_password_login.status_code, 200)

    def test_change_password_rejects_wrong_current_password(self) -> None:
        """Wrong current password is 400 and leaves the hash unchanged."""

        previous_password_hash: str = self.ops_user.password_hash
        self._login(ADMIN_USERNAME, CORRECT_PASSWORD)
        change_response = self.test_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": WRONG_PASSWORD, "new_password": NEW_PASSWORD},
        )

        self.assertEqual(change_response.status_code, 400)
        self.assertEqual(self.ops_user.password_hash, previous_password_hash)

    def test_change_password_requires_authentication(self) -> None:
        """No cookie is 401."""

        change_response = self.test_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": CORRECT_PASSWORD, "new_password": NEW_PASSWORD},
        )

        self.assertEqual(change_response.status_code, 401)

    def _login(self, username: str, password: str) -> None:
        """Establish a session cookie for later requests."""

        login_response = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        self.assertEqual(login_response.status_code, 200)


class OpsUserAdminHttpTests(unittest.TestCase):
    """Admin can list/create operators; readers cannot."""

    def setUp(self) -> None:
        """Build an admin plus a reader in one fake session."""

        clear_settings_cache()
        self.admin_user: OpsUser = _build_ops_user()
        self.reader_user: OpsUser = _build_ops_user(
            username=READER_USERNAME,
            role=OpsUserRole.READER,
        )
        self.fake_session: _FakeOpsDatabaseSession = _FakeOpsDatabaseSession(
            self.admin_user,
        )
        self.fake_session.ops_users.append(self.reader_user)
        self.test_client: TestClient = _build_auth_test_client(self.fake_session)

    def tearDown(self) -> None:
        """Close the client and drop settings."""

        self.test_client.close()
        clear_settings_cache()

    def test_admin_lists_ops_users_without_password_hashes(self) -> None:
        """GET /auth/users returns id, username, role, timestamps only."""

        self._login(ADMIN_USERNAME, CORRECT_PASSWORD)
        list_response = self.test_client.get("/api/v1/auth/users")

        self.assertEqual(list_response.status_code, 200)
        listed_usernames: list[str] = [
            user_row["username"] for user_row in list_response.json()
        ]

        self.assertIn(ADMIN_USERNAME, listed_usernames)
        self.assertIn(READER_USERNAME, listed_usernames)

        for user_row in list_response.json():
            self.assertIn("role", user_row)
            self.assertNotIn("password", user_row)
            self.assertNotIn("password_hash", user_row)

    def test_admin_creates_reader_user(self) -> None:
        """POST /auth/users as admin creates a reader without echoing the password."""

        self._login(ADMIN_USERNAME, CORRECT_PASSWORD)
        create_response = self.test_client.post(
            "/api/v1/auth/users",
            json={
                "username": "new-reader",
                "password": NEW_PASSWORD,
                "role": OpsUserRole.READER.value,
            },
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["username"], "new-reader")
        self.assertEqual(create_response.json()["role"], OpsUserRole.READER.value)
        self.assertNotIn("password", create_response.json())
        self.assertNotIn("password_hash", create_response.json())
        self.assertIsNotNone(self.fake_session.added_ops_user)
        self.assertTrue(
            plain_password_matches_hash(
                NEW_PASSWORD,
                self.fake_session.added_ops_user.password_hash,
            ),
        )

        created_login = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": "new-reader", "password": NEW_PASSWORD},
        )

        self.assertEqual(created_login.status_code, 200)
        self.assertEqual(created_login.json()["role"], OpsUserRole.READER.value)

    def test_reader_cannot_list_or_create_users(self) -> None:
        """Non-admin GET/POST /auth/users is 403."""

        self._login(READER_USERNAME, CORRECT_PASSWORD)
        list_response = self.test_client.get("/api/v1/auth/users")
        create_response = self.test_client.post(
            "/api/v1/auth/users",
            json={
                "username": "should-fail",
                "password": NEW_PASSWORD,
                "role": OpsUserRole.READER.value,
            },
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)

    def test_admin_can_patch_role_and_reset_password(self) -> None:
        """Optional admin routes: change role and set a password."""

        self._login(ADMIN_USERNAME, CORRECT_PASSWORD)
        patch_response = self.test_client.patch(
            f"/api/v1/auth/users/{self.reader_user.id}",
            json={"role": OpsUserRole.ADMIN.value},
        )
        reset_response = self.test_client.post(
            f"/api/v1/auth/users/{self.reader_user.id}/reset-password",
            json={"new_password": NEW_PASSWORD},
        )

        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["role"], OpsUserRole.ADMIN.value)
        self.assertEqual(reset_response.status_code, 200)
        self.assertTrue(
            plain_password_matches_hash(NEW_PASSWORD, self.reader_user.password_hash),
        )

    def _login(self, username: str, password: str) -> None:
        """Establish a session cookie for later requests."""

        login_response = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        self.assertEqual(login_response.status_code, 200)


class ReaderRbacHttpTests(unittest.TestCase):
    """Readers may GET domain routes; mutations are 403."""

    def setUp(self) -> None:
        """Build a reader-only client."""

        clear_settings_cache()
        self.reader_user: OpsUser = _build_ops_user(
            username=READER_USERNAME,
            role=OpsUserRole.READER,
        )
        self.fake_session: _FakeOpsDatabaseSession = _FakeOpsDatabaseSession(
            self.reader_user,
        )
        self.test_client: TestClient = _build_auth_test_client(self.fake_session)
        login_response = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": READER_USERNAME, "password": CORRECT_PASSWORD},
        )

        self.assertEqual(login_response.status_code, 200)

    def tearDown(self) -> None:
        """Close the client and drop settings."""

        self.test_client.close()
        clear_settings_cache()

    def test_reader_can_get_domain_routes(self) -> None:
        """GET /api/v1/brands is allowed for readers."""

        brands_response = self.test_client.get("/api/v1/brands")

        self.assertEqual(brands_response.status_code, 200)
        self.assertEqual(brands_response.json(), [])

    def test_reader_cannot_mutate_domain_routes(self) -> None:
        """POST brands, skeletons, and carousels are 403 for readers."""

        create_brand_response = self.test_client.post(
            "/api/v1/brands",
            json={"slug": "blocked", "name": "Blocked"},
        )

        self.assertEqual(create_brand_response.status_code, 403)
        self.assertIn("read-only", create_brand_response.json()["detail"].lower())

        patch_skeleton_response = self.test_client.patch(
            f"/api/v1/skeletons/{uuid.uuid4()}",
            json={"status": "live"},
        )

        self.assertEqual(patch_skeleton_response.status_code, 403)
        self.assertIn("read-only", patch_skeleton_response.json()["detail"].lower())

        create_element_response = self.test_client.post(
            f"/api/v1/skeletons/{uuid.uuid4()}/elements",
            json={
                "name": "Title",
                "band": "top",
                "content_kind": "text",
                "text_source": "title",
                "font_family": "DejaVu Sans",
                "font_size": 32,
                "font_color": "#112233",
                "alignment": "left",
            },
        )

        self.assertEqual(create_element_response.status_code, 403)
        self.assertIn("read-only", create_element_response.json()["detail"].lower())

        duplicate_skeleton_response = self.test_client.post(
            f"/api/v1/skeletons/{uuid.uuid4()}/duplicate",
        )

        self.assertEqual(duplicate_skeleton_response.status_code, 403)
        self.assertIn("read-only", duplicate_skeleton_response.json()["detail"].lower())

        delete_skeleton_response = self.test_client.delete(
            f"/api/v1/skeletons/{uuid.uuid4()}",
        )

        self.assertEqual(delete_skeleton_response.status_code, 403)
        self.assertIn("read-only", delete_skeleton_response.json()["detail"].lower())

        create_source_response = self.test_client.post(
            "/api/v1/carousels",
            json={"name": "Blocked album", "skeleton_id": str(uuid.uuid4())},
        )

        self.assertEqual(create_source_response.status_code, 403)
        self.assertIn("read-only", create_source_response.json()["detail"].lower())

        change_step_response = self.test_client.patch(
            f"/api/v1/carousels/{uuid.uuid4()}/step",
            json={"editor_step": 0},
        )

        self.assertEqual(change_step_response.status_code, 403)
        self.assertIn("read-only", change_step_response.json()["detail"].lower())

        upload_image_response = self.test_client.post(
            f"/api/v1/carousels/{uuid.uuid4()}/slides/{uuid.uuid4()}/images",
            data={"license": "cc0", "carousel": "https://example.com/photo"},
            files=[("files", ("photo.jpg", b"not-an-image", "image/jpeg"))],
        )

        self.assertEqual(upload_image_response.status_code, 403)
        self.assertIn("read-only", upload_image_response.json()["detail"].lower())

        import_image_response = self.test_client.post(
            f"/api/v1/carousels/{uuid.uuid4()}/slides/{uuid.uuid4()}/images/import",
            json={
                "url": "https://example.com/plate.png",
                "license": "cc0",
                "carousel": "https://example.com/plate.png",
            },
        )

        self.assertEqual(import_image_response.status_code, 403)
        self.assertIn("read-only", import_image_response.json()["detail"].lower())

        create_research_response = self.test_client.post(
            "/api/v1/research",
            json={"title": "Blocked notes"},
        )

        self.assertEqual(create_research_response.status_code, 403)
        self.assertIn("read-only", create_research_response.json()["detail"].lower())

        sample_response = self.test_client.post(
            f"/api/v1/skeletons/{uuid.uuid4()}/samples",
            json={"source_item_id": str(uuid.uuid4())},
        )

        self.assertEqual(sample_response.status_code, 403)
        self.assertIn("read-only", sample_response.json()["detail"].lower())

    def test_reader_can_preview_a_slide_on_its_skeleton(self) -> None:
        """Readers may POST the in-carousel preview. A missing carousel is 404."""

        preview_response = self.test_client.post(
            f"/api/v1/carousels/{uuid.uuid4()}/slides/preview",
            json={"texts": [], "slide_id": None},
        )

        self.assertEqual(preview_response.status_code, 404)
        self.assertNotIn("read-only", preview_response.json()["detail"].lower())

    def test_reader_can_preview_a_skeleton_payload(self) -> None:
        """Readers may POST /api/v1/skeletons/preview. No source item is required."""

        preview_response = self.test_client.post(
            "/api/v1/skeletons/preview",
            json={"elements": []},
        )

        self.assertEqual(preview_response.status_code, 200)
        self.assertIn("image_png_base64", preview_response.json())
        self.assertFalse(preview_response.json()["blocked"])

    def test_reader_can_change_own_password(self) -> None:
        """Readers may POST /auth/change-password."""

        change_response = self.test_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": CORRECT_PASSWORD, "new_password": NEW_PASSWORD},
        )

        self.assertEqual(change_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
