"""Assemble live slides into review rows. Drafts and the old queue stay out."""

import os
import tempfile
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.carousel_assembly import assemble_carousel
from app.api.v1.carousel_writes import create_carousel, create_slide
from app.api.v1.router import api_v1_router
from app.api.v1.schemas import CarouselCreateRequest, CarouselReadResponse, SlideWriteRequest
from app.auth.passwords import hash_plain_password
from app.carousels.final_assembly import TOO_FEW_LIVE_SLIDES_DETAIL
from app.db import get_our_database_session
from app.models.artifact import Artifact
from app.models.campaign import CampaignCarousel
from app.models.carousel import Carousel, Slide, SlideDraftBatch
from app.models.enums import OpsUserRole, SlideTextStatus
from app.models.ops_user import OpsUser
from app.models.post_job import PostJob
from app.settings import clear_settings_cache
from tests.test_carousel_writes import _MemoryCarouselSession
from tests.test_carousels import _default_source_from_catalog


READER_USERNAME: str = "reader-agent"
READER_PASSWORD: str = "correct-horse-battery"
PATCHED_CAP: int = 5
PNG_SIGNATURE: bytes = b"\x89PNG\r\n\x1a\n"


class CarouselAssemblyRouteTests(unittest.TestCase):
    """POST assemble stores the grouped frames and leaves the old routes alone."""

    def setUp(self) -> None:
        """Point frame files at a temporary store."""

        self.storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["ARTIFACT_STORAGE_DIR"] = self.storage.name
        clear_settings_cache()

    def tearDown(self) -> None:
        """Restore the artifact directory and drop the settings cache."""

        self.storage.cleanup()

        if self.previous_storage is None:
            os.environ.pop("ARTIFACT_STORAGE_DIR", None)
        else:
            os.environ["ARTIFACT_STORAGE_DIR"] = self.previous_storage

        clear_settings_cache()

    def test_six_live_slides_become_two_draft_carousels(self) -> None:
        """A cap of 5 stores five frames and one. A draft slide stays out."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Harbor final", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        _add_live_slides(session, created.id, 6)
        draft_slide: Slide = _add_pending_draft(carousel)
        before_foreign: int = _foreign_row_count(session)
        added: list[object] = []
        original_add = session.add

        def record_add(row: object) -> None:
            added.append(row)
            original_add(row)

        session.add = record_add  # type: ignore[method-assign]

        with patch(
            "app.carousels.final_assembly.slide_count_or_global_default",
            return_value=PATCHED_CAP,
        ) as patched_count:
            first: CarouselReadResponse = assemble_carousel(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        patched_count.assert_called_once_with(None)
        assert first.assembly is not None
        groups: list[int] = [len(group.frames) for group in first.assembly.carousels]
        frame_slide_ids: set[uuid.UUID] = {
            frame.slide_id
            for group in first.assembly.carousels
            for frame in group.frames
            if frame.slide_id is not None
        }
        first_refs: list[str] = _asset_refs(carousel)

        self.assertEqual(groups, [5, 1])
        self.assertEqual(first.assembly.slide_count, PATCHED_CAP)
        self.assertEqual(first.assembly.generation_number, carousel.generation_number)
        self.assertEqual(first.live_slide_count, 6)
        self.assertIsNotNone(first.pending_slide_draft_batch)
        assert first.pending_slide_draft_batch is not None
        self.assertEqual(first.pending_slide_draft_batch.status, "pending")
        self.assertNotIn(draft_slide.id, frame_slide_ids)

        for group in first.assembly.carousels:
            self.assertEqual(group.status, "draft")
            self.assertEqual(group.caption, "Harbor final")
            self.assertIsNone(group.cta_url)

        for asset_ref in first_refs:
            self.assertTrue(asset_ref.startswith("assembled/"))
            png_path: Path = Path(self.storage.name) / asset_ref
            self.assertEqual(png_path.read_bytes()[:8], PNG_SIGNATURE)

        self.assertEqual(_foreign_row_count(session), before_foreign)
        self.assertFalse(any(isinstance(row, (Artifact, CampaignCarousel, PostJob)) for row in added))

        with patch(
            "app.carousels.final_assembly.slide_count_or_global_default",
            return_value=PATCHED_CAP,
        ):
            second: CarouselReadResponse = assemble_carousel(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        assert second.assembly is not None
        second_refs: list[str] = _asset_refs(carousel)

        self.assertEqual(second.assembly.id, first.assembly.id)
        self.assertEqual(len(list(carousel.assemblies)), 1)
        self.assertEqual([len(group.frames) for group in second.assembly.carousels], [5, 1])

        for asset_ref in first_refs:
            self.assertFalse((Path(self.storage.name) / asset_ref).exists())

        for asset_ref in second_refs:
            self.assertTrue((Path(self.storage.name) / asset_ref).is_file())

    def test_one_live_slide_is_refused_and_writes_nothing(self) -> None:
        """A single live slide does not store an assembly or a PNG."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="One", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        _add_live_slides(session, created.id, 1)
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as refused:
            assemble_carousel(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        self.assertEqual(refused.exception.status_code, 400)
        self.assertEqual(refused.exception.detail, TOO_FEW_LIVE_SLIDES_DETAIL)
        self.assertEqual(list(carousel.assemblies), [])
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(list(Path(self.storage.name).rglob("*.png")), [])

    def test_a_failed_draw_leaves_no_png_and_no_assembly_row(self) -> None:
        """A draw error deletes the PNGs from that call and stores no row."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Broken", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        _add_live_slides(session, created.id, 2)
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        calls: dict[str, int] = {"count": 0}
        original_render = __import__(
            "app.carousels.final_assembly",
            fromlist=["render_assembled_frame"],
        ).render_assembled_frame

        def fail_on_second(*args: object, **kwargs: object) -> object:
            calls["count"] += 1

            if calls["count"] > 1:
                raise RuntimeError("draw failed")

            return original_render(*args, **kwargs)

        with patch(
            "app.carousels.final_assembly.slide_count_or_global_default",
            return_value=PATCHED_CAP,
        ):
            with patch(
                "app.carousels.final_assembly.render_assembled_frame",
                side_effect=fail_on_second,
            ):
                with self.assertRaises(RuntimeError):
                    assemble_carousel(
                        created.id,
                        session,  # type: ignore[arg-type]
                        None,
                    )

        self.assertEqual(list(carousel.assemblies), [])
        self.assertEqual(list(Path(self.storage.name).rglob("*.png")), [])

    def test_default_assembles_and_stays_six_live_slides(self) -> None:
        """Default's six packaged slides assemble. The live count stays six."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel: Carousel = _default_source_from_catalog()
        session.carousels.append(carousel)

        with patch(
            "app.carousels.final_assembly.slide_count_or_global_default",
            return_value=8,
        ):
            assembled: CarouselReadResponse = assemble_carousel(
                carousel.id,
                session,  # type: ignore[arg-type]
                None,
            )

        assert assembled.assembly is not None
        frame_count: int = sum(len(group.frames) for group in assembled.assembly.carousels)

        self.assertEqual(assembled.live_slide_count, 6)
        self.assertEqual(frame_count, 6)
        self.assertEqual(assembled.name, carousel.name)

    def test_a_reader_is_rejected(self) -> None:
        """A reader cannot assemble."""

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
            response = client.post(f"/api/v1/carousels/{uuid.uuid4()}/assemble")
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


def _add_live_slides(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    slide_count: int,
) -> None:
    """Store live slides with no picture. The skeleton does not need one."""

    for index in range(slide_count):
        create_slide(
            carousel_id,
            SlideWriteRequest(name=f"Live {index + 1}"),
            session,  # type: ignore[arg-type]
            None,
        )


def _add_pending_draft(carousel: Carousel) -> Slide:
    """Append a draft slide that belongs to a pending set."""

    batch: SlideDraftBatch = SlideDraftBatch(
        id=uuid.uuid4(),
        carousel_id=carousel.id,
        status="pending",
        slide_count=3,
    )
    draft: Slide = Slide(
        id=uuid.uuid4(),
        carousel_id=carousel.id,
        position=100,
        name="Pending",
        text_status=SlideTextStatus.DRAFT,
        draft_batch_id=batch.id,
    )
    draft.element_texts = []
    draft.exclusions = []
    draft.draft_batch = batch
    carousel.draft_batches.append(batch)
    carousel.slides.append(draft)

    return draft


def _asset_refs(carousel: Carousel) -> list[str]:
    """Return every frame path currently on the carousel's assemblies."""

    asset_refs: list[str] = []

    for assembly in list(carousel.assemblies):

        for assembled in list(assembly.assembled_carousels):

            for frame in list(assembled.frames):
                asset_refs.append(frame.asset_ref)

    return asset_refs


def _foreign_row_count(session: _MemoryCarouselSession) -> int:
    """Return how many artifact, campaign-carousel, and post-job rows the session sees."""

    artifact_count: int = len(session.scalars(select(Artifact)).all())
    campaign_count: int = len(session.scalars(select(CampaignCarousel)).all())
    post_job_count: int = len(session.scalars(select(PostJob)).all())
    foreign_count: int = artifact_count + campaign_count + post_job_count

    return foreign_count


class _ReaderSession:
    """Enough of a session to sign in a reader."""

    def __init__(self, reader: OpsUser) -> None:
        self.ops_users: list[OpsUser] = [reader]

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        """Return the reader by id."""

        if model is OpsUser:

            for stored_user in self.ops_users:

                if stored_user.id == row_id:

                    return stored_user

        return None

    def scalars(self, statement: object) -> object:
        """Return the reader for a login query."""

        username: str | None = None

        if hasattr(statement, "compile"):
            compiled_parameters: dict[str, object] = dict(
                getattr(statement.compile(), "params", {}) or {},
            )

            for parameter_value in compiled_parameters.values():

                if isinstance(parameter_value, str):
                    username = parameter_value

                    break

        matched: list[OpsUser] = [
            stored_user
            for stored_user in self.ops_users
            if username is None or stored_user.username == username
        ]

        return _Rows(matched)


class _Rows:
    """Stand-in for a scalar result."""

    def __init__(self, rows: list[object]) -> None:
        self._rows: list[object] = rows

    def all(self) -> list[object]:
        return list(self._rows)

    def first(self) -> object | None:
        """Return the first row, or None when the query matched nothing."""

        if len(self._rows) == 0:

            return None

        return self._rows[0]


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
    session: _ReaderSession = _ReaderSession(reader)
    application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield session  # type: ignore[misc]

    application.dependency_overrides[get_our_database_session] = override_database_session
    application.include_router(api_v1_router)

    return TestClient(application)


if __name__ == "__main__":
    unittest.main()
