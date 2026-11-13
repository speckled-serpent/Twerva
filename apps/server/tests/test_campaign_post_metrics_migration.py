"""Let metric snapshots point at a campaign post."""

import os
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.accounts import create_account
from app.api.v1.artifacts import create_artifact
from app.api.v1.brands import create_brand
from app.api.v1.clusters import create_cluster
from app.api.v1.post_jobs import create_post_job
from app.api.v1.schemas import (
    AccountCreateRequest,
    ArtifactCreateRequest,
    BrandCreateRequest,
    ClusterCreateRequest,
    PostJobCreateRequest,
)
from app.metrics.service import append_metric_snapshot
from app.models.enums import ArtifactStatus, Platform, PostJobStatus
from app.models.metric_snapshot import MetricSnapshot
from app.models.post_job import PostJob
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
PREVIOUS_REVISION: str = "campaign_posts"
METRICS_REVISION: str = "campaign_post_metrics"
SCHEDULED_FOR: datetime = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)


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


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for migration tests")
class CampaignPostMetricsMigrationTests(unittest.TestCase):
    """Upgrade and downgrade the campaign post pointer on metric snapshots."""

    def setUp(self) -> None:
        """Create an empty database and point Alembic at it."""

        self.database_name: str = f"twerva_metrics_{uuid.uuid4().hex[:10]}"
        self.database_url: str = (
            "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/"
            f"{self.database_name}"
        )
        self.previous_database_url: str | None = os.environ.get("DATABASE_URL")
        self.admin_engine: Engine = create_engine(
            ADMIN_DATABASE_URL,
            isolation_level="AUTOCOMMIT",
        )

        with self.admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{self.database_name}"'))

        os.environ["DATABASE_URL"] = self.database_url
        clear_settings_cache()
        self.database_engine: Engine = create_engine(self.database_url)

    def tearDown(self) -> None:
        """Drop the database and restore the previous URL."""

        clear_settings_cache()
        self.database_engine.dispose()

        if self.previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self.previous_database_url

        clear_settings_cache()

        with self.admin_engine.connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": self.database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{self.database_name}"'))

        self.admin_engine.dispose()

    def test_upgrade_downgrade_upgrade_keeps_post_job_snapshots(self) -> None:
        """A job snapshot stays. A campaign-post snapshot is removed on downgrade."""

        self._upgrade(METRICS_REVISION)
        session: Session = sessionmaker(bind=self.database_engine)()

        try:
            post_job_snapshot_id: uuid.UUID = self._store_post_job_snapshot(session)
            campaign_snapshot_id: uuid.UUID = self._store_campaign_snapshot(session)
            self._assert_owner_check_rejects_an_empty_row(session)
        finally:
            session.close()

        self.assertEqual(self._campaign_post_id(post_job_snapshot_id), None)
        self.assertIsNotNone(self._post_job_id(post_job_snapshot_id))

        self._downgrade(PREVIOUS_REVISION)
        self.assertNotIn("campaign_post_id", self._column_names("metric_snapshots"))
        self.assertEqual(self._row_count("metric_snapshots"), 1)
        self.assertIsNotNone(self._post_job_id(post_job_snapshot_id))
        self.assertIsNone(self._snapshot_id_exists(campaign_snapshot_id))

        self._upgrade(METRICS_REVISION)
        self.assertIn("campaign_post_id", self._column_names("metric_snapshots"))
        self.assertEqual(self._campaign_post_id(post_job_snapshot_id), None)
        self.assertIsNotNone(self._post_job_id(post_job_snapshot_id))
        self.assertTrue(self._post_job_id_is_nullable())

    def _store_post_job_snapshot(self, session: Session) -> uuid.UUID:
        """Insert one post-job snapshot and return its id."""

        suffix: str = uuid.uuid4().hex[:8]
        created_brand = create_brand(
            BrandCreateRequest(slug=f"metrics-{suffix}", name="Metrics brand"),
            session,
        )
        created_cluster = create_cluster(
            ClusterCreateRequest(
                brand_id=created_brand.id,
                slug=f"metrics-lane-{suffix}",
                name="Metrics lane",
            ),
            session,
        )
        created_account = create_account(
            AccountCreateRequest(
                cluster_id=created_cluster.id,
                platform=Platform.INSTAGRAM,
                handle=f"metrics_{suffix}",
            ),
            session,
        )
        created_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=created_brand.id,
                status=ArtifactStatus.DRAFT,
                caption="Old queue",
            ),
            session,
        )
        created_job = create_post_job(
            PostJobCreateRequest(
                artifact_id=created_artifact.id,
                account_id=created_account.id,
                status=PostJobStatus.PUBLISHED,
                scheduled_for=SCHEDULED_FOR,
            ),
            session,
        )
        stored_job: PostJob | None = session.get(PostJob, created_job.id)

        if stored_job is None:
            raise AssertionError("Post job was not stored.")

        snapshot: MetricSnapshot = append_metric_snapshot(
            stored_job,
            views=4,
            likes=1,
            comments=0,
            shares=0,
        )
        session.add(snapshot)
        session.commit()

        return snapshot.id

    def _store_campaign_snapshot(self, session: Session) -> uuid.UUID:
        """Insert one snapshot that points only at a campaign post."""

        from app.api.v1.campaigns import create_campaign
        from app.api.v1.carousel_writes import create_carousel
        from app.api.v1.schemas import CampaignCreateRequest, CarouselCreateRequest, SkeletonCreateRequest
        from app.api.v1.skeletons import create_skeleton
        from app.models.account import Account
        from app.models.campaign import CampaignPost
        from app.models.carousel import (
            AssembledCarousel,
            CarouselAssembly,
            CarouselGeneration,
        )
        from app.models.enums import CampaignType

        suffix: str = uuid.uuid4().hex[:8]
        created_account: Account | None = session.scalars(select_account(session)).first()

        if created_account is None:
            raise AssertionError("Account was not stored.")

        created_skeleton = create_skeleton(
            SkeletonCreateRequest(name=f"Metrics skeleton {suffix}"),
            session,
            None,
        )
        created_carousel = create_carousel(
            CarouselCreateRequest(
                name=f"Metrics carousel {suffix}",
                skeleton_id=created_skeleton.id,
            ),
            session,
            None,
        )
        created_campaign = create_campaign(
            CampaignCreateRequest(
                name=f"Metrics campaign {suffix}",
                campaign_type=CampaignType.SPOTMU,
                skeleton_id=created_skeleton.id,
                carousel_id=created_carousel.id,
                platforms=[Platform.INSTAGRAM],
                account_ids=[created_account.id],
                interests=[],
            ),
            session,
            None,
        )
        generation: CarouselGeneration = session.scalars(
            select_generation(session, created_carousel.id),
        ).one()
        assembly: CarouselAssembly = CarouselAssembly(
            id=uuid.uuid4(),
            carousel_id=created_carousel.id,
            generation_number=generation.generation_number,
            generation_id=generation.id,
            slide_count=5,
        )
        session.add(assembly)
        session.flush()
        assembled: AssembledCarousel = AssembledCarousel(
            id=uuid.uuid4(),
            assembly_id=assembly.id,
            position=0,
            status="draft",
            caption=created_carousel.name,
        )
        session.add(assembled)
        session.flush()
        campaign_post: CampaignPost = CampaignPost(
            id=uuid.uuid4(),
            campaign_id=created_campaign.id,
            assembled_carousel_id=assembled.id,
            account_id=created_account.id,
            status="posted",
            scheduled_for=SCHEDULED_FOR,
            platform_post_id=f"mock-instagram-{uuid.uuid4()}",
        )
        session.add(campaign_post)
        session.flush()
        snapshot: MetricSnapshot = MetricSnapshot(
            post_job_id=None,
            campaign_post_id=campaign_post.id,
            captured_at=SCHEDULED_FOR,
            views=100,
            likes=10,
            comments=2,
            shares=1,
        )
        session.add(snapshot)
        session.commit()

        return snapshot.id

    def _assert_owner_check_rejects_an_empty_row(self, session: Session) -> None:
        """A snapshot with neither owner fails the check."""

        with self.assertRaises(IntegrityError):
            with self.database_engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO metric_snapshots (id, captured_at)
                        VALUES (gen_random_uuid(), now())
                        """
                    ),
                )

        session.rollback()

    def _campaign_post_id(self, snapshot_id: uuid.UUID) -> str | None:
        """Return the campaign post id text, or None."""

        with self.database_engine.connect() as connection:
            value: object | None = connection.execute(
                text(
                    """
                    SELECT campaign_post_id::text
                    FROM metric_snapshots
                    WHERE id = CAST(:snapshot_id AS uuid)
                    """
                ),
                {"snapshot_id": str(snapshot_id)},
            ).scalar_one()

        if value is None:
            return None

        return str(value)

    def _post_job_id(self, snapshot_id: uuid.UUID) -> str | None:
        """Return the post job id text, or None when the snapshot is gone."""

        with self.database_engine.connect() as connection:
            value: object | None = connection.execute(
                text(
                    """
                    SELECT post_job_id::text
                    FROM metric_snapshots
                    WHERE id = CAST(:snapshot_id AS uuid)
                    """
                ),
                {"snapshot_id": str(snapshot_id)},
            ).scalar_one_or_none()

        if value is None:
            return None

        return str(value)

    def _snapshot_id_exists(self, snapshot_id: uuid.UUID) -> str | None:
        """Return the snapshot id when the row is still present."""

        with self.database_engine.connect() as connection:
            value: object | None = connection.execute(
                text(
                    """
                    SELECT id::text
                    FROM metric_snapshots
                    WHERE id = CAST(:snapshot_id AS uuid)
                    """
                ),
                {"snapshot_id": str(snapshot_id)},
            ).scalar_one_or_none()

        if value is None:
            return None

        return str(value)

    def _post_job_id_is_nullable(self) -> bool:
        """Return whether post_job_id accepts null."""

        with self.database_engine.connect() as connection:
            is_nullable: str = str(
                connection.execute(
                    text(
                        """
                        SELECT is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'metric_snapshots'
                          AND column_name = 'post_job_id'
                        """
                    ),
                ).scalar_one(),
            )

        return is_nullable == "YES"

    def _column_names(self, table_name: str) -> set[str]:
        """Return the column names on one table."""

        with self.database_engine.connect() as connection:
            names: set[str] = {
                str(row[0])
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                        """
                    ),
                    {"table_name": table_name},
                ).fetchall()
            }

        return names

    def _row_count(self, table_name: str) -> int:
        """Return how many rows one table holds."""

        with self.database_engine.connect() as connection:
            row_count: int = int(
                connection.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one(),
            )

        return row_count

    def _upgrade(self, revision: str) -> None:
        """Run alembic upgrade against this test database."""

        clear_settings_cache()
        command.upgrade(self._alembic_config(), revision)

    def _downgrade(self, revision: str) -> None:
        """Run alembic downgrade against this test database."""

        clear_settings_cache()
        command.downgrade(self._alembic_config(), revision)

    def _alembic_config(self) -> Config:
        """Return Alembic config for the server tree."""

        alembic_config: Config = Config(str(SERVER_ROOT / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(SERVER_ROOT / "alembic"))

        return alembic_config


def select_account(session: Session):
    """Return a select of every account. Kept as a function for a short call."""

    from sqlalchemy import select

    from app.models.account import Account

    _ = session

    return select(Account)


def select_generation(session: Session, carousel_id: uuid.UUID):
    """Return a select for one carousel's generation header."""

    from sqlalchemy import select

    from app.models.carousel import CarouselGeneration

    _ = session

    return select(CarouselGeneration).where(
        CarouselGeneration.carousel_id == carousel_id,
    )
