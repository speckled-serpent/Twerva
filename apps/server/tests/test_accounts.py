"""Account profile key: PATCH stores it, and a reader cannot write."""

from __future__ import annotations

import json
import os
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.accounts import (
    create_account,
    patch_account_profile_key,
    read_account_connection,
)
from app.publish.ayrshare import AyrsharePublishAdapter
from app.publish.mock import MOCK_CONNECTION_DETAIL
from app.api.v1.brands import create_brand
from app.api.v1.clusters import create_cluster
from app.api.v1.router import api_v1_router
from app.api.v1.schemas import (
    AccountCreateRequest,
    AccountProfileKeyPatchRequest,
    AccountReadResponse,
    BrandCreateRequest,
    ClusterCreateRequest,
)
from app.auth.passwords import hash_plain_password
from app.db import get_our_database_session
from app.models.account import Account
from app.models.enums import OpsUserRole, Platform
from app.models.ops_user import OpsUser
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
READER_USERNAME: str = "reader-agent"
READER_PASSWORD: str = "correct-horse-battery"
PROFILE_KEY: str = "ayrshare-profile-key-1"
AYRSHARE_TEST_API_KEY: str = "test-ayrshare-api-key"


def _postgres_available() -> bool:
    """Return whether the local Postgres admin database accepts a connection."""

    admin_engine: Engine | None = None

    try:
        admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")

        with admin_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:

        return False
    else:

        return True
    finally:

        if admin_engine is not None:
            admin_engine.dispose()


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for account tests")
class AccountProfileKeyTests(unittest.TestCase):
    """An admin can store the profile key. The route does not call Ayrshare."""

    engine: Engine
    database_name: str

    @classmethod
    def setUpClass(cls) -> None:
        """Migrate a throwaway database."""

        cls.database_name = f"twerva_acct_{uuid.uuid4().hex[:10]}"
        database_url: str = (
            "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/"
            f"{cls.database_name}"
        )
        previous_database_url: str | None = os.environ.get("DATABASE_URL")
        admin_engine: Engine = create_engine(
            ADMIN_DATABASE_URL,
            isolation_level="AUTOCOMMIT",
        )

        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{cls.database_name}"'))

        os.environ["DATABASE_URL"] = database_url
        clear_settings_cache()
        alembic_config: Config = Config(str(SERVER_ROOT / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(SERVER_ROOT / "alembic"))
        command.upgrade(alembic_config, "head")

        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

        clear_settings_cache()
        cls.engine = create_engine(database_url)
        cls.admin_engine = admin_engine

    @classmethod
    def tearDownClass(cls) -> None:
        """Drop the throwaway database."""

        if getattr(cls, "engine", None) is not None:
            cls.engine.dispose()

        admin_engine: Engine | None = getattr(cls, "admin_engine", None)

        if admin_engine is None:

            return

        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": cls.database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{cls.database_name}"'))

        admin_engine.dispose()

    def setUp(self) -> None:
        """Open a session."""

        self.session: Session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        """Close the session."""

        self.session.close()

    def test_admin_patch_stores_the_stripped_key(self) -> None:
        """PATCH stores the stripped profile key and returns it in full."""

        created: AccountReadResponse = _create_account(self.session, "patch_key")
        updated: AccountReadResponse = patch_account_profile_key(
            created.id,
            AccountProfileKeyPatchRequest(external_account_id="  profile-key  "),
            self.session,
        )
        stored: Account | None = self.session.get(Account, created.id)

        self.assertEqual(updated.external_account_id, "profile-key")
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.external_account_id, "profile-key")
        self.assertNotIn("AYRSHARE_API_KEY", updated.model_dump().values())
        self.assertEqual(updated.platform, Platform.INSTAGRAM)
        self.assertEqual(updated.handle, created.handle)

    def test_a_blank_patch_stores_null(self) -> None:
        """Null, spaces, and an empty string all store null."""

        created: AccountReadResponse = _create_account(self.session, "blank_key")
        patch_account_profile_key(
            created.id,
            AccountProfileKeyPatchRequest(external_account_id=PROFILE_KEY),
            self.session,
        )

        for blank_value in ("", "   ", None):
            cleared: AccountReadResponse = patch_account_profile_key(
                created.id,
                AccountProfileKeyPatchRequest(external_account_id=blank_value),
                self.session,
            )
            stored: Account | None = self.session.get(Account, created.id)

            self.assertIsNone(cleared.external_account_id)
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertIsNone(stored.external_account_id)

    def test_an_unknown_account_is_404(self) -> None:
        """PATCH of a missing id is 404 and writes nothing."""

        with self.assertRaises(HTTPException) as raised:
            patch_account_profile_key(
                uuid.uuid4(),
                AccountProfileKeyPatchRequest(external_account_id=PROFILE_KEY),
                self.session,
            )

        self.assertEqual(raised.exception.status_code, 404)

    def test_create_with_the_field_set_returns_it(self) -> None:
        """Create returns the profile key that was sent."""

        created: AccountReadResponse = _create_account(
            self.session,
            "created_key",
            PROFILE_KEY,
        )

        self.assertEqual(created.external_account_id, PROFILE_KEY)
        stored: Account | None = self.session.get(Account, created.id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.external_account_id, PROFILE_KEY)

    def test_patch_does_not_accept_other_account_fields(self) -> None:
        """Platform, handle, cluster, and cadence are not part of this body."""

        with self.assertRaises(ValidationError):
            AccountProfileKeyPatchRequest.model_validate(
                {
                    "external_account_id": PROFILE_KEY,
                    "platform": "tiktok",
                    "handle": "other",
                    "cluster_id": str(uuid.uuid4()),
                    "cadence_cap_per_day": 3,
                },
            )

    def test_mock_connection_check_does_not_call_ayrshare(self) -> None:
        """The mock adapter returns ok and does not change the profile key."""

        previous_adapter: str | None = os.environ.get("PUBLISH_ADAPTER")
        os.environ["PUBLISH_ADAPTER"] = "mock"
        clear_settings_cache()
        created: AccountReadResponse = _create_account(self.session, "mock_check", PROFILE_KEY)

        try:
            connection = read_account_connection(created.id, self.session, None)
            stored: Account | None = self.session.get(Account, created.id)
        finally:

            if previous_adapter is None:
                os.environ.pop("PUBLISH_ADAPTER", None)
            else:
                os.environ["PUBLISH_ADAPTER"] = previous_adapter

            clear_settings_cache()

        self.assertEqual(connection.adapter, "mock")
        self.assertTrue(connection.ok)
        self.assertEqual(connection.detail, MOCK_CONNECTION_DETAIL)
        self.assertNotIn(PROFILE_KEY, connection.detail)
        self.assertNotIn("AYRSHARE_API_KEY", connection.detail)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.external_account_id, PROFILE_KEY)

    def test_a_vendor_401_returns_ok_false_and_keeps_the_profile_key(self) -> None:
        """Ayrshare 401 is ok false. The stored profile key is unchanged."""

        created: AccountReadResponse = _create_account(self.session, "vendor_401", PROFILE_KEY)
        recorded_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:

            recorded_requests.append(request)

            return httpx.Response(
                401,
                json={"message": f"bad {AYRSHARE_TEST_API_KEY} for {PROFILE_KEY}"},
            )

        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with patch("app.api.v1.accounts.get_publish_adapter", return_value=adapter):
            connection = read_account_connection(created.id, self.session, None)

        stored: Account | None = self.session.get(Account, created.id)
        post_requests: list[httpx.Request] = [
            request for request in recorded_requests if request.method == "POST"
        ]

        self.assertFalse(connection.ok)
        self.assertEqual(connection.adapter, "ayrshare")
        self.assertEqual(len(recorded_requests), 1)
        self.assertEqual(recorded_requests[0].method, "GET")
        self.assertEqual(post_requests, [])
        self.assertNotIn(AYRSHARE_TEST_API_KEY, connection.detail)
        self.assertNotIn(PROFILE_KEY, connection.detail)
        self.assertNotIn("AYRSHARE_API_KEY", connection.detail)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.external_account_id, PROFILE_KEY)

    def test_a_blank_api_key_is_409_and_ok_false(self) -> None:
        """Selecting ayrshare without a key does not post."""

        created: AccountReadResponse = _create_account(self.session, "blank_api_key")
        previous_adapter: str | None = os.environ.get("PUBLISH_ADAPTER")
        previous_key: str | None = os.environ.get("AYRSHARE_API_KEY")
        os.environ["PUBLISH_ADAPTER"] = "ayrshare"
        os.environ["AYRSHARE_API_KEY"] = ""
        clear_settings_cache()

        try:
            response = read_account_connection(created.id, self.session, None)
        finally:

            if previous_adapter is None:
                os.environ.pop("PUBLISH_ADAPTER", None)
            else:
                os.environ["PUBLISH_ADAPTER"] = previous_adapter

            if previous_key is None:
                os.environ.pop("AYRSHARE_API_KEY", None)
            else:
                os.environ["AYRSHARE_API_KEY"] = previous_key

            clear_settings_cache()

        self.assertEqual(response.status_code, 409)
        body: dict[str, object] = json.loads(response.body)
        self.assertEqual(body["ok"], False)
        self.assertNotIn("AYRSHARE_API_KEY", response.body.decode("utf-8"))
        self.assertNotIn(PROFILE_KEY, response.body.decode("utf-8"))


class AccountProfileKeyRouteTests(unittest.TestCase):
    """A reader cannot PATCH. The check is the existing cookie rule."""

    def test_a_reader_is_rejected(self) -> None:
        """A reader PATCH is 403 and does not need a real account row."""

        previous_secret: str | None = os.environ.get("SESSION_SECRET")
        previous_secure: str | None = os.environ.get("SESSION_COOKIE_SECURE")
        os.environ["SESSION_SECRET"] = "test-session-secret-not-for-production"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        clear_settings_cache()
        client: TestClient = _reader_client()
        login = client.post(
            "/api/v1/auth/login",
            json={"username": READER_USERNAME, "password": READER_PASSWORD},
        )

        try:
            response = client.patch(
                f"/api/v1/accounts/{uuid.uuid4()}",
                json={"external_account_id": PROFILE_KEY},
            )
        finally:
            client.close()

            if previous_secret is None:
                os.environ.pop("SESSION_SECRET", None)
            else:
                os.environ["SESSION_SECRET"] = previous_secret

            if previous_secure is None:
                os.environ.pop("SESSION_COOKIE_SECURE", None)
            else:
                os.environ["SESSION_COOKIE_SECURE"] = previous_secure

            clear_settings_cache()

        self.assertEqual(login.status_code, 200)
        self.assertEqual(response.status_code, 403)
        self.assertIn("read-only", response.json()["detail"].lower())
        self.assertNotIn(PROFILE_KEY, response.text)

    def test_a_reader_cannot_check_the_connection(self) -> None:
        """A reader GET of the connection route is rejected."""

        previous_secret: str | None = os.environ.get("SESSION_SECRET")
        previous_secure: str | None = os.environ.get("SESSION_COOKIE_SECURE")
        os.environ["SESSION_SECRET"] = "test-session-secret-not-for-production"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        clear_settings_cache()
        client: TestClient = _reader_client()
        login = client.post(
            "/api/v1/auth/login",
            json={"username": READER_USERNAME, "password": READER_PASSWORD},
        )

        try:
            response = client.get(f"/api/v1/accounts/{uuid.uuid4()}/connection")
        finally:
            client.close()

            if previous_secret is None:
                os.environ.pop("SESSION_SECRET", None)
            else:
                os.environ["SESSION_SECRET"] = previous_secret

            if previous_secure is None:
                os.environ.pop("SESSION_COOKIE_SECURE", None)
            else:
                os.environ["SESSION_COOKIE_SECURE"] = previous_secure

            clear_settings_cache()

        self.assertEqual(login.status_code, 200)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("AYRSHARE_API_KEY", response.text)
        self.assertNotIn(PROFILE_KEY, response.text)


def _create_account(
    session: Session,
    handle: str,
    external_account_id: str | None = None,
) -> AccountReadResponse:
    """Create a brand, a cluster, and one Instagram account."""

    suffix: str = uuid.uuid4().hex[:8]
    created_brand = create_brand(
        BrandCreateRequest(slug=f"brand-{suffix}", name=f"Brand {suffix}"),
        session,
    )
    created_cluster = create_cluster(
        ClusterCreateRequest(
            brand_id=created_brand.id,
            slug=f"cluster-{suffix}",
            name=f"Cluster {suffix}",
        ),
        session,
    )
    created_account: AccountReadResponse = create_account(
        AccountCreateRequest(
            cluster_id=created_cluster.id,
            platform=Platform.INSTAGRAM,
            handle=f"{handle}_{suffix}",
            external_account_id=external_account_id,
        ),
        session,
    )

    return created_account


def _reader_client() -> TestClient:
    """Sign-in client whose only user is a reader."""

    now: datetime = datetime.now(timezone.utc)
    reader: OpsUser = OpsUser(
        id=uuid.uuid4(),
        username=READER_USERNAME,
        password_hash=hash_plain_password(READER_PASSWORD),
        role=OpsUserRole.READER,
        created_at=now,
        updated_at=now,
    )

    class _ReaderSession:
        """Session that can only find the reader."""

        def get(self, model: type[object], row_id: uuid.UUID) -> object | None:

            if model is OpsUser and row_id == reader.id:

                return reader

            return None

        def scalars(self, statement: object) -> object:

            matched: list[OpsUser] = []

            if "ops_users" in str(statement):
                matched = [reader]

            class _Rows:
                def __init__(self, rows: list[OpsUser]) -> None:

                    self._rows: list[OpsUser] = rows

                def first(self) -> OpsUser | None:

                    if len(self._rows) == 0:

                        return None

                    return self._rows[0]

            return _Rows(matched)

    application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield _ReaderSession()  # type: ignore[misc]

    application.dependency_overrides[get_our_database_session] = override_database_session
    application.include_router(api_v1_router)

    return TestClient(application)


if __name__ == "__main__":
    unittest.main()
