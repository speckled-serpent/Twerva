"""Place an assembled carousel on a campaign timeline."""

import json
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

import httpx
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.api.v1.accounts import create_account
from app.api.v1.brands import create_brand
from app.api.v1.campaign_posts import (
    create_campaign_post_metric_snapshot,
    create_campaign_post_stub_metric_snapshot,
    place_campaign_post_by_id,
    publish_campaign_post_by_id,
    remove_campaign_post_by_id,
    reschedule_campaign_post_by_id,
    serialize_campaign_post,
)
from app.api.v1.campaigns import (
    create_campaign,
    get_campaign_by_id,
    pause_campaign_by_id,
    run_campaign,
    start_campaign_by_id,
)
from app.api.v1.carousel_assembly import assemble_carousel
from app.api.v1.carousel_writes import create_carousel, create_slide
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
    CampaignPostRescheduleRequest,
    CampaignPostRead,
    ClusterCreateRequest,
    PostJobCreateRequest,
    PostJobMetricsCreateRequest,
    CarouselCreateRequest,
    SkeletonCreateRequest,
    SlideWriteRequest,
)
from app.api.v1.skeletons import create_skeleton
from app.auth.passwords import hash_plain_password
from app.carousels.final_assembly import GENERATION_ON_TIMELINE_DETAIL
from app.campaigns.posts import list_timeline_posts
from app.campaigns.posts import (
    ASSEMBLED_CAROUSEL_NOT_FOUND_DETAIL,
    CAMPAIGN_POST_ACCOUNT_DETAIL,
    CAMPAIGN_POST_ALREADY_UP_DETAIL,
    CAMPAIGN_POST_BLOCKED_DETAIL,
    CAMPAIGN_POST_DUPLICATE_DETAIL,
    CAMPAIGN_POST_NEEDS_CAROUSEL_DETAIL,
    CAMPAIGN_POST_NOT_FOUND_DETAIL,
    CAMPAIGN_POST_ONLY_UPCOMING_DETAIL,
    CAMPAIGN_POST_STAYS_DETAIL,
)
from app.api.v1.campaign_posts import RECORD_RESULTS_AFTER_POST_DETAIL
from app.db import get_our_database_session
from app.generate.carousel import DEFAULT_HASHTAGS
from app.metrics.service import append_metric_snapshot
from app.models.account import Account
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
from app.models.metric_snapshot import MetricSnapshot
from app.models.post_job import PostJob
from app.publish.ayrshare import AyrsharePublishAdapter
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
    next_position: int

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
        cls.next_position = 20

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

    def test_moving_later_the_same_day_keeps_the_post(self) -> None:
        """Cap 1 still allows a later hour, because this post is not counted twice."""

        account_id: uuid.UUID = _extra_capped_account(self.session)
        _link_account(self.session, self.world.campaign_id, account_id)
        assembled_id: uuid.UUID = _fresh_assembled(self.session, self.world.carousel_name)
        placed = _place(
            self.session,
            self.world.campaign_id,
            assembled_id,
            account_id,
        )
        later: datetime = SCHEDULED_FOR.replace(hour=18)
        moved = reschedule_campaign_post_by_id(
            self.world.campaign_id,
            placed.id,
            CampaignPostRescheduleRequest(scheduled_for=later),
            self.session,
            None,
        )

        self.assertEqual(moved.status, "upcoming")
        self.assertEqual(moved.scheduled_for, later)
        self.assertEqual(moved.account_id, account_id)
        self.assertEqual(moved.caption, self.world.carousel_name)
        self.assertEqual(moved.frames[0].id, placed.frames[0].id)

    def test_moving_onto_a_full_day_keeps_the_old_time(self) -> None:
        """A day that already holds another post refuses the move."""

        account_id: uuid.UUID = _extra_capped_account(self.session)
        _link_account(self.session, self.world.campaign_id, account_id)
        first_id: uuid.UUID = _fresh_assembled(self.session, self.world.carousel_name)
        second_id: uuid.UUID = _fresh_assembled(self.session, self.world.carousel_name)
        placed = _place(
            self.session,
            self.world.campaign_id,
            first_id,
            account_id,
        )
        next_day: datetime = SCHEDULED_FOR + timedelta(days=1)
        _place_at(
            self.session,
            self.world.campaign_id,
            second_id,
            account_id,
            next_day,
        )

        with self.assertRaises(HTTPException) as raised_http:
            reschedule_campaign_post_by_id(
                self.world.campaign_id,
                placed.id,
                CampaignPostRescheduleRequest(scheduled_for=next_day),
                self.session,
                None,
            )

        stored_post: CampaignPost | None = self.session.get(CampaignPost, placed.id)

        self.assertEqual(raised_http.exception.status_code, 409)
        self.assertIn("Cadence cap exceeded", str(raised_http.exception.detail))
        self.assertIsNotNone(stored_post)
        assert stored_post is not None
        self.assertEqual(stored_post.scheduled_for, SCHEDULED_FOR)
        self.assertEqual(stored_post.status, "upcoming")

    def test_a_posted_row_cannot_change_its_time(self) -> None:
        """Posted and the time stay when the post is no longer upcoming."""

        placed = _place(
            self.session,
            self.world.campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
        )
        stored_post: CampaignPost | None = self.session.get(CampaignPost, placed.id)
        assert stored_post is not None
        stored_post.status = "posted"
        self.session.commit()

        with self.assertRaises(HTTPException) as raised_http:
            reschedule_campaign_post_by_id(
                self.world.campaign_id,
                placed.id,
                CampaignPostRescheduleRequest(
                    scheduled_for=SCHEDULED_FOR.replace(hour=18),
                ),
                self.session,
                None,
            )

        self.session.refresh(stored_post)
        self.assertEqual(raised_http.exception.status_code, 409)
        self.assertEqual(
            raised_http.exception.detail,
            CAMPAIGN_POST_ONLY_UPCOMING_DETAIL,
        )
        self.assertEqual(stored_post.status, "posted")
        self.assertEqual(stored_post.scheduled_for, SCHEDULED_FOR)

    def test_delete_removes_an_upcoming_post_and_leaves_the_assembly(self) -> None:
        """The assembled carousel and its frames stay after the post is removed."""

        placed = _place(
            self.session,
            self.world.campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
        )
        frame_ids: list[uuid.UUID] = [frame.id for frame in placed.frames]
        remove_campaign_post_by_id(
            self.world.campaign_id,
            placed.id,
            self.session,
            None,
        )
        remaining_frames: list[AssembledCarouselFrame] = list(
            self.session.scalars(
                select(AssembledCarouselFrame).where(
                    AssembledCarouselFrame.id.in_(frame_ids),
                ),
            ).all(),
        )

        self.assertIsNone(self.session.get(CampaignPost, placed.id))
        self.assertIsNotNone(
            self.session.get(AssembledCarousel, placed.assembled_carousel_id),
        )
        self.assertEqual(
            {frame.id for frame in remaining_frames},
            set(frame_ids),
        )

    def test_delete_of_a_posted_row_is_rejected(self) -> None:
        """A posted carousel stays on the timeline."""

        placed = _place(
            self.session,
            self.world.campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
        )
        stored_post: CampaignPost | None = self.session.get(CampaignPost, placed.id)
        assert stored_post is not None
        stored_post.status = "posted"
        self.session.commit()

        with self.assertRaises(HTTPException) as raised_http:
            remove_campaign_post_by_id(
                self.world.campaign_id,
                placed.id,
                self.session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 409)
        self.assertEqual(raised_http.exception.detail, CAMPAIGN_POST_STAYS_DETAIL)
        self.assertIsNotNone(self.session.get(CampaignPost, placed.id))

    def test_a_post_on_another_campaign_is_not_found(self) -> None:
        """Patch and delete through a different campaign id are 404."""

        placed = _place(
            self.session,
            self.world.campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
        )
        other_campaign_id: uuid.UUID = _second_campaign(
            self.session,
            self.world.open_account_id,
        )

        with self.assertRaises(HTTPException) as patch_error:
            reschedule_campaign_post_by_id(
                other_campaign_id,
                placed.id,
                CampaignPostRescheduleRequest(
                    scheduled_for=SCHEDULED_FOR.replace(hour=18),
                ),
                self.session,
                None,
            )

        with self.assertRaises(HTTPException) as delete_error:
            remove_campaign_post_by_id(
                other_campaign_id,
                placed.id,
                self.session,
                None,
            )

        self.assertEqual(patch_error.exception.status_code, 404)
        self.assertEqual(patch_error.exception.detail, CAMPAIGN_POST_NOT_FOUND_DETAIL)
        self.assertEqual(delete_error.exception.status_code, 404)
        self.assertEqual(delete_error.exception.detail, CAMPAIGN_POST_NOT_FOUND_DETAIL)
        self.assertIsNotNone(self.session.get(CampaignPost, placed.id))

    def test_publish_retries_a_missing_file_then_refuses_a_posted_row(self) -> None:
        """A missing frame fails the post. Restoring the file publishes it."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            placed = _place(
                self.session,
                self.world.campaign_id,
                _fresh_assembled(self.session, self.world.carousel_name),
                self.world.open_account_id,
            )
            before_artifacts: int = _row_count(self.session, Artifact)
            before_post_jobs: int = _row_count(self.session, PostJob)
            failed = _publish(self.session, self.world.campaign_id, placed.id)

            self.assertEqual(failed.status, "failed")
            self.assertIsNotNone(failed.last_error)
            self.assertNotEqual(failed.last_error, "")
            self.assertIsNone(failed.published_at)

            _write_frame_file(self.session, placed.frames[0].id, Path(storage.name))
            posted = _publish(self.session, self.world.campaign_id, placed.id)

            self.assertEqual(posted.status, "posted")
            self.assertEqual(
                posted.platform_post_id,
                f"mock-instagram-{placed.id}",
            )
            self.assertNotIn(self.world.carousel_name, posted.platform_post_id)
            open_account: Account | None = self.session.get(
                Account,
                self.world.open_account_id,
            )
            self.assertIsNotNone(open_account)
            assert open_account is not None
            self.assertIsNone(open_account.external_account_id)
            self.assertIsNotNone(posted.platform_post_url)
            assert posted.platform_post_url is not None
            self.assertIn("example.invalid", posted.platform_post_url)
            self.assertIsNone(posted.last_error)
            self.assertIsNotNone(posted.published_at)
            self.assertEqual(_row_count(self.session, Artifact), before_artifacts)
            self.assertEqual(_row_count(self.session, PostJob), before_post_jobs)

            with self.assertRaises(HTTPException) as raised_http:
                _publish(self.session, self.world.campaign_id, placed.id)

            self.assertEqual(raised_http.exception.status_code, 409)
            self.assertEqual(
                raised_http.exception.detail,
                CAMPAIGN_POST_ALREADY_UP_DETAIL,
            )
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def test_publish_sends_the_assembled_caption(self) -> None:
        """The Ayrshare post field is the assembled caption, with no hashtags added."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()
        named_adapter, named_requests = _recording_ayrshare_adapter()
        empty_adapter, empty_requests = _recording_ayrshare_adapter()
        open_account: Account | None = self.session.get(Account, self.world.open_account_id)
        self.assertIsNotNone(open_account)
        assert open_account is not None
        previous_profile_key: str | None = open_account.external_account_id
        open_account.external_account_id = "profile-key-for-caption"
        self.session.commit()

        try:
            named = _place(
                self.session,
                self.world.campaign_id,
                _fresh_assembled(self.session, self.world.carousel_name),
                self.world.open_account_id,
            )
            _write_frame_file(self.session, named.frames[0].id, Path(storage.name))

            with patch(
                "app.campaigns.posts.get_publish_adapter",
                return_value=named_adapter,
            ):
                posted = _publish(self.session, self.world.campaign_id, named.id)

            named_body: dict[str, object] = _ayrshare_post_body(named_requests)
            campaign: Campaign | None = self.session.get(Campaign, self.world.campaign_id)

            self.assertEqual(posted.status, "posted")
            self.assertEqual(named_body["post"], self.world.carousel_name)
            self.assertIsNotNone(campaign)
            assert campaign is not None
            self.assertNotIn(campaign.hashtag, str(named_body["post"]))

            for hashtag in DEFAULT_HASHTAGS:
                self.assertNotIn(hashtag, str(named_body["post"]))

            empty_group_id: uuid.UUID = _fresh_assembled(
                self.session,
                self.world.carousel_name,
            )
            empty_group: AssembledCarousel | None = self.session.get(
                AssembledCarousel,
                empty_group_id,
            )
            self.assertIsNotNone(empty_group)
            assert empty_group is not None
            empty_group.caption = None
            self.session.commit()
            empty = _place(
                self.session,
                self.world.campaign_id,
                empty_group_id,
                self.world.open_account_id,
            )
            _write_frame_file(self.session, empty.frames[0].id, Path(storage.name))

            with patch(
                "app.campaigns.posts.get_publish_adapter",
                return_value=empty_adapter,
            ):
                empty_posted = _publish(self.session, self.world.campaign_id, empty.id)

            empty_body: dict[str, object] = _ayrshare_post_body(empty_requests)

            self.assertEqual(empty_posted.status, "posted")
            self.assertEqual(empty_body["post"], "")
            self.assertEqual(len(empty_requests), 2)
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()
            open_account.external_account_id = previous_profile_key
            self.session.commit()

    def test_a_blank_profile_key_fails_the_ayrshare_publish(self) -> None:
        """Ayrshare refuses before HTTP and the row stores that sentence."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()
        adapter, recorded_requests = _recording_ayrshare_adapter()

        try:
            placed = _place(
                self.session,
                self.world.campaign_id,
                _fresh_assembled(self.session, self.world.carousel_name),
                self.world.open_account_id,
            )
            _write_frame_file(self.session, placed.frames[0].id, Path(storage.name))
            open_account: Account | None = self.session.get(
                Account,
                self.world.open_account_id,
            )
            self.assertIsNotNone(open_account)
            assert open_account is not None
            self.assertIsNone(open_account.external_account_id)

            with patch(
                "app.campaigns.posts.get_publish_adapter",
                return_value=adapter,
            ):
                failed = _publish(self.session, self.world.campaign_id, placed.id)

            self.assertEqual(failed.status, "failed")
            self.assertEqual(
                failed.last_error,
                (
                    "This account has no Ayrshare profile key. "
                    "Set external_account_id before publishing."
                ),
            )
            self.assertEqual(recorded_requests, [])
            self.assertIsNone(failed.published_at)
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def test_a_tiktok_pending_id_is_stored_as_posted(self) -> None:
        """A pending TikTok id with no URL is posted. The id is stored as pending."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()
        adapter, _recorded_requests = _ayrshare_adapter_with_post_body(
            {
                "status": "success",
                "errors": [],
                "postIds": [
                    {
                        "status": "success",
                        "id": "pending",
                        "platform": "tiktok",
                    },
                ],
                "id": "ayrshare-own-id",
            },
        )

        try:
            source_campaign: Campaign | None = self.session.get(
                Campaign,
                self.world.campaign_id,
            )
            open_account: Account | None = self.session.get(
                Account,
                self.world.open_account_id,
            )
            self.assertIsNotNone(source_campaign)
            self.assertIsNotNone(open_account)
            assert source_campaign is not None
            assert open_account is not None
            tiktok_account = create_account(
                AccountCreateRequest(
                    cluster_id=open_account.cluster_id,
                    platform=Platform.TIKTOK,
                    handle=f"tt_{uuid.uuid4().hex[:8]}",
                    external_account_id="profile-key-tiktok",
                ),
                self.session,
            )
            created_campaign = create_campaign(
                CampaignCreateRequest(
                    name=f"TikTok {uuid.uuid4().hex[:6]}",
                    campaign_type=CampaignType.SPOTMU_TEST,
                    skeleton_id=source_campaign.skeleton_id,
                    carousel_id=source_campaign.carousel_id,
                    platforms=[Platform.TIKTOK],
                    account_ids=[tiktok_account.id],
                ),
                self.session,
                None,
            )
            placed = _place(
                self.session,
                created_campaign.id,
                _fresh_assembled(self.session, "Harbor"),
                tiktok_account.id,
            )
            _write_frame_file(self.session, placed.frames[0].id, Path(storage.name))

            with patch(
                "app.campaigns.posts.get_publish_adapter",
                return_value=adapter,
            ):
                posted = _publish(self.session, created_campaign.id, placed.id)

            self.assertEqual(posted.status, "posted")
            self.assertEqual(posted.platform_post_id, "pending")
            self.assertIsNone(posted.platform_post_url)
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def test_a_vendor_error_does_not_store_pending(self) -> None:
        """An Ayrshare error body leaves the row failed and does not store pending."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()
        adapter, _recorded_requests = _ayrshare_adapter_with_post_body(
            {
                "status": "error",
                "errors": [
                    {
                        "status": "error",
                        "code": 156,
                        "message": "TikTok rejected the post.",
                        "platform": "tiktok",
                    },
                ],
                "postIds": [
                    {
                        "status": "error",
                        "id": "pending",
                        "platform": "tiktok",
                    },
                ],
                "id": "ayrshare-own-id",
            },
        )

        try:
            source_campaign: Campaign | None = self.session.get(
                Campaign,
                self.world.campaign_id,
            )
            open_account: Account | None = self.session.get(
                Account,
                self.world.open_account_id,
            )
            self.assertIsNotNone(source_campaign)
            self.assertIsNotNone(open_account)
            assert source_campaign is not None
            assert open_account is not None
            tiktok_account = create_account(
                AccountCreateRequest(
                    cluster_id=open_account.cluster_id,
                    platform=Platform.TIKTOK,
                    handle=f"tt_err_{uuid.uuid4().hex[:8]}",
                    external_account_id="profile-key-tiktok",
                ),
                self.session,
            )
            created_campaign = create_campaign(
                CampaignCreateRequest(
                    name=f"TikTok err {uuid.uuid4().hex[:6]}",
                    campaign_type=CampaignType.SPOTMU_TEST,
                    skeleton_id=source_campaign.skeleton_id,
                    carousel_id=source_campaign.carousel_id,
                    platforms=[Platform.TIKTOK],
                    account_ids=[tiktok_account.id],
                ),
                self.session,
                None,
            )
            placed = _place(
                self.session,
                created_campaign.id,
                _fresh_assembled(self.session, "Harbor"),
                tiktok_account.id,
            )
            _write_frame_file(self.session, placed.frames[0].id, Path(storage.name))

            with patch(
                "app.campaigns.posts.get_publish_adapter",
                return_value=adapter,
            ):
                failed = _publish(self.session, created_campaign.id, placed.id)

            self.assertEqual(failed.status, "failed")
            self.assertNotEqual(failed.platform_post_id, "pending")
            self.assertIsNone(failed.platform_post_id)
            self.assertIn("TikTok rejected the post.", failed.last_error or "")
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def test_an_adapter_exception_leaves_the_post_failed(self) -> None:
        """A raising adapter stores failed and does not mark the post up."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            placed = _place(
                self.session,
                self.world.campaign_id,
                _fresh_assembled(self.session, self.world.carousel_name),
                self.world.open_account_id,
            )
            _write_frame_file(self.session, placed.frames[0].id, Path(storage.name))

            with patch(
                "app.campaigns.posts.get_publish_adapter",
                return_value=_RaisingPublishAdapter(),
            ):
                failed = _publish(self.session, self.world.campaign_id, placed.id)

            self.assertEqual(failed.status, "failed")
            self.assertIn("adapter broke", failed.last_error or "")
            self.assertIsNone(failed.published_at)
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def test_a_posted_mock_keeps_result_history(self) -> None:
        """The stub and a later manual count both stay, and results shows the later one."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            placed = _place(
                self.session,
                self.world.campaign_id,
                _fresh_assembled(self.session, self.world.carousel_name),
                self.world.open_account_id,
            )
            _write_frame_file(self.session, placed.frames[0].id, Path(storage.name))
            _publish(self.session, self.world.campaign_id, placed.id)
            create_campaign_post_stub_metric_snapshot(
                self.world.campaign_id,
                placed.id,
                self.session,
                None,
            )
            after_stub = _reload_post(self.session, placed.id)

            self.assertIsNotNone(after_stub.results)
            assert after_stub.results is not None
            self.assertEqual(after_stub.results.views, 100)
            self.assertEqual(after_stub.results.likes, 10)
            self.assertEqual(after_stub.results.comments, 2)
            self.assertEqual(after_stub.results.shares, 1)
            self.assertEqual(after_stub.status, "posted")

            later: datetime = datetime.now(timezone.utc) + timedelta(hours=3)
            create_campaign_post_metric_snapshot(
                self.world.campaign_id,
                placed.id,
                PostJobMetricsCreateRequest(
                    views=7,
                    likes=1,
                    comments=0,
                    shares=0,
                    captured_at=later,
                ),
                self.session,
                None,
            )
            after_manual = _reload_post(self.session, placed.id)

            self.assertIsNotNone(after_manual.results)
            assert after_manual.results is not None
            self.assertEqual(after_manual.results.views, 7)
            self.assertEqual(after_manual.results.likes, 1)
            self.assertEqual(_snapshot_count(self.session, placed.id), 2)
            self.assertEqual(after_manual.status, "posted")
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def test_results_wait_until_the_post_is_up(self) -> None:
        """An upcoming post is 409 and stores no snapshot."""

        placed = _place(
            self.session,
            self.world.campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
        )
        before_snapshots: int = _row_count(self.session, MetricSnapshot)

        with self.assertRaises(HTTPException) as raised_http:
            create_campaign_post_stub_metric_snapshot(
                self.world.campaign_id,
                placed.id,
                self.session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 409)
        self.assertEqual(
            raised_http.exception.detail,
            RECORD_RESULTS_AFTER_POST_DETAIL,
        )
        self.assertEqual(_row_count(self.session, MetricSnapshot), before_snapshots)

    def test_a_post_job_snapshot_stays_on_the_job(self) -> None:
        """A post-job snapshot keeps its job id and a null campaign post id."""

        created_job = create_post_job(
            PostJobCreateRequest(
                artifact_id=_artifact_id(self.session, self.world.brand_id),
                account_id=self.world.open_account_id,
                status=PostJobStatus.SCHEDULED,
                scheduled_for=SCHEDULED_FOR,
            ),
            self.session,
        )
        stored_job: PostJob | None = self.session.get(PostJob, created_job.id)
        assert stored_job is not None
        snapshot: MetricSnapshot = append_metric_snapshot(
            stored_job,
            views=3,
            likes=1,
            comments=0,
            shares=0,
        )
        self.session.add(snapshot)
        self.session.commit()
        stored_snapshot: MetricSnapshot | None = self.session.get(
            MetricSnapshot,
            snapshot.id,
        )

        self.assertIsNotNone(stored_snapshot)
        assert stored_snapshot is not None
        self.assertEqual(stored_snapshot.post_job_id, created_job.id)
        self.assertIsNone(stored_snapshot.campaign_post_id)

    def test_campaign_detail_lists_posts_in_time_order(self) -> None:
        """The detail lists upcoming then posted, and run leaves that list."""

        campaign_id: uuid.UUID = _campaign_on_world_carousel(self.session)
        empty_detail = get_campaign_by_id(campaign_id, self.session)
        self.assertEqual(empty_detail.posts, [])
        run_carousels = list(empty_detail.carousels)

        early_post = _place_at(
            self.session,
            campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
            SCHEDULED_FOR,
        )
        late_post = _place_at(
            self.session,
            campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
            SCHEDULED_FOR + timedelta(days=1),
        )
        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            _write_frame_file(self.session, late_post.frames[0].id, Path(storage.name))
            _publish(self.session, campaign_id, late_post.id)
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

        detail = get_campaign_by_id(campaign_id, self.session)
        ran = run_campaign(campaign_id, self.session, None)

        self.assertEqual([post.id for post in detail.posts], [early_post.id, late_post.id])
        self.assertEqual(detail.posts[0].status, "upcoming")
        self.assertEqual(detail.posts[1].status, "posted")
        self.assertEqual(detail.carousels, run_carousels)
        self.assertEqual(ran.carousels, run_carousels)
        self.assertEqual([post.id for post in ran.posts], [early_post.id, late_post.id])

    def test_cross_campaign_list_translates_post_jobs(self) -> None:
        """Post jobs use the timeline labels. Artifacts without a job stay off it."""

        suffix: str = uuid.uuid4().hex[:8]
        campaign_id: uuid.UUID = _campaign_on_world_carousel(self.session)
        campaign = get_campaign_by_id(campaign_id, self.session)
        placed = _place(
            self.session,
            campaign_id,
            _fresh_assembled(self.session, self.world.carousel_name),
            self.world.open_account_id,
        )
        draft_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.world.brand_id,
                status=ArtifactStatus.DRAFT,
                caption=f"draft-only-{suffix}",
            ),
            self.session,
        )
        approved_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=self.world.brand_id,
                status=ArtifactStatus.APPROVED,
                caption=f"approved-only-{suffix}",
            ),
            self.session,
        )
        scheduled_job = _timeline_post_job(
            self.session,
            self.world,
            PostJobStatus.SCHEDULED,
            SCHEDULED_FOR,
        )
        published_job = _timeline_post_job(
            self.session,
            self.world,
            PostJobStatus.PUBLISHED,
            SCHEDULED_FOR + timedelta(hours=1),
        )
        measured_job = _timeline_post_job(
            self.session,
            self.world,
            PostJobStatus.MEASURED,
            SCHEDULED_FOR + timedelta(hours=2),
        )
        failed_job = _timeline_post_job(
            self.session,
            self.world,
            PostJobStatus.FAILED,
            SCHEDULED_FOR + timedelta(hours=3),
        )
        untimed_job = _timeline_post_job(
            self.session,
            self.world,
            PostJobStatus.SCHEDULED,
            None,
        )
        rows = list_timeline_posts(self.session)
        by_id = {row.id: row for row in rows}
        captions: set[str | None] = {row.caption for row in rows}
        timed_index: int = next(
            index for index, row in enumerate(rows) if row.id == scheduled_job.id
        )
        untimed_index: int = next(
            index for index, row in enumerate(rows) if row.id == untimed_job.id
        )

        self.assertEqual(by_id[placed.id].origin, "campaign_post")
        self.assertEqual(by_id[placed.id].campaign_name, campaign.name)
        self.assertEqual(by_id[placed.id].status, "upcoming")
        self.assertEqual(by_id[scheduled_job.id].origin, "post_job")
        self.assertEqual(by_id[scheduled_job.id].status, "upcoming")
        self.assertIsNone(by_id[scheduled_job.id].campaign_name)
        self.assertIsNone(by_id[scheduled_job.id].campaign_id)
        self.assertEqual(by_id[published_job.id].status, "posted")
        self.assertEqual(by_id[measured_job.id].status, "posted")
        self.assertEqual(by_id[failed_job.id].status, "failed")
        self.assertNotIn(draft_artifact.caption, captions)
        self.assertNotIn(approved_artifact.caption, captions)
        self.assertLess(timed_index, untimed_index)

    def test_a_posted_assembly_stays_until_the_post_is_removed(self) -> None:
        """A campaign post blocks the next assemble and keeps the PNG files."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            carousel_id, skeleton_id, assembly_id, group_id, first_refs = (
                _assemble_two_live_slides(self.session)
            )
            campaign_id: uuid.UUID = _campaign_for_carousel(
                self.session,
                skeleton_id,
                carousel_id,
            )
            placed: CampaignPostRead = _place(
                self.session,
                campaign_id,
                group_id,
                self.world.open_account_id,
            )

            with self.assertRaises(HTTPException) as refused:
                assemble_carousel(carousel_id, self.session, None)

            held_refs: list[str] = _frame_asset_refs(self.session, assembly_id)
            held_files: bool = all(
                (Path(storage.name) / asset_ref).is_file() for asset_ref in first_refs
            )
            remove_campaign_post_by_id(campaign_id, placed.id, self.session, None)
            assemble_carousel(carousel_id, self.session, None)
            replaced_refs: list[str] = _frame_asset_refs(self.session, assembly_id)
            old_files_removed: bool = all(
                not (Path(storage.name) / asset_ref).exists() for asset_ref in first_refs
            )
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

        self.assertIn("post", methods_by_path["/api/v1/generate/carousel"])
        self.assertEqual(refused.exception.status_code, 409)
        self.assertEqual(refused.exception.detail, GENERATION_ON_TIMELINE_DETAIL)
        self.assertEqual(held_refs, first_refs)
        self.assertTrue(held_files)
        self.assertEqual(_assembly_count(self.session, carousel_id), 1)
        self.assertNotEqual(replaced_refs, first_refs)
        self.assertTrue(old_files_removed)
        self.assertGreater(len(replaced_refs), 0)

    def test_an_assembly_with_no_post_still_replaces_its_frames(self) -> None:
        """A second assemble replaces frames when nothing is on the timeline."""

        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            carousel_id, _skeleton_id, assembly_id, _group_id, first_refs = (
                _assemble_two_live_slides(self.session)
            )
            assemble_carousel(carousel_id, self.session, None)
            replaced_refs: list[str] = _frame_asset_refs(self.session, assembly_id)
            old_files_removed: bool = all(
                not (Path(storage.name) / asset_ref).exists() for asset_ref in first_refs
            )
        finally:
            storage.cleanup()

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

        self.assertTrue(old_files_removed)
        self.assertEqual(_assembly_count(self.session, carousel_id), 1)
        self.assertNotEqual(replaced_refs, first_refs)
        self.assertGreater(len(replaced_refs), 0)


class _RaisingPublishAdapter:
    """Test double whose media publish always fails."""

    def publish_media(
        self,
        post_id: uuid.UUID,
        account: object,
        media_paths: list[Path],
        caption: str = "",
        media_urls: list[str] | None = None,
    ) -> None:

        _ = post_id
        _ = account
        _ = media_paths
        _ = caption
        _ = media_urls

        raise RuntimeError("adapter broke")


class CampaignPostRouteTests(unittest.TestCase):
    """The new route stays on the API, and a reader cannot call it."""

    def test_generate_carousel_route_stays_registered(self) -> None:
        """The old generate route and the new post route are both registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)

        self.assertIn("post", methods_by_path["/api/v1/generate/carousel"])
        self.assertIn("post", methods_by_path["/api/v1/campaigns/{campaign_id}/posts"])
        self.assertIn(
            "patch",
            methods_by_path["/api/v1/campaigns/{campaign_id}/posts/{post_id}"],
        )
        self.assertIn(
            "delete",
            methods_by_path["/api/v1/campaigns/{campaign_id}/posts/{post_id}"],
        )
        self.assertIn(
            "post",
            methods_by_path[
                "/api/v1/campaigns/{campaign_id}/posts/{post_id}/publish"
            ],
        )
        self.assertIn("get", methods_by_path["/api/v1/posts"])

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

    def test_a_reader_cannot_move_or_remove_a_post(self) -> None:
        """Patch and delete are refused for a reader."""

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
        post_path: str = f"/api/v1/campaigns/{uuid.uuid4()}/posts/{uuid.uuid4()}"

        try:
            patch_response = client.patch(
                post_path,
                json={"scheduled_for": "2026-11-13T18:00:00Z"},
            )
            delete_response = client.delete(post_path)
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
        self.assertEqual(patch_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertIn("read-only", patch_response.json()["detail"].lower())
        self.assertIn("read-only", delete_response.json()["detail"].lower())

    def test_a_reader_cannot_publish_a_post(self) -> None:
        """Publish is refused for a reader."""

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
                f"/api/v1/campaigns/{uuid.uuid4()}/posts/{uuid.uuid4()}/publish",
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

    def test_a_reader_can_get_the_timeline(self) -> None:
        """A reader can open the cross-campaign list."""

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
            response = client.get("/api/v1/posts")
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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


def _place(
    session: Session,
    campaign_id: uuid.UUID,
    assembled_carousel_id: uuid.UUID,
    account_id: uuid.UUID,
) -> CampaignPostRead:
    """Call the place route at the shared afternoon time."""

    placed: CampaignPostRead = _place_at(
        session,
        campaign_id,
        assembled_carousel_id,
        account_id,
        SCHEDULED_FOR,
    )

    return placed


def _place_at(
    session: Session,
    campaign_id: uuid.UUID,
    assembled_carousel_id: uuid.UUID,
    account_id: uuid.UUID,
    scheduled_for: datetime,
) -> CampaignPostRead:
    """Call the place route and return the read model."""

    placed: CampaignPostRead = place_campaign_post_by_id(
        campaign_id,
        CampaignPostCreateRequest(
            assembled_carousel_id=assembled_carousel_id,
            account_id=account_id,
            scheduled_for=scheduled_for,
        ),
        session,
        None,
    )

    return placed


def _reload_post(session: Session, post_id: uuid.UUID) -> CampaignPostRead:
    """Load one post with its snapshots and return the read model."""

    stored_post: CampaignPost | None = session.scalars(
        select(CampaignPost)
        .where(CampaignPost.id == post_id)
        .options(
            selectinload(CampaignPost.metric_snapshots),
            selectinload(CampaignPost.account),
            selectinload(CampaignPost.assembled_carousel).selectinload(
                AssembledCarousel.frames,
            ),
            selectinload(CampaignPost.assembled_carousel).selectinload(
                AssembledCarousel.assembly,
            ),
        ),
    ).first()

    if stored_post is None:
        raise AssertionError("Campaign post was not stored.")

    reloaded: CampaignPostRead = serialize_campaign_post(stored_post)

    return reloaded


def _snapshot_count(session: Session, post_id: uuid.UUID) -> int:
    """Return how many snapshots belong to one campaign post."""

    snapshot_count: int = int(
        session.scalar(
            select(func.count())
            .select_from(MetricSnapshot)
            .where(MetricSnapshot.campaign_post_id == post_id),
        ),
    )

    return snapshot_count


def _recording_ayrshare_adapter() -> tuple[AyrsharePublishAdapter, list[httpx.Request]]:
    """An Ayrshare adapter whose HTTP client never leaves the process."""

    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:

        recorded_requests.append(request)

        if str(request.url).endswith("/api/media/upload"):
            upload_response: httpx.Response = httpx.Response(
                200,
                json={
                    "id": "upload-1",
                    "url": "https://images.ayrshare.com/frame.png",
                    "fileName": "frame.png",
                },
            )

            return upload_response

        post_response: httpx.Response = httpx.Response(
            200,
            json={
                "status": "success",
                "errors": [],
                "postIds": [
                    {
                        "status": "success",
                        "platform": "instagram",
                        "id": "17878176260289172",
                        "postUrl": "https://www.instagram.com/p/CP1dI9Hp_WO/",
                    },
                ],
                "id": "RhrbDtYh7hdSMc67zC8H",
            },
        )

        return post_response

    http_client: httpx.Client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
        "test-ayrshare-api-key",
        http_client,
    )

    return adapter, recorded_requests


def _ayrshare_adapter_with_post_body(
    post_body: dict[str, object],
) -> tuple[AyrsharePublishAdapter, list[httpx.Request]]:
    """Upload succeeds. The post response is the given JSON."""

    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:

        recorded_requests.append(request)

        if str(request.url).endswith("/api/media/upload"):
            upload_response: httpx.Response = httpx.Response(
                200,
                json={
                    "id": "upload-1",
                    "url": "https://images.ayrshare.com/frame.png",
                    "fileName": "frame.png",
                },
            )

            return upload_response

        post_response: httpx.Response = httpx.Response(200, json=post_body)

        return post_response

    http_client: httpx.Client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
        "test-ayrshare-api-key",
        http_client,
    )

    return adapter, recorded_requests


def _ayrshare_post_body(recorded_requests: list[httpx.Request]) -> dict[str, object]:
    """Return the JSON body of the one post request."""

    post_requests: list[httpx.Request] = [
        request
        for request in recorded_requests
        if str(request.url).endswith("/api/post")
    ]

    if len(post_requests) != 1:
        raise AssertionError(f"expected one Ayrshare post, saw {len(post_requests)}")

    decoded_body: object = json.loads(post_requests[0].content.decode("utf-8"))

    if not isinstance(decoded_body, dict):
        raise AssertionError("Ayrshare post body was not a JSON object")

    return decoded_body


def _publish(
    session: Session,
    campaign_id: uuid.UUID,
    post_id: uuid.UUID,
) -> CampaignPostRead:
    """Call the publish route and return the read model."""

    published: CampaignPostRead = publish_campaign_post_by_id(
        campaign_id,
        post_id,
        session,
        None,
    )

    return published


def _write_frame_file(
    session: Session,
    frame_id: uuid.UUID,
    storage_directory: Path,
) -> None:
    """Write the frame's stored relative path under the artifact store."""

    stored_frame: AssembledCarouselFrame | None = session.get(
        AssembledCarouselFrame,
        frame_id,
    )

    if stored_frame is None:
        raise AssertionError("Frame was not stored.")

    frame_path: Path = storage_directory / stored_frame.asset_ref
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.write_bytes(b"\x89PNG\r\n\x1a\n")


def _fresh_assembled(session: Session, caption: str) -> uuid.UUID:
    """Add one more group on the seeded assembly."""

    seeded: AssembledCarousel | None = session.get(
        AssembledCarousel,
        CampaignPostPlacementTests.world.happy_assembled_id,
    )

    if seeded is None:
        raise AssertionError("Assembly group was not stored.")

    position: int = CampaignPostPlacementTests.next_position
    CampaignPostPlacementTests.next_position = position + 1
    assembled_id: uuid.UUID = _store_group(
        session,
        seeded.assembly_id,
        position,
        caption,
        [(uuid.uuid4(), 0, False)],
    )

    return assembled_id


def _assemble_two_live_slides(
    session: Session,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, list[str]]:
    """Assemble a new carousel that has two live slides."""

    suffix: str = uuid.uuid4().hex[:8]
    created_skeleton = create_skeleton(
        SkeletonCreateRequest(name=f"Guard skeleton {suffix}"),
        session,
        None,
    )
    created_carousel = create_carousel(
        CarouselCreateRequest(
            name=f"Guard carousel {suffix}",
            skeleton_id=created_skeleton.id,
        ),
        session,
        None,
    )
    create_slide(
        created_carousel.id,
        SlideWriteRequest(name="One"),
        session,
        None,
    )
    create_slide(
        created_carousel.id,
        SlideWriteRequest(name="Two"),
        session,
        None,
    )
    assembled = assemble_carousel(created_carousel.id, session, None)

    if assembled.assembly is None or len(assembled.assembly.carousels) == 0:
        raise AssertionError("Assemble did not store a carousel.")

    assembly_id: uuid.UUID = assembled.assembly.id
    group_id: uuid.UUID = assembled.assembly.carousels[0].id
    frame_refs: list[str] = _frame_asset_refs(session, assembly_id)

    return created_carousel.id, created_skeleton.id, assembly_id, group_id, frame_refs


def _campaign_for_carousel(
    session: Session,
    skeleton_id: uuid.UUID,
    carousel_id: uuid.UUID,
) -> uuid.UUID:
    """Bind a new campaign to a carousel that was just assembled."""

    suffix: str = uuid.uuid4().hex[:8]
    created_campaign = create_campaign(
        CampaignCreateRequest(
            name=f"Guard campaign {suffix}",
            campaign_type=CampaignType.SPOTMU,
            skeleton_id=skeleton_id,
            carousel_id=carousel_id,
            platforms=[Platform.INSTAGRAM],
            account_ids=[CampaignPostPlacementTests.world.open_account_id],
            interests=[],
        ),
        session,
        None,
    )

    return created_campaign.id


def _frame_asset_refs(session: Session, assembly_id: uuid.UUID) -> list[str]:
    """Return the frame paths stored on one assembly, in position order."""

    session.expire_all()
    frames: list[AssembledCarouselFrame] = list(
        session.scalars(
            select(AssembledCarouselFrame)
            .join(
                AssembledCarousel,
                AssembledCarouselFrame.assembled_carousel_id == AssembledCarousel.id,
            )
            .where(AssembledCarousel.assembly_id == assembly_id)
            .order_by(AssembledCarousel.position, AssembledCarouselFrame.position),
        ).all(),
    )
    asset_refs: list[str] = [frame.asset_ref for frame in frames]

    return asset_refs


def _assembly_count(session: Session, carousel_id: uuid.UUID) -> int:
    """Return how many assembly rows belong to this carousel."""

    stored_count: int | None = session.scalar(
        select(func.count())
        .select_from(CarouselAssembly)
        .where(CarouselAssembly.carousel_id == carousel_id),
    )

    if stored_count is None:
        return 0

    return stored_count


def _campaign_on_world_carousel(session: Session) -> uuid.UUID:
    """Create a campaign bound to the seeded carousel and open account."""

    stored_campaign: Campaign | None = session.get(
        Campaign,
        CampaignPostPlacementTests.world.campaign_id,
    )

    if stored_campaign is None or stored_campaign.skeleton_id is None:
        raise AssertionError("Seeded campaign was not stored.")

    if stored_campaign.carousel_id is None:
        raise AssertionError("Seeded campaign has no carousel.")

    suffix: str = uuid.uuid4().hex[:8]
    created_campaign = create_campaign(
        CampaignCreateRequest(
            name=f"Timeline {suffix}",
            campaign_type=CampaignType.SPOTMU,
            skeleton_id=stored_campaign.skeleton_id,
            carousel_id=stored_campaign.carousel_id,
            platforms=[Platform.INSTAGRAM],
            account_ids=[CampaignPostPlacementTests.world.open_account_id],
            interests=[],
        ),
        session,
        None,
    )

    return created_campaign.id


def _timeline_post_job(
    session: Session,
    world: _TimelineWorld,
    status: PostJobStatus,
    scheduled_for: datetime | None,
):
    """Store one post job for the cross-campaign list."""

    created_job = create_post_job(
        PostJobCreateRequest(
            artifact_id=_artifact_id(session, world.brand_id),
            account_id=world.open_account_id,
            status=status,
            scheduled_for=scheduled_for,
        ),
        session,
    )

    return created_job


def _second_campaign(session: Session, account_id: uuid.UUID) -> uuid.UUID:
    """Create another campaign that does not own the seeded posts."""

    suffix: str = uuid.uuid4().hex[:8]
    created_skeleton = create_skeleton(
        SkeletonCreateRequest(name=f"Other skeleton {suffix}"),
        session,
        None,
    )
    created_carousel = create_carousel(
        CarouselCreateRequest(
            name=f"Other bound carousel {suffix}",
            skeleton_id=created_skeleton.id,
        ),
        session,
        None,
    )
    created_campaign = create_campaign(
        CampaignCreateRequest(
            name=f"Other campaign {suffix}",
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

    return created_campaign.id


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
