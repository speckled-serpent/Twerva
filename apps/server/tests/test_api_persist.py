"""HTTP persist-proof handlers against Postgres when a URL is reachable.

Existing 1.2 tests are metadata-only. These exercises POST + GET against a
live database and skip when nothing is listening — same stance as 1.2a-v
/ 1.2k-iii (no required live box in CI).
"""

import os
import unittest
import uuid
from datetime import datetime, timezone

os.environ.setdefault("TWERVA_ENV", "test")

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.accounts import create_account, get_account_by_id
from app.api.v1.artifacts import create_artifact, get_artifact_by_id
from app.api.v1.brands import create_brand, get_brand_by_id, list_brands
from app.api.v1.clusters import (
    attach_source_item_to_cluster,
    create_cluster,
    detach_source_item_from_cluster,
    get_cluster_by_id,
)
from app.api.v1.post_jobs import create_post_job, get_post_job_by_id
from app.api.v1.schemas import (
    AccountCreateRequest,
    ArtifactCreateRequest,
    BrandCreateRequest,
    ClusterCreateRequest,
    PostJobCreateRequest,
    SourceItemCreateRequest,
)
from app.api.v1.source_items import create_source_item, get_source_item_by_id
from app.models.enums import ArtifactStatus, Platform, PostJobStatus


CANDIDATE_DATABASE_URLS: tuple[str, ...] = (
    os.environ.get("TWERVA_TEST_DATABASE_URL", "").strip(),
    os.environ.get("DATABASE_URL", "").strip(),
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva_test",
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
)


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


@unittest.skipIf(TEST_ENGINE is None, "Postgres is not reachable for API persist tests")
class ApiPersistTests(unittest.TestCase):
    """1.2l: create then GET Brand → SourceItem → Cluster → Account → Artifact → PostJob."""

    def setUp(self) -> None:
        """Open a session on the reachable test engine."""

        if TEST_ENGINE is None:
            self.skipTest("Postgres is not reachable for API persist tests")

        self.SessionFactory: sessionmaker[Session] = sessionmaker(
            bind=TEST_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.our_database_session: Session = self.SessionFactory()

    def tearDown(self) -> None:
        """Close the request-scoped test session."""

        if getattr(self, "our_database_session", None) is not None:
            self.our_database_session.close()

    def test_create_and_get_persist_chain(self) -> None:
        """Round-trip the 1.2l-v object chain, including status fields."""

        run_suffix: str = uuid.uuid4().hex[:8]
        created_brand = create_brand(
            BrandCreateRequest(slug=f"persist-{run_suffix}", name="Persist Brand"),
            self.our_database_session,
        )
        listed_brands = list_brands(self.our_database_session)
        listed_brand_ids: set[uuid.UUID] = {
            brand_response.id for brand_response in listed_brands
        }

        self.assertIn(created_brand.id, listed_brand_ids)

        fetched_brand = get_brand_by_id(created_brand.id, self.our_database_session)
        created_source_item = create_source_item(
            SourceItemCreateRequest(
                brand_id=created_brand.id,
                title="Persist source",
                interest_heading="Persist heading",
                overview_bullets=["a", "b", "c"],
                canonical_url="https://spotmu.com/interest/example",
                external_key=f"persist-{run_suffix}",
            ),
            self.our_database_session,
        )
        fetched_source_item = get_source_item_by_id(
            created_source_item.id,
            self.our_database_session,
        )
        created_cluster = create_cluster(
            ClusterCreateRequest(
                brand_id=created_brand.id,
                slug=f"persist-lane-{run_suffix}",
                name="Persist lane",
            ),
            self.our_database_session,
        )
        fetched_cluster = get_cluster_by_id(
            created_cluster.id,
            self.our_database_session,
        )
        created_account = create_account(
            AccountCreateRequest(
                cluster_id=created_cluster.id,
                platform=Platform.INSTAGRAM,
                handle=f"persist_{run_suffix}",
            ),
            self.our_database_session,
        )
        fetched_account = get_account_by_id(
            created_account.id,
            self.our_database_session,
        )
        created_artifact = create_artifact(
            ArtifactCreateRequest(
                brand_id=created_brand.id,
                source_item_id=created_source_item.id,
                cluster_id=created_cluster.id,
                status=ArtifactStatus.DRAFT,
            ),
            self.our_database_session,
        )
        fetched_artifact = get_artifact_by_id(
            created_artifact.id,
            self.our_database_session,
        )
        scheduled_for: datetime = datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc)
        created_post_job = create_post_job(
            PostJobCreateRequest(
                artifact_id=created_artifact.id,
                account_id=created_account.id,
                status=PostJobStatus.SCHEDULED,
                scheduled_for=scheduled_for,
            ),
            self.our_database_session,
        )
        fetched_post_job = get_post_job_by_id(
            created_post_job.id,
            self.our_database_session,
        )

        self.assertEqual(fetched_brand.slug, f"persist-{run_suffix}")
        self.assertEqual(fetched_source_item.brand_id, created_brand.id)
        self.assertEqual(len(fetched_source_item.overview_bullets), 3)
        self.assertEqual(fetched_cluster.slug, f"persist-lane-{run_suffix}")
        self.assertEqual(fetched_cluster.source_item_ids, [])
        attached_cluster = attach_source_item_to_cluster(
            created_cluster.id,
            created_source_item.id,
            self.our_database_session,
        )
        reattached_cluster = attach_source_item_to_cluster(
            created_cluster.id,
            created_source_item.id,
            self.our_database_session,
        )
        fetched_cluster_after_attach = get_cluster_by_id(
            created_cluster.id,
            self.our_database_session,
        )

        self.assertEqual(attached_cluster.source_item_ids, [created_source_item.id])
        self.assertEqual(reattached_cluster.source_item_ids, [created_source_item.id])
        self.assertEqual(
            fetched_cluster_after_attach.source_item_ids,
            [created_source_item.id],
        )
        detach_source_item_from_cluster(
            created_cluster.id,
            created_source_item.id,
            self.our_database_session,
        )
        fetched_cluster_after_detach = get_cluster_by_id(
            created_cluster.id,
            self.our_database_session,
        )

        self.assertEqual(fetched_cluster_after_detach.source_item_ids, [])
        self.assertEqual(fetched_account.platform, Platform.INSTAGRAM)
        self.assertEqual(fetched_artifact.status, ArtifactStatus.DRAFT)
        self.assertEqual(fetched_post_job.status, PostJobStatus.SCHEDULED)


if __name__ == "__main__":
    unittest.main()
