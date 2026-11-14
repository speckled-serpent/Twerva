"""Campaign create validation, plus attach and detach against Postgres."""

import os
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("TWERVA_ENV", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.accounts import create_account
from app.api.v1.brands import create_brand
from app.api.v1.campaigns import (
    CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL,
    CAMPAIGN_ACCOUNT_ALREADY_LINKED_DETAIL,
    CAMPAIGN_ACCOUNT_STAYS_DETAIL,
    CAMPAIGN_NAME_REQUIRED_DETAIL,
    CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
    DUPLICATE_ACCOUNT_PLATFORM_DETAIL,
    attach_campaign_account,
    create_campaign,
    detach_campaign_account,
)
from app.api.v1.carousel_writes import create_carousel
from app.api.v1.clusters import create_cluster
from app.api.v1.router import api_v1_router
from app.api.v1.skeletons import create_skeleton
from app.auth.passwords import hash_plain_password
from app.db import get_our_database_session
from app.models.account import Account
from app.models.campaign import CampaignAccount, CampaignPost
from app.models.carousel import AssembledCarousel, CarouselAssembly, CarouselGeneration
from app.models.enums import OpsUserRole
from app.models.ops_user import OpsUser
from app.settings import clear_settings_cache
from app.models.campaign import CampaignInterest
from app.api.v1.schemas import (
    AccountCreateRequest,
    BrandCreateRequest,
    CampaignAccountAttachRequest,
    CampaignCreateRequest,
    CampaignInterestWrite,
    CampaignReadResponse,
    CarouselCreateRequest,
    ClusterCreateRequest,
    SkeletonCreateRequest,
)
from app.models.enums import (
    AdvertisementType,
    CampaignStatus,
    CampaignType,
    Platform,
)


class CampaignCreateValidationTests(unittest.TestCase):
    """Spotmu create rejects incomplete bodies before any write."""

    def test_other_campaign_type_is_rejected(self) -> None:
        """POST body with `other` returns HTTP 400 and does not persist."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = CampaignCreateRequest(
            name="Later",
            campaign_type=CampaignType.OTHER,
            advertisement_type=AdvertisementType.CAROUSEL,
            skeleton_id=uuid.uuid4(),
            carousel_id=uuid.uuid4(),
        )

        with self.assertRaises(HTTPException) as raised_http:
            create_campaign(
                campaign_create_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertIn("not implemented", str(raised_http.exception.detail).lower())
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()

    def test_blank_campaign_name_is_rejected(self) -> None:
        """Whitespace-only name returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            name="   ",
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_NAME_REQUIRED_DETAIL,
        )

    def test_empty_platforms_are_rejected(self) -> None:
        """Spotmu create with no platforms returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            platforms=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
        )

    def test_empty_account_ids_are_rejected(self) -> None:
        """Spotmu create with no accounts returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            account_ids=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_ACCOUNTS_REQUIRED_DETAIL,
        )

    def test_spotmu_test_empty_account_ids_succeeds(self) -> None:
        """Spotmu-test create with no accounts persists a ready campaign."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            campaign_type=CampaignType.SPOTMU_TEST,
            account_ids=[],
        )
        reloaded_campaign: MagicMock = _campaign_reload_double(
            CampaignType.SPOTMU_TEST,
            campaign_create_request,
        )

        with patch(
            "app.api.v1.campaigns.resolve_campaign_binding",
            return_value=(MagicMock(), MagicMock()),
        ), patch(
            "app.api.v1.campaigns._load_taken_campaign_slugs",
            return_value=set(),
        ), patch(
            "app.api.v1.campaigns.commit_database_session_or_raise_conflict",
        ), patch(
            "app.api.v1.campaigns._load_campaign_with_joins",
            return_value=reloaded_campaign,
        ):
            campaign_read_response: CampaignReadResponse = create_campaign(
                campaign_create_request,
                fake_session,
                None,
            )

        self.assertEqual(campaign_read_response.campaign_type, CampaignType.SPOTMU_TEST)
        self.assertEqual(campaign_read_response.status, CampaignStatus.READY)
        self.assertEqual(campaign_read_response.account_count, 0)
        self.assertEqual(campaign_read_response.interest_count, 1)
        fake_session.add.assert_called()
        fake_session.flush.assert_called_once()

    def test_spotmu_test_blank_name_is_rejected(self) -> None:
        """Spotmu-test still requires a non-empty name."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            name="   ",
            campaign_type=CampaignType.SPOTMU_TEST,
            account_ids=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_NAME_REQUIRED_DETAIL,
        )

    def test_spotmu_test_empty_platforms_are_rejected(self) -> None:
        """Spotmu-test create with no platforms returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            campaign_type=CampaignType.SPOTMU_TEST,
            platforms=[],
            account_ids=[],
        )

        self._assert_create_rejected(
            campaign_create_request,
            fake_session,
            CAMPAIGN_PLATFORMS_REQUIRED_DETAIL,
        )

    def test_spotmu_test_empty_interests_are_stored_as_none(self) -> None:
        """Spotmu-test create with no interests persists an empty interest list."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            campaign_type=CampaignType.SPOTMU_TEST,
            account_ids=[],
            interests=[],
        )
        campaign_read_response: CampaignReadResponse = _create_campaign_for_test(
            campaign_create_request,
            fake_session,
            CampaignType.SPOTMU_TEST,
        )

        self.assertEqual(campaign_read_response.interest_count, 0)
        self.assertEqual(_added_interests(fake_session), [])

    def test_empty_interests_are_stored_as_none(self) -> None:
        """Spotmu create with no interests persists an empty interest list."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            interests=[],
        )
        campaign_read_response: CampaignReadResponse = _create_campaign_for_test(
            campaign_create_request,
            fake_session,
            CampaignType.SPOTMU,
        )

        self.assertEqual(campaign_read_response.status, CampaignStatus.READY)
        self.assertEqual(campaign_read_response.interest_count, 0)
        self.assertEqual(_added_interests(fake_session), [])

    def test_blank_interest_slugs_are_dropped(self) -> None:
        """Interests that strip to empty are not stored."""

        fake_session: MagicMock = MagicMock()
        campaign_create_request: CampaignCreateRequest = _spotmu_create_request(
            interests=[
                CampaignInterestWrite(slug="   ", title="Blank"),
                CampaignInterestWrite(slug="", title="Empty"),
            ],
        )
        campaign_read_response: CampaignReadResponse = _create_campaign_for_test(
            campaign_create_request,
            fake_session,
            CampaignType.SPOTMU,
        )

        self.assertEqual(campaign_read_response.status, CampaignStatus.READY)
        self.assertEqual(_added_interests(fake_session), [])

    def _assert_create_rejected(
        self,
        campaign_create_request: CampaignCreateRequest,
        fake_session: MagicMock,
        expected_detail: str,
    ) -> None:
        """Assert create raises 400 with the given detail and does not persist."""

        with self.assertRaises(HTTPException) as raised_http:
            create_campaign(
                campaign_create_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, expected_detail)
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()


def _spotmu_create_request(
    name: str = "Spring Launch",
    campaign_type: CampaignType = CampaignType.SPOTMU,
    platforms: list[Platform] | None = None,
    account_ids: list[uuid.UUID] | None = None,
    interests: list[CampaignInterestWrite] | None = None,
) -> CampaignCreateRequest:
    """Build a Spotmu-family create body with complete defaults unless overridden."""

    selected_platforms: list[Platform] = (
        [Platform.INSTAGRAM] if platforms is None else platforms
    )
    selected_account_ids: list[uuid.UUID] = (
        [uuid.uuid4()] if account_ids is None else account_ids
    )
    selected_interests: list[CampaignInterestWrite] = (
        [CampaignInterestWrite(slug="ai-agents", title="AI Agents")]
        if interests is None
        else interests
    )
    campaign_create_request: CampaignCreateRequest = CampaignCreateRequest(
        name=name,
        campaign_type=campaign_type,
        advertisement_type=AdvertisementType.CAROUSEL,
        skeleton_id=uuid.uuid4(),
        carousel_id=uuid.uuid4(),
        platforms=selected_platforms,
        account_ids=selected_account_ids,
        interests=selected_interests,
    )

    return campaign_create_request


def _create_campaign_for_test(
    campaign_create_request: CampaignCreateRequest,
    fake_session: MagicMock,
    campaign_type: CampaignType,
) -> CampaignReadResponse:
    """Run create with the account load and commit patched out."""

    linked_account: MagicMock = MagicMock()
    linked_account.platform = Platform.INSTAGRAM
    reloaded_campaign: MagicMock = _campaign_reload_double(
        campaign_type,
        campaign_create_request,
    )
    stored_interests: list[CampaignInterestWrite] = [
        interest_write
        for interest_write in campaign_create_request.interests
        if interest_write.slug.strip() != ""
    ]
    reloaded_campaign.interest_links = [
        _interest_link_double(interest_write) for interest_write in stored_interests
    ]

    with patch(
        "app.api.v1.campaigns.fetch_account_by_id_or_raise",
        return_value=linked_account,
    ), patch(
        "app.api.v1.campaigns.resolve_campaign_binding",
        return_value=(MagicMock(), MagicMock()),
    ), patch(
        "app.api.v1.campaigns._load_taken_campaign_slugs",
        return_value=set(),
    ), patch(
        "app.api.v1.campaigns.commit_database_session_or_raise_conflict",
    ), patch(
        "app.api.v1.campaigns._load_campaign_with_joins",
        return_value=reloaded_campaign,
    ):
        campaign_read_response: CampaignReadResponse = create_campaign(
            campaign_create_request,
            fake_session,
            None,
        )

    return campaign_read_response


def _interest_link_double(interest_write: CampaignInterestWrite) -> MagicMock:
    """Build one interest link the serializer can read."""

    interest_link: MagicMock = MagicMock()
    interest_link.spotmu_slug = interest_write.slug.strip()
    interest_link.title = interest_write.title
    interest_link.spotmu_interest_id = interest_write.spotmu_interest_id

    return interest_link


def _added_interests(fake_session: MagicMock) -> list[CampaignInterest]:
    """Return CampaignInterest rows passed to ``session.add``."""

    added_interests: list[CampaignInterest] = []

    for add_call in fake_session.add.call_args_list:
        added_row: object = add_call.args[0]

        if isinstance(added_row, CampaignInterest):
            added_interests.append(added_row)

    return added_interests


def _campaign_reload_double(
    campaign_type: CampaignType,
    campaign_create_request: CampaignCreateRequest,
) -> MagicMock:
    """Build a join-loaded campaign stand-in for serialize after a mocked write."""

    interest_links: list[MagicMock] = []

    for interest_write in campaign_create_request.interests:
        interest_link: MagicMock = MagicMock()
        interest_link.spotmu_slug = interest_write.slug
        interest_link.title = interest_write.title
        interest_link.spotmu_interest_id = interest_write.spotmu_interest_id
        interest_links.append(interest_link)

    now_timestamp: datetime = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    reloaded_campaign: MagicMock = MagicMock()
    reloaded_campaign.id = uuid.uuid4()
    reloaded_campaign.name = campaign_create_request.name.strip()
    reloaded_campaign.slug = "spring-launch"
    reloaded_campaign.hashtag = "#spring-launch"
    reloaded_campaign.campaign_type = campaign_type
    reloaded_campaign.advertisement_type = AdvertisementType.CAROUSEL
    reloaded_campaign.status = CampaignStatus.READY
    reloaded_campaign.platforms = [
        platform.value for platform in campaign_create_request.platforms
    ]
    reloaded_campaign.account_links = []
    reloaded_campaign.interest_links = interest_links
    reloaded_campaign.skeleton_id = campaign_create_request.skeleton_id
    reloaded_campaign.carousel_id = campaign_create_request.carousel_id
    reloaded_campaign.skeleton = None
    reloaded_campaign.carousel = None
    reloaded_campaign.carousels = []
    reloaded_campaign.posts = []
    reloaded_campaign.created_at = now_timestamp
    reloaded_campaign.updated_at = now_timestamp
    reloaded_campaign.created_by = None

    return reloaded_campaign


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
READER_USERNAME: str = "reader-agent"
READER_PASSWORD: str = "correct-horse-battery"


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


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for campaign account tests")
class CampaignAccountLinkTests(unittest.TestCase):
    """Attach and detach an account on a campaign that already exists."""

    engine: Engine
    database_name: str

    @classmethod
    def setUpClass(cls) -> None:
        """Migrate a throwaway database."""

        cls.database_name = f"twerva_link_{uuid.uuid4().hex[:10]}"
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

    def test_admin_attaches_a_matching_account(self) -> None:
        """An Instagram account joins an Instagram campaign and is listed."""

        campaign_id, instagram_account_id, _tiktok_account_id = _campaign_and_accounts(
            self.session,
        )
        before_posts: int = _post_count(self.session, campaign_id)
        attached: CampaignReadResponse = attach_campaign_account(
            campaign_id,
            CampaignAccountAttachRequest(account_id=instagram_account_id),
            self.session,
            None,
        )
        listed_ids: list[uuid.UUID] = [account.id for account in attached.accounts]

        self.assertIn(instagram_account_id, listed_ids)
        self.assertEqual(_link_count(self.session, campaign_id), 1)
        self.assertEqual(_post_count(self.session, campaign_id), before_posts)

    def test_a_tiktok_account_on_an_instagram_campaign_is_rejected(self) -> None:
        """The platform check refuses the link and leaves the count alone."""

        campaign_id, _instagram_account_id, tiktok_account_id = _campaign_and_accounts(
            self.session,
        )

        with self.assertRaises(HTTPException) as raised:
            attach_campaign_account(
                campaign_id,
                CampaignAccountAttachRequest(account_id=tiktok_account_id),
                self.session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, DUPLICATE_ACCOUNT_PLATFORM_DETAIL)
        self.assertEqual(_link_count(self.session, campaign_id), 0)

    def test_a_duplicate_attach_is_rejected(self) -> None:
        """The second link for the same pair is 409."""

        campaign_id, instagram_account_id, _tiktok_account_id = _campaign_and_accounts(
            self.session,
        )
        attach_campaign_account(
            campaign_id,
            CampaignAccountAttachRequest(account_id=instagram_account_id),
            self.session,
            None,
        )

        with self.assertRaises(HTTPException) as raised:
            attach_campaign_account(
                campaign_id,
                CampaignAccountAttachRequest(account_id=instagram_account_id),
                self.session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, CAMPAIGN_ACCOUNT_ALREADY_LINKED_DETAIL)
        self.assertEqual(_link_count(self.session, campaign_id), 1)

    def test_detach_removes_the_link_and_leaves_the_account(self) -> None:
        """The join row goes away. The account row stays."""

        campaign_id, instagram_account_id, _tiktok_account_id = _campaign_and_accounts(
            self.session,
        )
        attach_campaign_account(
            campaign_id,
            CampaignAccountAttachRequest(account_id=instagram_account_id),
            self.session,
            None,
        )
        detached: CampaignReadResponse = detach_campaign_account(
            campaign_id,
            instagram_account_id,
            self.session,
            None,
        )
        listed_ids: list[uuid.UUID] = [account.id for account in detached.accounts]
        stored_account: Account | None = self.session.get(Account, instagram_account_id)

        self.assertNotIn(instagram_account_id, listed_ids)
        self.assertEqual(_link_count(self.session, campaign_id), 0)
        self.assertIsNotNone(stored_account)

    def test_detach_is_refused_while_an_upcoming_post_uses_the_account(self) -> None:
        """The link stays when an upcoming post uses that account."""

        campaign_id, instagram_account_id, _tiktok_account_id = _campaign_and_accounts(
            self.session,
        )
        attach_campaign_account(
            campaign_id,
            CampaignAccountAttachRequest(account_id=instagram_account_id),
            self.session,
            None,
        )
        _store_upcoming_post(self.session, campaign_id, instagram_account_id)

        with self.assertRaises(HTTPException) as raised:
            detach_campaign_account(
                campaign_id,
                instagram_account_id,
                self.session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, CAMPAIGN_ACCOUNT_STAYS_DETAIL)
        self.assertEqual(_link_count(self.session, campaign_id), 1)
        self.assertIsNotNone(self.session.get(Account, instagram_account_id))


class CampaignAccountLinkRouteTests(unittest.TestCase):
    """A reader cannot attach an account."""

    def test_a_reader_is_rejected(self) -> None:
        """Attach and detach are 403 for a reader."""

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
        campaign_id: uuid.UUID = uuid.uuid4()
        account_id: uuid.UUID = uuid.uuid4()

        try:
            attach_response = client.post(
                f"/api/v1/campaigns/{campaign_id}/accounts",
                json={"account_id": str(account_id)},
            )
            detach_response = client.delete(
                f"/api/v1/campaigns/{campaign_id}/accounts/{account_id}",
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
        self.assertEqual(attach_response.status_code, 403)
        self.assertEqual(detach_response.status_code, 403)
        self.assertIn("read-only", attach_response.json()["detail"].lower())
        self.assertIn("read-only", detach_response.json()["detail"].lower())


def _campaign_and_accounts(session: Session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create an Instagram-only Spotmu test campaign and two accounts."""

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
    instagram_account = create_account(
        AccountCreateRequest(
            cluster_id=created_cluster.id,
            platform=Platform.INSTAGRAM,
            handle=f"ig_{suffix}",
        ),
        session,
    )
    tiktok_account = create_account(
        AccountCreateRequest(
            cluster_id=created_cluster.id,
            platform=Platform.TIKTOK,
            handle=f"tt_{suffix}",
        ),
        session,
    )
    created_skeleton = create_skeleton(
        SkeletonCreateRequest(name=f"Skeleton {suffix}"),
        session,
        None,
    )
    created_carousel = create_carousel(
        CarouselCreateRequest(
            name=f"Carousel {suffix}",
            skeleton_id=created_skeleton.id,
        ),
        session,
        None,
    )
    created_campaign: CampaignReadResponse = create_campaign(
        CampaignCreateRequest(
            name=f"Campaign {suffix}",
            campaign_type=CampaignType.SPOTMU_TEST,
            skeleton_id=created_skeleton.id,
            carousel_id=created_carousel.id,
            platforms=[Platform.INSTAGRAM],
            account_ids=[],
        ),
        session,
        None,
    )
    return created_campaign.id, instagram_account.id, tiktok_account.id


def _store_upcoming_post(
    session: Session,
    campaign_id: uuid.UUID,
    account_id: uuid.UUID,
) -> None:
    """Insert one upcoming post so detach has a row to refuse."""

    from app.models.campaign import Campaign

    stored_campaign: Campaign | None = session.get(Campaign, campaign_id)

    if stored_campaign is None or stored_campaign.carousel_id is None:
        raise AssertionError("Campaign carousel was not stored.")

    generation: CarouselGeneration | None = session.scalars(
        select(CarouselGeneration).where(
            CarouselGeneration.carousel_id == stored_campaign.carousel_id,
        ),
    ).first()

    if generation is None:
        raise AssertionError("Carousel generation was not stored.")

    assembly: CarouselAssembly = CarouselAssembly(
        id=uuid.uuid4(),
        carousel_id=stored_campaign.carousel_id,
        generation_number=generation.generation_number,
        generation_id=generation.id,
        slide_count=2,
    )
    session.add(assembly)
    session.flush()
    assembled: AssembledCarousel = AssembledCarousel(
        id=uuid.uuid4(),
        assembly_id=assembly.id,
        position=0,
        status="draft",
        caption="Harbor",
    )
    session.add(assembled)
    session.flush()
    session.add(
        CampaignPost(
            campaign_id=campaign_id,
            assembled_carousel_id=assembled.id,
            account_id=account_id,
            status="upcoming",
            scheduled_for=datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc),
        ),
    )
    session.commit()


def _link_count(session: Session, campaign_id: uuid.UUID) -> int:
    """Count campaign_accounts rows for one campaign."""

    link_count: int = int(
        session.scalar(
            select(func.count())
            .select_from(CampaignAccount)
            .where(CampaignAccount.campaign_id == campaign_id),
        ),
    )

    return link_count


def _post_count(session: Session, campaign_id: uuid.UUID) -> int:
    """Count campaign posts. Attach must not create one."""

    post_count: int = int(
        session.scalar(
            select(func.count())
            .select_from(CampaignPost)
            .where(CampaignPost.campaign_id == campaign_id),
        ),
    )

    return post_count


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
