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
from app.api.v1.carousel_writes import create_carousel, create_slide, patch_carousel_step
from app.api.v1.carousels import get_carousel
from app.api.v1.router import api_v1_router
from app.api.v1.schemas import (
    CarouselCreateRequest,
    CarouselReadResponse,
    CarouselStepPatchRequest,
    SlideWriteRequest,
)
from app.carousels.slide_skeleton import (
    FINAL_LOCKED_DETAIL,
    SLIDES_LOCKED_DETAIL,
    CarouselStepState,
)
from app.models.album import AlbumImage
from app.auth.passwords import hash_plain_password
from app.carousels.final_assembly import TOO_FEW_LIVE_SLIDES_DETAIL
from app.db import get_our_database_session
from app.models.artifact import Artifact
from app.models.campaign import CampaignCarousel
from app.models.carousel import Carousel, Slide, SlideDraftBatch
from app.models.enums import BackgroundKind, OpsUserRole, SlideTextStatus
from app.models.ops_user import OpsUser
from app.models.post_job import PostJob
from app.settings import clear_settings_cache
from tests.test_api_routes import _openapi_methods_by_path
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

    def test_a_reader_can_get_the_frozen_frame(self) -> None:
        """A reader receives the PNG. The album file route and generate stay."""

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
        frame_id: uuid.UUID = assembled.assembly.carousels[0].frames[0].id
        album_image: AlbumImage | None = carousel.slides[0].album_image
        assert album_image is not None
        previous_secret: str | None = os.environ.get("SESSION_SECRET")
        previous_secure: str | None = os.environ.get("SESSION_COOKIE_SECURE")
        os.environ["SESSION_SECRET"] = "test-session-secret-not-for-production"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        clear_settings_cache()
        client: TestClient = _reader_client(session)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": READER_USERNAME, "password": READER_PASSWORD},
        )
        frame_url: str = (
            f"/api/v1/carousels/{carousel.id}/assembly/frames/{frame_id}/file"
        )
        secret_path: Path = Path(self.storage.name).resolve().parent / "twerva-secret-frame.png"
        secret_path.write_bytes(b"NOT-A-PNG-SECRET")

        try:
            frame_response = client.get(frame_url)
            unknown_response = client.get(
                f"/api/v1/carousels/{carousel.id}/assembly/frames/{uuid.uuid4()}/file",
            )
            album_response = client.get(
                f"/api/v1/albums/{album_image.album_id}/images/{album_image.id}/file",
            )
            stored_frame = _frame_by_id(carousel, frame_id)
            assert stored_frame is not None
            stored_frame.asset_ref = "assembled/missing-frame.png"
            missing_response = client.get(frame_url)
            stored_frame.asset_ref = "../twerva-secret-frame.png"
            escaped_response = client.get(frame_url)
        finally:
            secret_path.unlink(missing_ok=True)
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

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)

        self.assertEqual(login.status_code, 200)
        self.assertEqual(frame_response.status_code, 200)
        self.assertTrue(frame_response.content.startswith(PNG_SIGNATURE))
        self.assertEqual(unknown_response.status_code, 404)
        self.assertEqual(album_response.status_code, 200)
        self.assertTrue(album_response.content.startswith(b"\xff\xd8\xff"))
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(escaped_response.status_code, 404)
        self.assertNotIn(b"NOT-A-PNG-SECRET", escaped_response.content)
        self.assertIn("post", methods_by_path["/api/v1/generate/carousel"])

    def test_final_step_follows_live_slides_and_the_assembly(self) -> None:
        """Two live slides make Final available. Assemble marks it done.

        One live slide stays locked, including after the 400. Step 4 is
        refused. A picture carousel with no album still refuses step 3.
        """

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Step", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        _add_live_slides(session, created.id, 1)
        one_slide: CarouselReadResponse = get_carousel(
            created.id,
            session,  # type: ignore[arg-type]
        )

        with self.assertRaises(HTTPException) as refused:
            assemble_carousel(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        still_one: CarouselReadResponse = get_carousel(
            created.id,
            session,  # type: ignore[arg-type]
        )

        self.assertEqual(one_slide.steps.final, CarouselStepState.LOCKED)
        self.assertEqual(refused.exception.status_code, 400)
        self.assertEqual(refused.exception.detail, TOO_FEW_LIVE_SLIDES_DETAIL)
        self.assertEqual(still_one.steps.final, CarouselStepState.LOCKED)
        self.assertIsNone(still_one.assembly)

        _add_live_slides(session, created.id, 1)
        two_slides: CarouselReadResponse = get_carousel(
            created.id,
            session,  # type: ignore[arg-type]
        )

        with patch(
            "app.carousels.final_assembly.slide_count_or_global_default",
            return_value=PATCHED_CAP,
        ):
            assembled: CarouselReadResponse = assemble_carousel(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        with self.assertRaises(HTTPException) as final_step:
            patch_carousel_step(
                created.id,
                CarouselStepPatchRequest(editor_step=4),
                session,  # type: ignore[arg-type]
                None,
            )

        stored: CarouselReadResponse = get_carousel(
            created.id,
            session,  # type: ignore[arg-type]
        )

        self.assertEqual(two_slides.steps.final, CarouselStepState.AVAILABLE)
        self.assertIsNone(two_slides.assembly)
        self.assertEqual(assembled.steps.final, CarouselStepState.DONE)
        self.assertEqual(final_step.exception.status_code, 400)
        self.assertEqual(final_step.exception.detail, FINAL_LOCKED_DETAIL)
        self.assertEqual(stored.editor_step, created.editor_step)
        self.assertEqual(stored.steps.final, CarouselStepState.DONE)

        picture: _MemoryCarouselSession = _MemoryCarouselSession()
        picture.skeleton.background_kind = BackgroundKind.PICTURE
        picture.skeleton.elements = []
        picture_carousel: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Plates", skeleton_id=picture.skeleton.id),
            picture,  # type: ignore[arg-type]
            None,
        )

        with self.assertRaises(HTTPException) as slides_step:
            patch_carousel_step(
                picture_carousel.id,
                CarouselStepPatchRequest(editor_step=3),
                picture,  # type: ignore[arg-type]
                None,
            )

        picture_loaded: CarouselReadResponse = get_carousel(
            picture_carousel.id,
            picture,  # type: ignore[arg-type]
        )

        self.assertEqual(slides_step.exception.status_code, 400)
        self.assertEqual(slides_step.exception.detail, SLIDES_LOCKED_DETAIL)
        self.assertEqual(picture_loaded.editor_step, 0)
        self.assertEqual(picture_loaded.steps.slides, CarouselStepState.LOCKED)


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
    """Enough of a session to sign in a reader and read assembled frames."""

    def __init__(
        self,
        reader: OpsUser,
        carousel_session: _MemoryCarouselSession | None = None,
    ) -> None:
        self.ops_users: list[OpsUser] = [reader]
        self.carousel_session: _MemoryCarouselSession | None = carousel_session

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        """Return the reader, or a row from the carousel session."""

        if model is OpsUser:

            for stored_user in self.ops_users:

                if stored_user.id == row_id:

                    return stored_user

        if self.carousel_session is None:

            return None

        found: object | None = self.carousel_session.get(model, row_id)

        return found

    def scalars(self, statement: object) -> object:
        """Return the reader for a login query, otherwise the carousel rows."""

        if "ops_users" in str(statement):
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

        if self.carousel_session is None:

            return _Rows([])

        carousel_rows: object = self.carousel_session.scalars(statement)

        return carousel_rows


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


def _frame_by_id(carousel: Carousel, frame_id: uuid.UUID) -> object | None:
    """Return one stored frame from the in-memory carousel."""

    for assembly in list(carousel.assemblies):

        for assembled in list(assembly.assembled_carousels):

            for frame in list(assembled.frames):

                if frame.id == frame_id:

                    return frame

    return None


def _reader_client(carousel_session: _MemoryCarouselSession | None = None) -> TestClient:
    """Sign-in client whose only user is a reader.

    When a carousel session is passed, its rows are visible to the same
    request. Login still resolves the reader.
    """

    now: datetime = datetime.now(timezone.utc)
    reader: OpsUser = OpsUser(
        id=uuid.uuid4(),
        username=READER_USERNAME,
        password_hash=hash_plain_password(READER_PASSWORD),
        role=OpsUserRole.READER,
        created_at=now,
        updated_at=now,
    )
    session: _ReaderSession = _ReaderSession(reader, carousel_session)
    application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield session  # type: ignore[misc]

    application.dependency_overrides[get_our_database_session] = override_database_session
    application.include_router(api_v1_router)

    return TestClient(application)


if __name__ == "__main__":
    unittest.main()
