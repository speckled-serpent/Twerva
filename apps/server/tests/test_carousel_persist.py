"""Persist a generated carousel draft and read it via GET schema (1.4d)."""

from __future__ import annotations

import os
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("TWERVA_ENV", "test")

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.artifacts import get_artifact_by_id
from app.api.v1.brands import create_brand
from app.api.v1.clusters import create_cluster
from app.api.v1.schemas import BrandCreateRequest, ClusterCreateRequest, SourceItemCreateRequest
from app.api.v1.source_items import create_source_item
from app.generate.service import generate_carousel_artifact_draft
from app.models.enums import ArtifactStatus


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


@unittest.skipIf(TEST_ENGINE is None, "Postgres is not reachable for carousel persist tests")
class CarouselPersistTests(unittest.TestCase):
    """1.4d: generate inserts a draft Artifact readable via GET schema."""

    def setUp(self) -> None:
        """Open a session on the reachable test engine."""

        if TEST_ENGINE is None:
            self.skipTest("Postgres is not reachable for carousel persist tests")

        self.SessionFactory: sessionmaker[Session] = sessionmaker(
            bind=TEST_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.our_database_session: Session = self.SessionFactory()
        self.temporary_directory: TemporaryDirectory[str] = TemporaryDirectory()
        self.storage_directory: Path = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        """Close the session and drop the tmp artifact store."""

        if getattr(self, "our_database_session", None) is not None:
            self.our_database_session.close()

        if getattr(self, "temporary_directory", None) is not None:
            self.temporary_directory.cleanup()

    def test_generate_persists_draft_readable_via_get_schema(self) -> None:
        """New draft each generate; GET returns slides with asset_ref."""

        run_suffix: str = uuid.uuid4().hex[:8]
        created_brand = create_brand(
            BrandCreateRequest(slug=f"carousel-{run_suffix}", name="Carousel Brand"),
            self.our_database_session,
        )
        created_source_item = create_source_item(
            SourceItemCreateRequest(
                brand_id=created_brand.id,
                title="Carousel persist source",
                interest_heading="Persist heading",
                overview_bullets=["first claim", "second claim"],
                canonical_url="https://spotmu.com/interest/carousel-persist",
                external_key=f"carousel-{run_suffix}",
            ),
            self.our_database_session,
        )
        created_cluster = create_cluster(
            ClusterCreateRequest(
                brand_id=created_brand.id,
                slug=f"carousel-lane-{run_suffix}",
                name="Carousel lane",
            ),
            self.our_database_session,
        )
        first_artifact = generate_carousel_artifact_draft(
            created_source_item.id,
            self.our_database_session,
            cluster_id=created_cluster.id,
            artifact_storage_directory=self.storage_directory,
        )
        self.our_database_session.commit()
        fetched_artifact = get_artifact_by_id(
            first_artifact.id,
            self.our_database_session,
        )
        second_artifact = generate_carousel_artifact_draft(
            created_source_item.id,
            self.our_database_session,
            cluster_id=created_cluster.id,
            artifact_storage_directory=self.storage_directory,
        )
        self.our_database_session.commit()

        self.assertEqual(fetched_artifact.status, ArtifactStatus.DRAFT)
        self.assertEqual(fetched_artifact.format, "carousel")
        self.assertEqual(fetched_artifact.brand_id, created_brand.id)
        self.assertEqual(fetched_artifact.source_item_id, created_source_item.id)
        self.assertEqual(fetched_artifact.cluster_id, created_cluster.id)
        self.assertTrue(fetched_artifact.caption)
        self.assertEqual(
            fetched_artifact.cta_url,
            "https://spotmu.com/interest/carousel-persist",
        )
        self.assertIsNotNone(fetched_artifact.slides)
        serialized_slides: list[object] = fetched_artifact.slides or []
        self.assertGreaterEqual(len(serialized_slides), 3)

        for slide_object in serialized_slides:
            self.assertIsInstance(slide_object, dict)

            if not isinstance(slide_object, dict):
                self.fail("each slide must be a JSON object")

            self.assertIn("role", slide_object)
            self.assertIn("text", slide_object)
            self.assertIn("asset_ref", slide_object)
            asset_reference: object = slide_object["asset_ref"]

            self.assertIsInstance(asset_reference, str)

            if not isinstance(asset_reference, str):
                self.fail("asset_ref must be a string")

            stored_path: Path = self.storage_directory / asset_reference

            self.assertTrue(stored_path.is_file())

        self.assertNotEqual(first_artifact.id, second_artifact.id)
        self.assertEqual(second_artifact.status, ArtifactStatus.DRAFT)
        self.assertEqual(first_artifact.template_id, "spotmu_paper_v1")

        bold_artifact = generate_carousel_artifact_draft(
            created_source_item.id,
            self.our_database_session,
            cluster_id=created_cluster.id,
            artifact_storage_directory=self.storage_directory,
            template_id="spotmu_bold_v1",
        )
        self.our_database_session.commit()

        self.assertEqual(bold_artifact.template_id, "spotmu_bold_v1")
        self.assertNotEqual(bold_artifact.id, first_artifact.id)


if __name__ == "__main__":
    unittest.main()
