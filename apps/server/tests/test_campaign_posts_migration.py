"""Add campaign posts without copying artifacts or post jobs."""

import os
import unittest
import uuid
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

from app.carousels.default_carousel import DEFAULT_ALBUM_SLUG
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
PREVIOUS_REVISION: str = "carousel_generations"
POSTS_REVISION: str = "campaign_posts"
BRAND_ID: str = "11111111-1111-4111-8111-111111111101"
CLUSTER_ID: str = "22222222-2222-4222-8222-222222222201"
ACCOUNT_ID: str = "33333333-3333-4333-8333-333333333301"
CAMPAIGN_ID: str = "44444444-4444-4444-8444-444444444401"
ASSEMBLY_ID: str = "55555555-5555-4555-8555-555555555501"
ASSEMBLED_ID: str = "66666666-6666-4666-8666-666666666601"
CAMPAIGN_CAROUSEL_ID: str = "77777777-7777-4777-8777-777777777701"
ARTIFACT_ID: str = "88888888-8888-4888-8888-888888888801"
POST_JOB_ID: str = "99999999-9999-4999-8999-999999999901"
POST_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01"
DUPLICATE_POST_ID: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02"
SCHEDULED_FOR: str = "2026-11-13 15:00:00+00"
POST_UNIQUE: str = "uq_campaign_posts_assembled_carousel_id_account_id"


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
class CampaignPostsMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again. Existing posts are not invented."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_posts_{uuid.uuid4().hex[:10]}"
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
        """Drop the empty database and restore the previous URL."""

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

    def test_upgrade_downgrade_upgrade_inserts_no_posts(self) -> None:
        """A campaign with an assembly and six live slides gains no post row."""

        self._upgrade(PREVIOUS_REVISION)
        self._insert_campaign_with_assembly()
        before_artifacts: int = self._row_count("artifacts")
        before_post_jobs: int = self._row_count("post_jobs")
        before_campaign_carousels: int = self._row_count("campaign_carousels")
        before_slides: int = self._slide_count()

        self.assertEqual(before_slides, 6)
        self.assertEqual(before_artifacts, 1)
        self.assertEqual(before_post_jobs, 1)
        self.assertEqual(before_campaign_carousels, 1)

        self._upgrade(POSTS_REVISION)
        self.assertEqual(self._row_count("campaign_posts"), 0)
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("post_jobs"), before_post_jobs)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)
        self.assertEqual(self._slide_count(), 6)
        self.assertEqual(self._artifact_status(), "draft")
        self.assertEqual(self._post_job_status(), "scheduled")
        self._insert_upcoming_post(POST_ID)
        self.assertEqual(self._post_status(), "upcoming")
        self.assertEqual(self._post_scheduled_for(), "2026-11-13 15:00:00+00")

        with self.assertRaises(IntegrityError) as duplicate_error:
            self._insert_upcoming_post(DUPLICATE_POST_ID)

        self.assertIn(POST_UNIQUE, str(duplicate_error.exception))

        with self.assertRaises(IntegrityError) as restrict_error:
            self._delete_assembled_carousel()

        self.assertIn(
            "fk_campaign_posts_assembled_carousel_id_assembled_carousels",
            str(restrict_error.exception),
        )
        self.assertEqual(self._row_count("campaign_posts"), 1)

        self._downgrade(PREVIOUS_REVISION)
        self.assertIsNone(self._regclass("campaign_posts"))
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("post_jobs"), before_post_jobs)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)
        self.assertEqual(self._artifact_status(), "draft")
        self.assertEqual(self._slide_count(), 6)

        self._upgrade(POSTS_REVISION)
        self.assertEqual(self._row_count("campaign_posts"), 0)
        self.assertEqual(self._slide_count(), 6)
        self.assertEqual(self._row_count("artifacts"), before_artifacts)
        self.assertEqual(self._row_count("post_jobs"), before_post_jobs)
        self.assertEqual(self._row_count("campaign_carousels"), before_campaign_carousels)

    def _insert_campaign_with_assembly(self) -> None:
        """Bind a campaign to Default, which already has six live slides."""

        carousel_id: str
        skeleton_id: str
        generation_id: str
        carousel_id, skeleton_id, generation_id = self._default_carousel()

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO brands (id, slug, name)
                    VALUES (CAST(:brand_id AS uuid), 'posts-brand', 'Posts brand')
                    """
                ),
                {"brand_id": BRAND_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO clusters (id, brand_id, slug, name)
                    VALUES (
                        CAST(:cluster_id AS uuid),
                        CAST(:brand_id AS uuid),
                        'posts-cluster',
                        'Posts cluster'
                    )
                    """
                ),
                {"cluster_id": CLUSTER_ID, "brand_id": BRAND_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        id, cluster_id, platform, handle, status
                    )
                    VALUES (
                        CAST(:account_id AS uuid),
                        CAST(:cluster_id AS uuid),
                        'instagram'::platform,
                        'harbor',
                        'active'::account_status
                    )
                    """
                ),
                {"account_id": ACCOUNT_ID, "cluster_id": CLUSTER_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaigns (
                        id,
                        name,
                        slug,
                        hashtag,
                        campaign_type,
                        advertisement_type,
                        status,
                        platforms,
                        skeleton_id,
                        carousel_id
                    )
                    VALUES (
                        CAST(:campaign_id AS uuid),
                        'Harbor',
                        'harbor-posts',
                        '#harbor-posts',
                        'spotmu'::campaign_type,
                        'carousel'::advertisement_type,
                        'ready'::campaign_status,
                        CAST(:platforms AS jsonb),
                        CAST(:skeleton_id AS uuid),
                        CAST(:carousel_id AS uuid)
                    )
                    """
                ),
                {
                    "campaign_id": CAMPAIGN_ID,
                    "platforms": '["instagram"]',
                    "skeleton_id": skeleton_id,
                    "carousel_id": carousel_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_accounts (campaign_id, account_id)
                    VALUES (CAST(:campaign_id AS uuid), CAST(:account_id AS uuid))
                    """
                ),
                {"campaign_id": CAMPAIGN_ID, "account_id": ACCOUNT_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO carousel_assemblies (
                        id,
                        carousel_id,
                        generation_number,
                        slide_count,
                        generation_id
                    )
                    VALUES (
                        CAST(:assembly_id AS uuid),
                        CAST(:carousel_id AS uuid),
                        1,
                        5,
                        CAST(:generation_id AS uuid)
                    )
                    """
                ),
                {
                    "assembly_id": ASSEMBLY_ID,
                    "carousel_id": carousel_id,
                    "generation_id": generation_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO assembled_carousels (
                        id, assembly_id, position, status, caption
                    )
                    VALUES (
                        CAST(:assembled_id AS uuid),
                        CAST(:assembly_id AS uuid),
                        0,
                        'draft',
                        'Default'
                    )
                    """
                ),
                {"assembled_id": ASSEMBLED_ID, "assembly_id": ASSEMBLY_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_carousels (id, campaign_id, position)
                    VALUES (
                        CAST(:campaign_carousel_id AS uuid),
                        CAST(:campaign_id AS uuid),
                        0
                    )
                    """
                ),
                {
                    "campaign_carousel_id": CAMPAIGN_CAROUSEL_ID,
                    "campaign_id": CAMPAIGN_ID,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO artifacts (id, brand_id, status)
                    VALUES (
                        CAST(:artifact_id AS uuid),
                        CAST(:brand_id AS uuid),
                        'draft'::artifact_status
                    )
                    """
                ),
                {"artifact_id": ARTIFACT_ID, "brand_id": BRAND_ID},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO post_jobs (id, artifact_id, account_id, status)
                    VALUES (
                        CAST(:post_job_id AS uuid),
                        CAST(:artifact_id AS uuid),
                        CAST(:account_id AS uuid),
                        'scheduled'::post_job_status
                    )
                    """
                ),
                {
                    "post_job_id": POST_JOB_ID,
                    "artifact_id": ARTIFACT_ID,
                    "account_id": ACCOUNT_ID,
                },
            )

    def _insert_upcoming_post(self, post_id: str) -> None:
        """Store one upcoming post for the seeded assembly and account."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_posts (
                        id,
                        campaign_id,
                        assembled_carousel_id,
                        account_id,
                        status,
                        scheduled_for
                    )
                    VALUES (
                        CAST(:post_id AS uuid),
                        CAST(:campaign_id AS uuid),
                        CAST(:assembled_id AS uuid),
                        CAST(:account_id AS uuid),
                        'upcoming',
                        CAST(:scheduled_for AS timestamptz)
                    )
                    """
                ),
                {
                    "post_id": post_id,
                    "campaign_id": CAMPAIGN_ID,
                    "assembled_id": ASSEMBLED_ID,
                    "account_id": ACCOUNT_ID,
                    "scheduled_for": SCHEDULED_FOR,
                },
            )

    def _delete_assembled_carousel(self) -> None:
        """Try to delete the assembled carousel the post still points at."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DELETE FROM assembled_carousels
                    WHERE id = CAST(:assembled_id AS uuid)
                    """
                ),
                {"assembled_id": ASSEMBLED_ID},
            )

    def _default_carousel(self) -> tuple[str, str, str]:
        """Return Default's carousel id, skeleton id, and generation id."""

        with self.database_engine.connect() as connection:
            row: tuple[object, ...] = connection.execute(
                text(
                    """
                    SELECT
                        carousels.id::text,
                        carousels.skeleton_id::text,
                        carousel_generations.id::text
                    FROM carousels
                    JOIN carousel_generations
                      ON carousel_generations.carousel_id = carousels.id
                     AND carousel_generations.generation_number
                         = carousels.generation_number
                    WHERE carousels.slug = :slug
                    """
                ),
                {"slug": DEFAULT_ALBUM_SLUG},
            ).one()

        carousel_id: str = str(row[0])
        skeleton_id: str = str(row[1])
        generation_id: str = str(row[2])

        return carousel_id, skeleton_id, generation_id

    def _slide_count(self) -> int:
        """Return how many slides Default has."""

        carousel_id: str
        carousel_id, _skeleton_id, _generation_id = self._default_carousel()

        with self.database_engine.connect() as connection:
            slide_count: int = int(
                connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM slides
                        WHERE carousel_id = CAST(:carousel_id AS uuid)
                        """
                    ),
                    {"carousel_id": carousel_id},
                ).scalar_one(),
            )

        return slide_count

    def _post_status(self) -> str:
        """Return the stored status of the seeded post."""

        with self.database_engine.connect() as connection:
            status_value: str = str(
                connection.execute(
                    text(
                        """
                        SELECT status
                        FROM campaign_posts
                        WHERE id = CAST(:post_id AS uuid)
                        """
                    ),
                    {"post_id": POST_ID},
                ).scalar_one(),
            )

        return status_value

    def _post_scheduled_for(self) -> str:
        """Return the seeded post time as a UTC timestamp string."""

        with self.database_engine.connect() as connection:
            scheduled_for: str = str(
                connection.execute(
                    text(
                        """
                        SELECT to_char(
                            scheduled_for AT TIME ZONE 'UTC',
                            'YYYY-MM-DD HH24:MI:SS+00'
                        )
                        FROM campaign_posts
                        WHERE id = CAST(:post_id AS uuid)
                        """
                    ),
                    {"post_id": POST_ID},
                ).scalar_one(),
            )

        return scheduled_for

    def _artifact_status(self) -> str:
        """Return the seeded artifact status."""

        with self.database_engine.connect() as connection:
            status_value: str = str(
                connection.execute(
                    text(
                        """
                        SELECT status::text
                        FROM artifacts
                        WHERE id = CAST(:artifact_id AS uuid)
                        """
                    ),
                    {"artifact_id": ARTIFACT_ID},
                ).scalar_one(),
            )

        return status_value

    def _post_job_status(self) -> str:
        """Return the seeded post job status."""

        with self.database_engine.connect() as connection:
            status_value: str = str(
                connection.execute(
                    text(
                        """
                        SELECT status::text
                        FROM post_jobs
                        WHERE id = CAST(:post_job_id AS uuid)
                        """
                    ),
                    {"post_job_id": POST_JOB_ID},
                ).scalar_one(),
            )

        return status_value

    def _row_count(self, table_name: str) -> int:
        """Return how many rows one table holds."""

        with self.database_engine.connect() as connection:
            row_count: int = int(
                connection.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one(),
            )

        return row_count

    def _regclass(self, table_name: str) -> str | None:
        """Return the table name, or None when the relation is gone."""

        with self.database_engine.connect() as connection:
            registered_name: str | None = connection.execute(
                text("SELECT to_regclass(:table_name)::text"),
                {"table_name": f"public.{table_name}"},
            ).scalar_one()

        return registered_name

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


if __name__ == "__main__":
    unittest.main()
