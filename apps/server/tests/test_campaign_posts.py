"""Place an assembled carousel on a campaign timeline."""

import os
import unittest
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

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
from app.api.v1.campaign_posts import place_campaign_post_by_id
from app.api.v1.campaigns import (
    create_campaign,
    pause_campaign_by_id,
    start_campaign_by_id,
)
from app.api.v1.carousel_writes import create_carousel
from app.api.v1.clusters import create_cluster
from app.api.v1.artifacts import create_artifact
from app.api.v1.post_jobs import create_post_job
from app.api.v1.router import api_v1_router
from app.api.v1.schemas import (
    AccountCreateRequest,
    ArtifactCreateRequest,
    BrandCreateRequest,
    CampaignCreateRequest,
    CampaignPostCreateRequest,
    CampaignPostRead,
    ClusterCreateRequest,
    PostJobCreateRequest,
    CarouselCreateRequest,
    SkeletonCreateRequest,
)
from app.api.v1.skeletons import create_skeleton
from app.auth.passwords import hash_plain_password
from app.campaigns.posts import (
    ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL,
    CAMPAIGN_POST_ACCOUNT_DETAIL,
    CAMPAIGN_POST_BLOCKED_DETAIL,
    CAMPAIGN_POST_DUPLICATE_DETAIL,
    CAMPAIGN_POST_NEEDS_CAROUSEL_DETAIL,
)
from app.db import get_our_database_session
from app.models.artifact import Artifact
from app.models.campaign import Campaign, CampaignPost
from app.models.campaign import CampaignCarousel
from app.models.carousel import (
    AssembledCarousel,
    AssembledCarouselFrame,
    CarouselAssembly,
    CarouselGeneration,
)
from app.models.enums import (
    ArtifactStatus,
    CampaignType,
    OpsUserRole,
    Platform,
    PostJobStatus,
)
from app.models.ops_user import OpsUser
from app.models.post_job import PostJob
from app.settings import clear_settings_cache
from tests.test_api_routes import _openapi_methods_by_path


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
SCHEDULED_FOR: datetime = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
READER_USERNAME: str = "reader-agent"
READER_PASSWORD: str = "correct-horse-battery"


@dataclass
class _TimelineWorld:
    """Ids for one campaign and the assembled carousels a test can place."""

    campaign_id: uuid.UUID
    carousel_name: str
    generation_number: int
    open_account_id: uuid.UUID
    capped_account_id: uuid.UUID
    unlinked_account_id: uuid.UUID
    brand_id: uuid.UUID
    happy_assembled_id: uuid.UUID
    happy_early_frame_id: uuid.UUID
    happy_late_frame_id: uuid.UUID
    duplicate_assembled_id: uuid.UUID
    blocked_assembled_id: uuid.UUID
    cap_job_assembled_id: uuid.UUID
    cap_first_assembled_id: uuid.UUID
    cap_second_assembled_id: uuid.UUID
    null_first_assembled_id: uuid.UUID
    null_second_assembled_id: uuid.UUID
    pause_assembled_id: uuid.UUID
    foreign_assembled_id: uuid.UUID


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


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for campaign post tests")
class CampaignPostPlacementTests(unittest.TestCase):
    """An admin can put one unblocked assembled carousel on the timeline."""

    engine: Engine
    database_name: str
    world: _TimelineWorld

    @classmethod
    def setUpClass(cls) -> None:
        """Migrate a throwaway database and seed one campaign."""

        cls.database_name = f"twerva_place_{uuid.uuid4().hex[:10]}"
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
        session: Session = sessionmaker(bind=cls.engine)()

        try:
            cls.world = _build_world(session)
        finally:
            session.close()

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
        """Open a session on the seeded database."""

        self.session: Session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        """Close the session."""

        self.session.close()

    def test_admin_places_an_unblocked_carousel(self) -> None:
        """The post is upcoming, caption is the carousel name, and frames stay in order."""

        before_artifacts: int = _row_count(self.session, Artifact)
        before_post_jobs: int = _row_count(self.session, PostJob)
        before_campaign_carousels: int = _row_count(self.session, CampaignCarousel)
        placed = _place(
            self.session,
            self.world.campaign_id,
            self.world.happy_assembled_id,
            self.world.open_account_id,
        )

        self.assertEqual(placed.status, "upcoming")
        self.assertEqual(placed.caption, self.world.carousel_name)
        self.assertIsNone(placed.cta_url)
        self.assertIsNone(placed.published_at)
        self.assertIsNone(placed.platform_post_id)
        self.assertIsNone(placed.platform_post_url)
        self.assertIsNone(placed.last_error)
        self.assertFalse(placed.blocked)
        self.assertEqual(placed.generation_number, self.world.generation_number)
        self.assertEqual(placed.platform, Platform.INSTAGRAM)
        self.assertEqual(
            [frame.id for frame in placed.frames],
            [self.world.happy_early_frame_id, self.world.happy_late_frame_id],
        )
        self.assertEqual([frame.position for frame in placed.frames], [0, 1])
        self.assertEqual(_row_count(self.session, Artifact), before_artifacts)
        self.assertEqual(_row_count(self.session, PostJob), before_post_jobs)
        self.assertEqual(
            _row_count(self.session, CampaignCarousel),
            before_campaign_carousels,
        )

    def test_a_blocked_carousel_stores_nothing(self) -> None:
        """A blocked frame refuses the post and leaves the table unchanged."""

        before_posts: int = _row_count(self.session, CampaignPost)

        with self.assertRaises(HTTPException) as raised_http:
            _place(
                self.session,
                self.world.campaign_id,
                self.world.blocked_assembled_id,
                self.world.open_account_id,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, CAMPAIGN_POST_BLOCKED_DETAIL)
        self.assertEqual(_row_count(self.session, CampaignPost), before_posts)

    def test_the_same_pair_is_rejected(self) -> None:
        """A second post for the same carousel and account is 409."""

        _place(
            self.session,
            self.world.campaign_id,
            self.world.duplicate_assembled_id,
            self.world.open_account_id,
        )
        before_posts: int = _row_count(self.session, CampaignPost)

        with self.assertRaises(HTTPException) as raised_http:
            _place(
                self.session,
                self.world.campaign_id,
                self.world.duplicate_assembled_id,
                self.world.open_account_id,
            )

        self.assertEqual(raised_http.exception.status_code, 409)
        self.assertEqual(raised_http.exception.detail, CAMPAIGN_POST_DUPLICATE_DETAIL)
        self.assertEqual(_row_count(self.session, CampaignPost), before_posts)

    def test_an_unlinked_account_is_rejected(self) -> None:
        """An account that is not on the campaign cannot take the post."""

        before_posts: int = _row_count(self.session, CampaignPost)

        with self.assertRaises(HTTPException) as raised_http:
            _place(
                self.session,
                self.world.campaign_id,
                self.world.happy_assembled_id,
                self.world.unlinked_account_id,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, CAMPAIGN_POST_ACCOUNT_DETAIL)
        self.assertEqual(_row_count(self.session, CampaignPost), before_posts)

    def test_a_campaign_without_a_carousel_is_rejected(self) -> None:
        """A null carousel id is 400 and stores nothing."""

        bare_campaign_id: uuid.UUID = _campaign_without_carousel(
            self.session,
            self.world.open_account_id,
        )
        before_posts: int = _row_count(self.session, CampaignPost)

        with self.assertRaises(HTTPException) as raised_http:
            _place(
                self.session,
                bare_campaign_id,
                self.world.happy_assembled_id,
                self.world.open_account_id,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            CAMPAIGN_POST_NEEDS_CAROUSEL_DETAIL,
        )
        self.assertEqual(_row_count(self.session, CampaignPost), before_posts)

    def test_another_carousels_assembly_is_not_found(self) -> None:
        """An assembled carousel from a different carousel is 404."""

        with self.assertRaises(HTTPException) as raised_http:
            _place(
                self.session,
                self.world.campaign_id,
                self.world.foreign_assembled_id,
                self.world.open_account_id,
            )

        self.assertEqual(raised_http.exception.status_code, 404)
        self.assertEqual(
            raised_http.exception.detail,
            ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL,
        )

    def test_a_post_job_fills_the_cap(self) -> None:
        """A non-failed post job on that UTC day blocks the new post."""

        create_post_job(
            PostJobCreateRequest(
                artifact_id=_artifact_id(self.session, self.world.brand_id),
                account_id=self.world.capped_account_id,
                status=PostJobStatus.SCHEDULED,
                scheduled_for=SCHEDULED_FOR,
            ),
            self.session,
        )
        before_posts: int = _row_count(self.session, CampaignPost)

        with self.assertRaises(HTTPException) as raised_http:
            _place(
                self.session,
                self.world.campaign_id,
                self.world.cap_job_assembled_id,
                self.world.capped_account_id,
            )

        self.assertEqual(raised_http.exception.status_code, 409)
        self.assertIn("Cadence cap exceeded", str(raised_http.exception.detail))
        self.assertIn(
            "post_jobs and campaign posts",
            str(raised_http.exception.detail),
        )
        self.assertEqual(_row_count(self.session, CampaignPost), before_posts)

    def test_a_second_campaign_post_fills_the_cap(self) -> None:
        """Cap 1 allows one campaign post and refuses the next on that day."""

        second_capped_account_id: uuid.UUID = _extra_capped_account(self.session)
        _link_account(self.session, self.world.campaign_id, second_capped_account_id)
        _place(
            self.session,
            self.world.campaign_id,
            self.world.cap_first_assembled_id,
            second_capped_account_id,
        )

        with self.assertRaises(HTTPException) as raised_http:
            _place(
                self.session,
                self.world.campaign_id,
                self.world.cap_second_assembled_id,
                second_capped_account_id,
            )

        self.assertEqual(raised_http.exception.status_code, 409)
        self.assertIn("Cadence cap exceeded", str(raised_http.exception.detail))

    def test_a_null_cap_allows_a_post_job_and_two_posts(self) -> None:
        """A null cap does not block a post job or a second campaign post."""

        create_post_job(
            PostJobCreateRequest(
                artifact_id=_artifact_id(self.session, self.world.brand_id),
                account_id=self.world.open_account_id,
                status=PostJobStatus.SCHEDULED,
                scheduled_for=SCHEDULED_FOR,
            ),
            self.session,
        )
        first = _place(
            self.session,
            self.world.campaign_id,
            self.world.null_first_assembled_id,
            self.world.open_account_id,
        )
        second = _place(
            self.session,
            self.world.campaign_id,
            self.world.null_second_assembled_id,
            self.world.open_account_id,
        )

        self.assertEqual(first.status, "upcoming")
        self.assertEqual(second.status, "upcoming")

    def test_a_paused_campaign_can_take_a_post(self) -> None:
        """Start and pause do not gate the timeline."""

        start_campaign_by_id(self.world.campaign_id, self.session)
        paused = pause_campaign_by_id(self.world.campaign_id, self.session)
        placed = _place(
            self.session,
            self.world.campaign_id,
            self.world.pause_assembled_id,
            self.world.open_account_id,
        )

        self.assertEqual(paused.status.value, "paused")
        self.assertEqual(placed.status, "upcoming")


class CampaignPostRouteTests(unittest.TestCase):
    """The new route stays on the API, and a reader cannot call it."""

    def test_generate_carousel_route_stays_registered(self) -> None:
        """The old generate route and the new post route are both registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)

        self.assertIn("post", methods_by_path["/api/v1/generate/carousel"])
        self.assertIn("post", methods_by_path["/api/v1/campaigns/{campaign_id}/posts"])

    def test_a_reader_is_rejected(self) -> None:
        """A reader cannot place a post."""

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
            response = client.post(
                f"/api/v1/campaigns/{uuid.uuid4()}/posts",
                json={
                    "assembled_carousel_id": str(uuid.uuid4()),
                    "account_id": str(uuid.uuid4()),
                    "scheduled_for": "2026-11-13T15:00:00Z",
                },
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


def _place(
    session: Session,
    campaign_id: uuid.UUID,
    assembled_carousel_id: uuid.UUID,
    account_id: uuid.UUID,
) -> CampaignPostRead:
    """Call the place route and return the read model."""

    placed = place_campaign_post_by_id(
        campaign_id,
        CampaignPostCreateRequest(
            assembled_carousel_id=assembled_carousel_id,
            account_id=account_id,
            scheduled_for=SCHEDULED_FOR,
        ),
        session,
        None,
    )

    return placed


def _row_count(session: Session, model: type[object]) -> int:
    """Return how many rows of one model the session can see."""

    row_count: int = int(
        session.scalar(select(func.count()).select_from(model)),
    )

    return row_count


def _build_world(session: Session) -> _TimelineWorld:
    """Seed a campaign, two accounts, and the assembled carousels the tests use."""

    suffix: str = uuid.uuid4().hex[:8]
    created_brand = create_brand(
        BrandCreateRequest(slug=f"place-{suffix}", name="Place brand"),
        session,
    )
    created_cluster = create_cluster(
        ClusterCreateRequest(
            brand_id=created_brand.id,
            slug=f"place-lane-{suffix}",
            name="Place lane",
        ),
        session,
    )
    open_account = create_account(
        AccountCreateRequest(
            cluster_id=created_cluster.id,
            platform=Platform.INSTAGRAM,
            handle=f"open_{suffix}",
            cadence_cap_per_day=None,
        ),
        session,
    )
    capped_account = create_account(
        AccountCreateRequest(
            cluster_id=created_cluster.id,
            platform=Platform.INSTAGRAM,
            handle=f"capped_{suffix}",
            cadence_cap_per_day=1,
        ),
        session,
    )
    unlinked_account = create_account(
        AccountCreateRequest(
            cluster_id=created_cluster.id,
            platform=Platform.INSTAGRAM,
            handle=f"unlinked_{suffix}",
            cadence_cap_per_day=None,
        ),
        session,
    )
    created_skeleton = create_skeleton(
        SkeletonCreateRequest(name=f"Place skeleton {suffix}"),
        session,
        None,
    )
    created_carousel = create_carousel(
        CarouselCreateRequest(
            name=f"Place carousel {suffix}",
            skeleton_id=created_skeleton.id,
        ),
        session,
        None,
    )
    foreign_carousel = create_carousel(
        CarouselCreateRequest(
            name=f"Other carousel {suffix}",
            skeleton_id=created_skeleton.id,
        ),
        session,
        None,
    )
    created_campaign = create_campaign(
        CampaignCreateRequest(
            name=f"Place campaign {suffix}",
            campaign_type=CampaignType.SPOTMU,
            skeleton_id=created_skeleton.id,
            carousel_id=created_carousel.id,
            platforms=[Platform.INSTAGRAM],
            account_ids=[open_account.id, capped_account.id],
            interests=[],
        ),
        session,
        None,
    )
    generation: CarouselGeneration = session.scalars(
        select(CarouselGeneration).where(
            CarouselGeneration.carousel_id == created_carousel.id,
        ),
    ).one()
    foreign_generation: CarouselGeneration = session.scalars(
        select(CarouselGeneration).where(
            CarouselGeneration.carousel_id == foreign_carousel.id,
        ),
    ).one()
    assembly: CarouselAssembly = _store_assembly_header(
        session,
        created_carousel.id,
        generation,
    )
    foreign_assembly: CarouselAssembly = _store_assembly_header(
        session,
        foreign_carousel.id,
        foreign_generation,
    )
    early_frame_id: uuid.UUID = uuid.uuid4()
    late_frame_id: uuid.UUID = uuid.uuid4()
    happy_assembled_id: uuid.UUID = _store_group(
        session,
        assembly.id,
        0,
        created_carousel.name,
        [
            (late_frame_id, 1, False),
            (early_frame_id, 0, False),
        ],
    )
    world: _TimelineWorld = _TimelineWorld(
        campaign_id=created_campaign.id,
        carousel_name=created_carousel.name,
        generation_number=generation.generation_number,
        open_account_id=open_account.id,
        capped_account_id=capped_account.id,
        unlinked_account_id=unlinked_account.id,
        brand_id=created_brand.id,
        happy_assembled_id=happy_assembled_id,
        happy_early_frame_id=early_frame_id,
        happy_late_frame_id=late_frame_id,
        duplicate_assembled_id=_store_group(
            session,
            assembly.id,
            1,
            created_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
        blocked_assembled_id=_store_group(
            session,
            assembly.id,
            2,
            created_carousel.name,
            [(uuid.uuid4(), 0, True)],
        ),
        cap_job_assembled_id=_store_group(
            session,
            assembly.id,
            3,
            created_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
        cap_first_assembled_id=_store_group(
            session,
            assembly.id,
            4,
            created_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
        cap_second_assembled_id=_store_group(
            session,
            assembly.id,
            5,
            created_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
        null_first_assembled_id=_store_group(
            session,
            assembly.id,
            6,
            created_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
        null_second_assembled_id=_store_group(
            session,
            assembly.id,
            7,
            created_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
        pause_assembled_id=_store_group(
            session,
            assembly.id,
            8,
            created_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
        foreign_assembled_id=_store_group(
            session,
            foreign_assembly.id,
            0,
            foreign_carousel.name,
            [(uuid.uuid4(), 0, False)],
        ),
    )

    return world


def _store_assembly_header(
    session: Session,
    carousel_id: uuid.UUID,
    generation: CarouselGeneration,
) -> CarouselAssembly:
    """Insert the one assembly row a generation can hold."""

    assembly: CarouselAssembly = CarouselAssembly(
        id=uuid.uuid4(),
        carousel_id=carousel_id,
        generation_number=generation.generation_number,
        generation_id=generation.id,
        slide_count=5,
    )
    session.add(assembly)
    session.commit()

    return assembly


def _store_group(
    session: Session,
    assembly_id: uuid.UUID,
    position: int,
    caption: str,
    frames: list[tuple[uuid.UUID, int, bool]],
) -> uuid.UUID:
    """Insert one assembled carousel and return its id."""

    assembled: AssembledCarousel = AssembledCarousel(
        id=uuid.uuid4(),
        assembly_id=assembly_id,
        position=position,
        status="draft",
        caption=caption,
        cta_url=None,
    )
    session.add(assembled)
    session.flush()

    for frame_id, frame_position, blocked in frames:
        frame: AssembledCarouselFrame = AssembledCarouselFrame(
            id=frame_id,
            assembled_carousel_id=assembled.id,
            position=frame_position,
            asset_ref=f"assembled/{assembly_id}/{frame_id}.png",
            blocked=blocked,
            block_reason="missing_asset" if blocked else None,
            block_detail="Missing file." if blocked else None,
        )
        session.add(frame)

    session.commit()

    return assembled.id


def _campaign_without_carousel(session: Session, account_id: uuid.UUID) -> uuid.UUID:
    """Create a campaign and then clear its carousel pointer."""

    suffix: str = uuid.uuid4().hex[:8]
    created_skeleton = create_skeleton(
        SkeletonCreateRequest(name=f"Bare skeleton {suffix}"),
        session,
        None,
    )
    created_carousel = create_carousel(
        CarouselCreateRequest(
            name=f"Bare carousel {suffix}",
            skeleton_id=created_skeleton.id,
        ),
        session,
        None,
    )
    created_campaign = create_campaign(
        CampaignCreateRequest(
            name=f"Bare campaign {suffix}",
            campaign_type=CampaignType.SPOTMU,
            skeleton_id=created_skeleton.id,
            carousel_id=created_carousel.id,
            platforms=[Platform.INSTAGRAM],
            account_ids=[account_id],
            interests=[],
        ),
        session,
        None,
    )
    stored_campaign: Campaign | None = session.get(Campaign, created_campaign.id)

    if stored_campaign is None:
        raise AssertionError("Campaign was not stored.")

    stored_campaign.carousel_id = None
    session.commit()

    return stored_campaign.id


def _extra_capped_account(session: Session) -> uuid.UUID:
    """Add one more account with a cap of 1 on the seeded brand's cluster."""

    from app.models.account import Account

    existing_account: Account | None = session.get(Account, CampaignPostPlacementTests.world.capped_account_id)

    if existing_account is None:
        raise AssertionError("Capped account was not stored.")

    suffix: str = uuid.uuid4().hex[:8]
    created_account = create_account(
        AccountCreateRequest(
            cluster_id=existing_account.cluster_id,
            platform=Platform.INSTAGRAM,
            handle=f"second_cap_{suffix}",
            cadence_cap_per_day=1,
        ),
        session,
    )

    return created_account.id


def _link_account(session: Session, campaign_id: uuid.UUID, account_id: uuid.UUID) -> None:
    """Attach an account that was created after the campaign."""

    from app.models.campaign import CampaignAccount

    session.add(CampaignAccount(campaign_id=campaign_id, account_id=account_id))
    session.commit()


def _artifact_id(session: Session, brand_id: uuid.UUID) -> uuid.UUID:
    """Store one draft artifact the cadence post job can point at."""

    created_artifact = create_artifact(
        ArtifactCreateRequest(
            brand_id=brand_id,
            status=ArtifactStatus.DRAFT,
            caption="Old queue",
        ),
        session,
    )

    return created_artifact.id


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

                def all(self) -> list[OpsUser]:
                    return list(self._rows)

            return _Rows(matched)

    application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield _ReaderSession()  # type: ignore[misc]

    application.dependency_overrides[get_our_database_session] = override_database_session
    application.include_router(api_v1_router)

    return TestClient(application)


if __name__ == "__main__":
    unittest.main()
