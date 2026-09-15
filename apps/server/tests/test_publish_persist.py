"""Persist 1.6 mock publish against Postgres when reachable."""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.accounts import create_account
from app.api.v1.artifacts import approve_artifact_by_id
from app.api.v1.brands import create_brand
from app.api.v1.clusters import create_cluster
from app.api.v1.post_jobs import create_post_job, get_post_job_by_id
from app.api.v1.publish import publish_post_job_by_id
from app.api.v1.schedule import schedule_post_job
from app.api.v1.schemas import (
    AccountCreateRequest,
    BrandCreateRequest,
    ClusterCreateRequest,
    PostJobCreateRequest,
    SchedulePostJobRequest,
    SourceItemCreateRequest,
)
from app.api.v1.source_items import create_source_item
from app.generate.service import generate_carousel_artifact_draft
from app.models.enums import Platform, PostJobStatus
from app.settings import clear_settings_cache


CANDIDATE_DATABASE_URLS: tuple[str, ...] = (
    os.environ.get("TWERVA_TEST_DATABASE_URL", "").strip(),
    os.environ.get("DATABASE_URL", "").strip(),
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva_test",
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
)

SCHEDULED_FOR: datetime = datetime(2026, 9, 17, 15, 0, tzinfo=timezone.utc)


def _connect_test_engine() -> Engine | None:
    """Return an engine for the first reachable candidate URL, if any."""

    for candidate_database_url in CANDIDATE_DATABASE_URLS:

        if candidate_database_url == "":
            continue

        normalized_database_url: str = candidate_database_url

        if normalized_database_url.startswith("postgresql://"):
            remainder: str = normalized_database_url[len("postgresql://"):]
            normalized_database_url = f"postgresql+psycopg://{remainder}"

        candidate_engine: Engine | None = None

        try:
            candidate_engine = create_engine(normalized_database_url)
            with candidate_engine.connect() as our_database_connection:
                our_database_connection.execute(text("SELECT 1"))
        except OperationalError:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        except Exception:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        else:

            return candidate_engine

    return None


TEST_ENGINE: Engine | None = _connect_test_engine()


@unittest.skipIf(TEST_ENGINE is None, "Postgres is not reachable for 1.6 persist tests")
class PublishPersistTests(unittest.TestCase):
    """1.6c: generate → approve → schedule → mock publish records fake ids."""

    def setUp(self) -> None:
        """Open a session and point ARTIFACT_STORAGE_DIR at a tmp store."""

        if TEST_ENGINE is None:
            self.skipTest("Postgres is not reachable for 1.6 persist tests")

        self.previous_artifact_storage_dir: str | None = os.environ.get(
            "ARTIFACT_STORAGE_DIR",
        )
        self.temporary_directory: TemporaryDirectory[str] = TemporaryDirectory()
        os.environ["ARTIFACT_STORAGE_DIR"] = self.temporary_directory.name
        clear_settings_cache()
        self.SessionFactory: sessionmaker[Session] = sessionmaker(
            bind=TEST_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.our_database_session: Session = self.SessionFactory()
        self.run_suffix: str = uuid.uuid4().hex[:8]
        self.created_brand = create_brand(
            BrandCreateRequest(
                slug=f"publish-{self.run_suffix}",
                name="Publish Brand",
            ),
            self.our_database_session,
        )
        self.created_source_item = create_source_item(
            SourceItemCreateRequest(
                brand_id=self.created_brand.id,
                title="Publish source",
                interest_heading="Publish heading",
                overview_bullets=["one", "two"],
                canonical_url="https://spotmu.com/interest/example",
                external_key=f"publish-{self.run_suffix}",
            ),
            self.our_database_session,
        )
        self.created_cluster = create_cluster(
            ClusterCreateRequest(
                brand_id=self.created_brand.id,
                slug=f"publish-lane-{self.run_suffix}",
                name="Publish lane",
            ),
            self.our_database_session,
        )
        self.created_account = create_account(
            AccountCreateRequest(
                cluster_id=self.created_cluster.id,
                platform=Platform.INSTAGRAM,
                handle=f"publish_{self.run_suffix}",
            ),
            self.our_database_session,
        )

    def tearDown(self) -> None:
        """Close the session, restore env, and drop the tmp store."""

        if getattr(self, "our_database_session", None) is not None:
            self.our_database_session.close()

        if hasattr(self, "previous_artifact_storage_dir"):

            if self.previous_artifact_storage_dir is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = self.previous_artifact_storage_dir

            clear_settings_cache()

        if getattr(self, "temporary_directory", None) is not None:
            self.temporary_directory.cleanup()

    def test_mock_publish_scheduled_job_records_fake_platform_ids(self) -> None:
        """Scheduled job becomes published with mock- prefix ids."""

        storage_directory: Path = Path(self.temporary_directory.name)
        generated_artifact = generate_carousel_artifact_draft(
            self.created_source_item.id,
            self.our_database_session,
            cluster_id=self.created_cluster.id,
            artifact_storage_directory=storage_directory,
        )
        self.our_database_session.commit()
        approve_artifact_by_id(
            generated_artifact.id,
            None,
            self.our_database_session,
        )
        scheduled_post_job = schedule_post_job(
            SchedulePostJobRequest(
                artifact_id=generated_artifact.id,
                account_id=self.created_account.id,
                scheduled_for=SCHEDULED_FOR,
            ),
            self.our_database_session,
        )

        self.assertEqual(scheduled_post_job.status, PostJobStatus.SCHEDULED)

        published_post_job = publish_post_job_by_id(
            scheduled_post_job.id,
            self.our_database_session,
        )

        self.assertEqual(published_post_job.status, PostJobStatus.PUBLISHED)
        self.assertIsNotNone(published_post_job.platform_post_id)
        self.assertTrue(
            str(published_post_job.platform_post_id).startswith("mock-instagram-"),
        )
        self.assertIsNotNone(published_post_job.platform_post_url)
        self.assertIn("example.invalid/instagram/p/", str(published_post_job.platform_post_url))
        self.assertIsNotNone(published_post_job.published_at)
        self.assertIsNone(published_post_job.last_error)

        fetched_post_job = get_post_job_by_id(
            published_post_job.id,
            self.our_database_session,
        )

        self.assertEqual(fetched_post_job.status, PostJobStatus.PUBLISHED)
        self.assertEqual(
            fetched_post_job.platform_post_id,
            published_post_job.platform_post_id,
        )

        with self.assertRaises(HTTPException) as raised_again:
            publish_post_job_by_id(
                published_post_job.id,
                self.our_database_session,
            )

        self.assertEqual(raised_again.exception.status_code, 409)

    def test_publish_of_measured_job_returns_409(self) -> None:
        """Non-scheduled, non-failed jobs are not publishable."""

        generated_artifact = generate_carousel_artifact_draft(
            self.created_source_item.id,
            self.our_database_session,
            cluster_id=self.created_cluster.id,
            artifact_storage_directory=Path(self.temporary_directory.name),
        )
        self.our_database_session.commit()
        measured_post_job = create_post_job(
            PostJobCreateRequest(
                artifact_id=generated_artifact.id,
                account_id=self.created_account.id,
                status=PostJobStatus.MEASURED,
            ),
            self.our_database_session,
        )

        with self.assertRaises(HTTPException) as raised_measured:
            publish_post_job_by_id(
                measured_post_job.id,
                self.our_database_session,
            )

        self.assertEqual(raised_measured.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
