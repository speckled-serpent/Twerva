"""Replace the current generation snapshot from the working rows."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func, select, text
from starlette.datastructures import UploadFile
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.v1.albums import patch_album, upload_album_image
from app.api.v1.carousel_assembly import assemble_carousel
from app.api.v1.carousel_generations import get_carousel_generation
from app.api.v1.carousels import get_carousel, list_carousels
from app.api.v1.carousel_text import (
    accept_slide_draft_batch,
    discard_slide_draft_batch,
    generate_slide_collection,
)
from app.api.v1.carousel_writes import (
    create_carousel,
    create_slide,
    delete_carousel_album,
    delete_carousel_instruction,
    delete_carousel_research,
    delete_slide,
    patch_carousel_instruction,
    patch_slide,
    post_carousel_album,
    post_carousel_instruction,
    post_carousel_research,
    put_carousel_album,
    put_carousel_instructions,
    put_carousel_research,
)
from app.api.v1.research import delete_research, patch_research
from app.api.v1.skeleton_elements import create_skeleton_element
from app.carousels.image_store import LocalAlbumImageStore
from app.api.v1.schemas import (
    CarouselAlbumAttachRequest,
    CarouselAlbumCreateRequest,
    AlbumImageWrite,
    AlbumPatchRequest,
    CarouselCreateRequest,
    CarouselInstructionCreateRequest,
    CarouselInstructionOrderRequest,
    CarouselInstructionPatchRequest,
    CarouselResearchAttachRequest,
    CarouselResearchOrderRequest,
    ResearchPatchRequest,
    SkeletonElementCreateRequest,
    SlideElementTextWrite,
    SlideWriteRequest,
)
from app.api.v1.router import api_v1_router
from app.auth.passwords import hash_plain_password
from app.carousels.default_carousel import default_album_carousel_id
from app.carousels.editing import new_row_id
from app.db import get_our_database_session
from app.carousels.generations import replace_current_generation_snapshot
from app.models.album import Album, AlbumImage
from app.models.artifact import Artifact
from app.models.campaign import CampaignCarousel
from app.models.carousel import (
    INSTRUCTION_BODY_MAX_CHARACTERS,
    Carousel,
    CarouselAssembly,
    CarouselGeneration,
    CarouselGenerationImage,
    CarouselGenerationInstruction,
    CarouselGenerationResearch,
    CarouselGenerationSlide,
    CarouselGenerationSlideText,
    CarouselInstruction,
    CarouselResearchItem,
    Slide,
    SlideDraftBatch,
    SlideElementText,
    SlideExclusion,
)
from app.models.ops_user import OpsUser
from app.models.post_job import PostJob
from app.models.enums import (
    OpsUserRole,
    AdvertisementType,
    BackgroundKind,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonStatus,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
    SlideTextStatus,
)
from app.models.research_item import ResearchItem
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
OLDER_BODY: str = "Older line"
BLANK_BODY: str = ""
KEPT_BODY: str = "Keep the harbor."
STALE_BODY: str = "Wrong"
LIVE_VALUE: str = "Reviewed line"
DRAFT_VALUE: str = "Unreviewed line"
FIRST_RESEARCH_TITLE: str = "Tides"
FIRST_RESEARCH_BODY: str = "The water is cold."
SECOND_RESEARCH_TITLE: str = "Quay"
SECOND_RESEARCH_BODY: str = "The stones are wet."


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


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for generation tests")
class ReplaceCurrentGenerationSnapshotTests(unittest.TestCase):
    """The current snapshot matches the working rows. An older generation stays."""

    def setUp(self) -> None:
        """Create an empty database at the current head."""

        self.database_name: str = f"twerva_genrep_{uuid.uuid4().hex[:10]}"
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
        alembic_config: Config = Config(str(SERVER_ROOT / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(SERVER_ROOT / "alembic"))
        command.upgrade(alembic_config, "head")

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

    def test_replace_copies_the_working_rows_and_leaves_the_other_generation(self) -> None:
        """Generation 1 matches the carousel. Generation 2 keeps its own body."""

        with Session(self.database_engine) as session:
            element: SkeletonElement = self._text_element(session)
            carousel: Carousel = self._full_carousel(session, element)
            older: CarouselGeneration = self._older_generation(session, carousel)
            self._stale_current_generation(session, carousel)
            empty: Carousel = self._empty_carousel(session, element.skeleton_id)
            self._stale_current_generation(session, empty)
            before_counts: tuple[int, int, int] = self._foreign_counts(session)
            working_slide_ids: set[uuid.UUID] = {slide.id for slide in list(carousel.slides)}
            session.commit()
            carousel_id: uuid.UUID = carousel.id
            empty_id: uuid.UUID = empty.id
            older_id: uuid.UUID = older.id

        with Session(self.database_engine) as session:
            replace_current_generation_snapshot(carousel_id, session)
            session.commit()

        with Session(self.database_engine) as session:
            self._assert_full_snapshot(session, carousel_id)
            self._assert_older_generation(session, older_id)
            self.assertEqual(self._working_slide_ids(session, carousel_id), working_slide_ids)
            self.assertEqual(self._generation_number(session, carousel_id), 1)
            self.assertEqual(self._foreign_counts(session), before_counts)
            replace_current_generation_snapshot(carousel_id, session)
            session.commit()

        with Session(self.database_engine) as session:
            self._assert_full_snapshot(session, carousel_id)
            self._assert_older_generation(session, older_id)
            self.assertEqual(self._working_slide_ids(session, carousel_id), working_slide_ids)
            replace_current_generation_snapshot(empty_id, session)
            session.commit()

        with Session(self.database_engine) as session:
            self._assert_empty_snapshot(session, empty_id)
            self._assert_older_generation(session, older_id)
            self._assert_full_snapshot(session, carousel_id)
            self.assertEqual(self._foreign_counts(session), before_counts)

    def test_carousel_writes_refresh_generation_one_only(self) -> None:
        """Create, instructions, research, and the album update generation 1."""

        with Session(self.database_engine) as session:
            element: SkeletonElement = self._text_element(session)
            before_counts: tuple[int, int, int] = self._foreign_counts(session)
            created: CarouselReadResponse = create_carousel(
                CarouselCreateRequest(name="Harbor", skeleton_id=element.skeleton_id),
                session,  # type: ignore[arg-type]
                None,
            )
            other: CarouselReadResponse = create_carousel(
                CarouselCreateRequest(name="Other", skeleton_id=element.skeleton_id),
                session,  # type: ignore[arg-type]
                None,
            )
            carousel: Carousel | None = session.get(Carousel, created.id)
            assert carousel is not None
            older: CarouselGeneration = self._older_generation(session, carousel)
            session.commit()
            self._assert_empty_snapshot(session, created.id)
            self._assert_empty_snapshot(session, other.id)
            saved: CarouselReadResponse = post_carousel_instruction(
                created.id,
                CarouselInstructionCreateRequest(body=KEPT_BODY),
                session,  # type: ignore[arg-type]
                None,
            )
            patched: CarouselReadResponse = patch_carousel_instruction(
                created.id,
                saved.instructions[0].id,
                CarouselInstructionPatchRequest(body="Keep the tide."),
                session,  # type: ignore[arg-type]
                None,
            )
            put_carousel_instructions(
                created.id,
                CarouselInstructionOrderRequest(instruction_ids=[patched.instructions[0].id]),
                session,  # type: ignore[arg-type]
                None,
            )

            with self.assertRaises(HTTPException) as too_long:
                patch_carousel_instruction(
                    created.id,
                    patched.instructions[0].id,
                    CarouselInstructionPatchRequest(
                        body="x" * (INSTRUCTION_BODY_MAX_CHARACTERS + 1),
                    ),
                    session,  # type: ignore[arg-type]
                    None,
                )

            research: ResearchItem = ResearchItem(
                id=new_row_id(),
                title=FIRST_RESEARCH_TITLE,
                slug=f"tides-{uuid.uuid4().hex[:8]}",
                body=FIRST_RESEARCH_BODY,
            )
            session.add(research)
            session.commit()
            post_carousel_research(
                created.id,
                CarouselResearchAttachRequest(research_item_id=research.id),
                session,  # type: ignore[arg-type]
                None,
            )
            put_carousel_research(
                created.id,
                CarouselResearchOrderRequest(research_item_ids=[research.id]),
                session,  # type: ignore[arg-type]
                None,
            )
            album: Album = Album(
                id=new_row_id(),
                name="Harbor photos",
                slug=f"harbor-photos-{uuid.uuid4().hex[:8]}",
            )
            album.images = [
                _album_image(album.id, 0, f"albums/write-{uuid.uuid4().hex[:8]}.png"),
                _album_image(album.id, 1, f"albums/write-{uuid.uuid4().hex[:8]}.png"),
            ]
            session.add(album)
            session.commit()
            put_carousel_album(
                created.id,
                CarouselAlbumAttachRequest(album_id=album.id),
                session,  # type: ignore[arg-type]
                None,
            )
            post_carousel_album(
                other.id,
                CarouselAlbumCreateRequest(name="Side album"),
                session,  # type: ignore[arg-type]
                None,
            )
            self.assertEqual(too_long.exception.status_code, 400)
            self._assert_write_snapshot(session, created.id, album.id)
            self._assert_older_generation(session, older.id)
            self.assertEqual(self._instruction_bodies_for(session, other.id), [])
            self.assertEqual(self._research_titles_for(session, other.id), [])
            delete_carousel_album(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )
            cleared: CarouselGeneration = self._current_generation_for(session, created.id)

            self.assertIsNone(cleared.album_id)
            self.assertEqual(list(cleared.images), [])
            self.assertEqual(self._instruction_bodies_for(session, created.id), ["Keep the tide."])
            delete_carousel_instruction(
                created.id,
                patched.instructions[0].id,
                session,  # type: ignore[arg-type]
                None,
            )
            delete_carousel_research(
                created.id,
                research.id,
                session,  # type: ignore[arg-type]
                None,
            )

            self.assertEqual(self._instruction_bodies_for(session, created.id), [])
            self.assertEqual(self._research_titles_for(session, created.id), [])
            self.assertEqual(self._generation_number(session, created.id), 1)
            self._assert_older_generation(session, older.id)
            self.assertEqual(self._foreign_counts(session), before_counts)

    def test_slide_writes_refresh_generation_one(self) -> None:
        """Slide edits, a generated set, and a new text element update generation 1."""

        previous_provider: str | None = os.environ.get("TEXT_GENERATION_PROVIDER")
        os.environ["TEXT_GENERATION_PROVIDER"] = "fake"
        clear_settings_cache()

        try:
            with Session(self.database_engine) as session:
                element: SkeletonElement = self._text_element(session)
                created = create_carousel(
                    CarouselCreateRequest(name="Slides", skeleton_id=element.skeleton_id),
                    session,  # type: ignore[arg-type]
                    None,
                )
                first = create_slide(
                    created.id,
                    _slide_write(element.id, "Quay", "Reviewed line"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._assert_snapshot_slides(
                    session,
                    created.id,
                    [("Quay", SlideTextStatus.LIVE, "Reviewed line", None)],
                )
                patch_slide(
                    created.id,
                    first.id,
                    _slide_write(element.id, "Pier", "New line"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._assert_snapshot_slides(
                    session,
                    created.id,
                    [("Pier", SlideTextStatus.LIVE, "New line", None)],
                )
                second = create_slide(
                    created.id,
                    _slide_write(element.id, "Dock", "Beside"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                patch_slide(
                    created.id,
                    first.id,
                    _slide_write(element.id, "Pier", "New line", [second.id]),
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._assert_exclusion_pair(session, created.id, first.id, second.id)
                delete_slide(
                    created.id,
                    second.id,
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._assert_snapshot_slides(
                    session,
                    created.id,
                    [("Pier", SlideTextStatus.LIVE, "New line", None)],
                )
                post_carousel_instruction(
                    created.id,
                    CarouselInstructionCreateRequest(body=KEPT_BODY),
                    session,  # type: ignore[arg-type]
                    None,
                )

                with patch(
                    "app.carousels.slide_collection.slide_count_or_global_default",
                    return_value=1,
                ):
                    generated = generate_slide_collection(
                        created.id,
                        session,  # type: ignore[arg-type]
                        None,
                    )

                assert generated.pending_slide_draft_batch is not None
                drafted_value: str = f"Claim. {KEPT_BODY}"
                self._assert_snapshot_slides(
                    session,
                    created.id,
                    [
                        ("Pier", SlideTextStatus.LIVE, "New line", None),
                        ("Drafted slide 1", SlideTextStatus.DRAFT, "", drafted_value),
                    ],
                )
                self.assertEqual(self._batch_statuses(session, created.id), ["pending"])
                accept_slide_draft_batch(
                    created.id,
                    generated.pending_slide_draft_batch.id,
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._assert_snapshot_slides(
                    session,
                    created.id,
                    [
                        ("Pier", SlideTextStatus.LIVE, "New line", None),
                        ("Drafted slide 1", SlideTextStatus.LIVE, drafted_value, None),
                    ],
                )

                with patch(
                    "app.carousels.slide_collection.slide_count_or_global_default",
                    return_value=1,
                ):
                    second_set = generate_slide_collection(
                        created.id,
                        session,  # type: ignore[arg-type]
                        None,
                    )

                assert second_set.pending_slide_draft_batch is not None
                discard_slide_draft_batch(
                    created.id,
                    second_set.pending_slide_draft_batch.id,
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._assert_snapshot_slides(
                    session,
                    created.id,
                    [
                        ("Pier", SlideTextStatus.LIVE, "New line", None),
                        ("Drafted slide 1", SlideTextStatus.LIVE, drafted_value, None),
                    ],
                )
                added: SkeletonElementReadResponse = create_skeleton_element(
                    element.skeleton_id,
                    SkeletonElementCreateRequest(
                        name="Aside",
                        band=SkeletonElementBand.BOTTOM,
                        content_kind=SkeletonElementContentKind.TEXT,
                        font_family="Georgia",
                        font_size=24,
                        font_color="#222222",
                        alignment=SkeletonElementAlignment.LEFT,
                    ),
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._assert_empty_element_on_snapshot(session, created.id, added.id)
                self.assertEqual(self._generation_number(session, created.id), 1)
        finally:
            if previous_provider is None:
                os.environ.pop("TEXT_GENERATION_PROVIDER", None)
            else:
                os.environ["TEXT_GENERATION_PROVIDER"] = previous_provider

            clear_settings_cache()

    def test_shared_album_and_research_refresh_generation_one_only(self) -> None:
        """An album or research edit updates generation 1 and leaves generation 2."""

        with Session(self.database_engine) as session:
            element: SkeletonElement = self._text_element(session)
            created = create_carousel(
                CarouselCreateRequest(name="Shared", skeleton_id=element.skeleton_id),
                session,  # type: ignore[arg-type]
                None,
            )
            album: Album = Album(
                id=new_row_id(),
                name="Harbor photos",
                slug=f"shared-photos-{uuid.uuid4().hex[:8]}",
            )
            session.add(album)
            session.commit()
            put_carousel_album(
                created.id,
                CarouselAlbumAttachRequest(album_id=album.id),
                session,  # type: ignore[arg-type]
                None,
            )

            with tempfile.TemporaryDirectory() as storage_directory:
                store: LocalAlbumImageStore = LocalAlbumImageStore(Path(storage_directory))

                with patch(
                    "app.api.v1.albums.configured_album_image_store",
                    return_value=store,
                ):
                    first = upload_album_image(
                        album.id,
                        _upload("one.jpg"),
                        SlideImageLicense.CC0,
                        "bench",
                        "One",
                        "",
                        session,  # type: ignore[arg-type]
                        None,
                    )
                    second = upload_album_image(
                        album.id,
                        _upload("two.jpg"),
                        SlideImageLicense.CC0,
                        "bench",
                        "Two",
                        "",
                        session,  # type: ignore[arg-type]
                        None,
                    )

                self.assertEqual(
                    self._snapshot_image_ids(session, created.id, 1),
                    [first.id, second.id],
                )
                older: CarouselGeneration = self._generation_with_image_and_research(
                    session,
                    created.id,
                    first.id,
                )
                session.commit()

                with patch(
                    "app.api.v1.albums.configured_album_image_store",
                    return_value=store,
                ):
                    third = upload_album_image(
                        album.id,
                        _upload("three.jpg"),
                        SlideImageLicense.CC0,
                        "bench",
                        "Three",
                        "",
                        session,  # type: ignore[arg-type]
                        None,
                    )

                self.assertEqual(
                    self._snapshot_image_ids(session, created.id, 1),
                    [first.id, second.id, third.id],
                )
                self.assertEqual(self._generation_image_ids(session, older.id), [first.id])
                patch_album(
                    album.id,
                    AlbumPatchRequest(
                        name="Harbor photos",
                        images=[
                            _image_write(third.id),
                            _image_write(first.id),
                            _image_write(second.id),
                        ],
                    ),
                    session,  # type: ignore[arg-type]
                    None,
                )
                self.assertEqual(
                    self._snapshot_image_ids(session, created.id, 1),
                    [third.id, first.id, second.id],
                )
                self.assertEqual(self._generation_image_ids(session, older.id), [first.id])
                research: ResearchItem = ResearchItem(
                    id=new_row_id(),
                    title=FIRST_RESEARCH_TITLE,
                    slug=f"shared-tides-{uuid.uuid4().hex[:8]}",
                    body=FIRST_RESEARCH_BODY,
                )
                session.add(research)
                session.commit()
                post_carousel_research(
                    created.id,
                    CarouselResearchAttachRequest(research_item_id=research.id),
                    session,  # type: ignore[arg-type]
                    None,
                )
                self._copy_research_onto_generation(session, older.id, research)
                session.commit()
                patch_research(
                    research.id,
                    ResearchPatchRequest(title=FIRST_RESEARCH_TITLE, body="The water is warm."),
                    session,  # type: ignore[arg-type]
                    None,
                )
                self.assertEqual(
                    self._snapshot_research_bodies(session, created.id, 1),
                    ["The water is warm."],
                )
                self.assertEqual(
                    self._generation_research(session, older.id),
                    (FIRST_RESEARCH_TITLE, FIRST_RESEARCH_BODY, research.id),
                )
                delete_research(
                    research.id,
                    session,  # type: ignore[arg-type]
                    None,
                )
                session.expire_all()

                self.assertEqual(self._snapshot_research_bodies(session, created.id, 1), [])
                self.assertEqual(
                    self._generation_research(session, older.id),
                    (FIRST_RESEARCH_TITLE, FIRST_RESEARCH_BODY, None),
                )
                self.assertEqual(self._generation_number(session, created.id), 1)

    def test_detail_lists_generations_and_a_reader_can_read_one(self) -> None:
        """The detail summarizes generation 1. A reader can read that snapshot."""

        previous_secret: str | None = os.environ.get("SESSION_SECRET")
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["SESSION_SECRET"] = "test-session-secret-not-for-production"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            with Session(self.database_engine) as session:
                element: SkeletonElement = self._text_element(session)
                created = create_carousel(
                    CarouselCreateRequest(name="Readable", skeleton_id=element.skeleton_id),
                    session,  # type: ignore[arg-type]
                    None,
                )
                post_carousel_instruction(
                    created.id,
                    CarouselInstructionCreateRequest(body=KEPT_BODY),
                    session,  # type: ignore[arg-type]
                    None,
                )
                research: ResearchItem = ResearchItem(
                    id=new_row_id(),
                    title=FIRST_RESEARCH_TITLE,
                    slug=f"readable-{uuid.uuid4().hex[:8]}",
                    body=FIRST_RESEARCH_BODY,
                )
                session.add(research)
                session.commit()
                post_carousel_research(
                    created.id,
                    CarouselResearchAttachRequest(research_item_id=research.id),
                    session,  # type: ignore[arg-type]
                    None,
                )
                create_slide(
                    created.id,
                    _slide_write(element.id, "Quay", "Reviewed line"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                create_slide(
                    created.id,
                    _slide_write(element.id, "Dock", "Beside"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                detail = get_carousel(
                    created.id,
                    session,  # type: ignore[arg-type]
                )
                listed = list_carousels(session)  # type: ignore[arg-type]

                self.assertEqual(len(detail.generations), 1)
                self.assertEqual(detail.generations[0].generation_number, 1)
                self.assertEqual(detail.generations[0].instruction_count, 1)
                self.assertEqual(detail.generations[0].research_count, 1)
                self.assertEqual(detail.generations[0].image_count, 0)
                self.assertEqual(detail.generations[0].slide_count, 2)
                self.assertFalse(detail.generations[0].has_assembly)

                for item in listed:
                    self.assertNotIn("generations", item.model_dump())

                with self.assertRaises(HTTPException) as missing_generation:
                    get_carousel_generation(
                        created.id,
                        2,
                        session,  # type: ignore[arg-type]
                        None,
                    )

                self.assertEqual(missing_generation.exception.status_code, 404)
                reader: OpsUser = OpsUser(
                    id=new_row_id(),
                    username="generation-reader",
                    password_hash=hash_plain_password("correct-horse-battery"),
                    role=OpsUserRole.READER,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(reader)
                session.commit()
                client: TestClient = _reader_client(session)
                login = client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "generation-reader",
                        "password": "correct-horse-battery",
                    },
                )
                snapshot = client.get(f"/api/v1/carousels/{created.id}/generations/1")

                self.assertEqual(login.status_code, 200)
                self.assertEqual(snapshot.status_code, 200)
                self.assertEqual(snapshot.json()["instructions"][0]["body"], KEPT_BODY)
                self.assertEqual(snapshot.json()["research"][0]["body"], FIRST_RESEARCH_BODY)
                self.assertNotIn("frames", snapshot.json())
                assembled = assemble_carousel(
                    created.id,
                    session,  # type: ignore[arg-type]
                    None,
                )
                after = get_carousel(
                    created.id,
                    session,  # type: ignore[arg-type]
                )

                self.assertTrue(after.generations[0].has_assembly)
                assert assembled.assembly is not None
                frame_id: uuid.UUID = assembled.assembly.carousels[0].frames[0].id
                frame = client.get(
                    f"/api/v1/carousels/{created.id}/assembly/frames/{frame_id}/file",
                )

                self.assertEqual(frame.status_code, 200)
                self.assertTrue(frame.content.startswith(b"\x89PNG\r\n\x1a\n"))
        finally:
            storage.cleanup()

            if previous_secret is None:
                os.environ.pop("SESSION_SECRET", None)
            else:
                os.environ["SESSION_SECRET"] = previous_secret

            os.environ.pop("SESSION_COOKIE_SECURE", None)

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def test_duplicate_starts_the_next_generation(self) -> None:
        """Duplicate freezes generation 1 and copies the working rows onto the next number."""

        previous_secret: str | None = os.environ.get("SESSION_SECRET")
        previous_secure: str | None = os.environ.get("SESSION_COOKIE_SECURE")
        previous_storage: str | None = os.environ.get("ARTIFACT_STORAGE_DIR")
        os.environ["SESSION_SECRET"] = "test-session-secret-not-for-production"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        storage: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        os.environ["ARTIFACT_STORAGE_DIR"] = storage.name
        clear_settings_cache()

        try:
            with Session(self.database_engine) as session:
                element: SkeletonElement = self._text_element(session)
                created = create_carousel(
                    CarouselCreateRequest(name="Harbor", skeleton_id=element.skeleton_id),
                    session,  # type: ignore[arg-type]
                    None,
                )
                first = create_slide(
                    created.id,
                    _slide_write(element.id, "Quay", "Reviewed line"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                create_slide(
                    created.id,
                    _slide_write(element.id, "Dock", "Beside"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                assembled = assemble_carousel(
                    created.id,
                    session,  # type: ignore[arg-type]
                    None,
                )
                batch: SlideDraftBatch = SlideDraftBatch(
                    id=new_row_id(),
                    carousel_id=created.id,
                    status="pending",
                    slide_count=2,
                )
                session.add(batch)
                session.commit()
                stored: Carousel | None = session.get(Carousel, created.id)
                assert stored is not None
                assert assembled.assembly is not None
                slide_ids: set[uuid.UUID] = {slide.id for slide in list(stored.slides)}
                copied_at_call: list[SlideCopy] = self._working_slide_copies(session, created.id)
                before_counts: tuple[int, int, int] = self._publish_counts(session)
                before_files: int = _stored_file_count(storage.name)
                admin: OpsUser = OpsUser(
                    id=new_row_id(),
                    username="generation-admin",
                    password_hash=hash_plain_password("correct-horse-battery"),
                    role=OpsUserRole.ADMIN,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                reader: OpsUser = OpsUser(
                    id=new_row_id(),
                    username="generation-reader",
                    password_hash=hash_plain_password("correct-horse-battery"),
                    role=OpsUserRole.READER,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(admin)
                session.add(reader)
                session.commit()
                admin_client: TestClient = _reader_client(session)
                reader_client: TestClient = _reader_client(session)
                admin_login = admin_client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "generation-admin",
                        "password": "correct-horse-battery",
                    },
                )
                reader_login = reader_client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "generation-reader",
                        "password": "correct-horse-battery",
                    },
                )
                duplicated = admin_client.post(f"/api/v1/carousels/{created.id}/generations")
                duplicated_body = duplicated.json()

                self.assertEqual(admin_login.status_code, 200)
                self.assertEqual(reader_login.status_code, 200)
                self.assertEqual(duplicated.status_code, 200)
                self.assertEqual(duplicated_body["generation_number"], 2)
                self.assertIsNone(duplicated_body["assembly"])
                self.assertEqual(duplicated_body["steps"]["final"], "available")
                self.assertEqual(duplicated_body["name"], stored.name)
                self.assertEqual(duplicated_body["slug"], stored.slug)
                self.assertEqual(duplicated_body["skeleton_id"], str(stored.skeleton_id))
                self.assertEqual(duplicated_body["editor_step"], stored.editor_step)
                self.assertEqual(
                    [item["generation_number"] for item in duplicated_body["generations"]],
                    [1, 2],
                )
                self.assertTrue(duplicated_body["generations"][0]["has_assembly"])
                self.assertFalse(duplicated_body["generations"][1]["has_assembly"])
                self.assertEqual(
                    duplicated_body["pending_slide_draft_batch"]["id"],
                    str(batch.id),
                )
                self.assertEqual(
                    duplicated_body["pending_slide_draft_batch"]["status"],
                    "pending",
                )
                self.assertEqual(
                    {item["id"] for item in duplicated_body["slides"]},
                    {str(slide_id) for slide_id in slide_ids},
                )
                self.assertEqual(self._copied_slides(session, created.id, 1), copied_at_call)
                self.assertEqual(self._copied_slides(session, created.id, 2), copied_at_call)
                self.assertEqual(self._assembly_ids(session, created.id), [assembled.assembly.id])
                self.assertEqual(self._batch_statuses(session, created.id), ["pending"])
                self.assertEqual(self._working_slide_ids(session, created.id), slide_ids)
                self.assertEqual(_stored_file_count(storage.name), before_files)
                patch_slide(
                    created.id,
                    first.id,
                    _slide_write(element.id, "Pier", "New line"),
                    session,  # type: ignore[arg-type]
                    None,
                )
                patched: list[SlideCopy] = self._copied_slides(session, created.id, 2)
                kept: list[SlideCopy] = self._copied_slides(session, created.id, 1)

                self.assertEqual(kept, copied_at_call)
                self.assertEqual(patched[0][1], "Pier")
                self.assertEqual(patched[0][3][0][1], "New line")
                rejected = reader_client.post(f"/api/v1/carousels/{created.id}/generations")

                self.assertEqual(rejected.status_code, 403)
                self.assertEqual(self._generation_number(session, created.id), 2)
                second = admin_client.post(f"/api/v1/carousels/{created.id}/generations")

                self.assertEqual(second.status_code, 200)
                self.assertEqual(second.json()["generation_number"], 3)
                self.assertEqual(
                    [item["generation_number"] for item in second.json()["generations"]],
                    [1, 2, 3],
                )
                self.assertEqual(self._copied_slides(session, created.id, 1), copied_at_call)
                self.assertEqual(self._publish_counts(session), before_counts)
                empty = create_carousel(
                    CarouselCreateRequest(name="Empty", skeleton_id=element.skeleton_id),
                    session,  # type: ignore[arg-type]
                    None,
                )
                empty_duplicated = admin_client.post(
                    f"/api/v1/carousels/{empty.id}/generations",
                )

                self.assertEqual(empty_duplicated.status_code, 200)
                self.assertEqual(empty_duplicated.json()["generation_number"], 2)
                self.assertIsNone(empty_duplicated.json()["assembly"])
                self.assertEqual(empty_duplicated.json()["steps"]["final"], "locked")
                self.assertEqual(empty_duplicated.json()["slides"], [])
                default_carousel: Carousel | None = session.get(
                    Carousel,
                    default_album_carousel_id(),
                )
                assert default_carousel is not None
                default_skeleton_id: uuid.UUID = default_carousel.skeleton_id
                default_slide_ids: set[uuid.UUID] = {
                    slide.id for slide in list(default_carousel.slides)
                }
                default_duplicated = admin_client.post(
                    f"/api/v1/carousels/{default_carousel.id}/generations",
                )

                self.assertEqual(default_duplicated.status_code, 200)
                self.assertEqual(default_duplicated.json()["generation_number"], 2)
                self.assertEqual(
                    default_duplicated.json()["skeleton_id"],
                    str(default_skeleton_id),
                )
                self.assertEqual(default_duplicated.json()["steps"]["final"], "available")
                self.assertEqual(
                    {item["id"] for item in default_duplicated.json()["slides"]},
                    {str(slide_id) for slide_id in default_slide_ids},
                )
                self.assertEqual(self._publish_counts(session), before_counts)
        finally:
            storage.cleanup()

            if previous_secret is None:
                os.environ.pop("SESSION_SECRET", None)
            else:
                os.environ["SESSION_SECRET"] = previous_secret

            if previous_secure is None:
                os.environ.pop("SESSION_COOKIE_SECURE", None)
            else:
                os.environ["SESSION_COOKIE_SECURE"] = previous_secure

            if previous_storage is None:
                os.environ.pop("ARTIFACT_STORAGE_DIR", None)
            else:
                os.environ["ARTIFACT_STORAGE_DIR"] = previous_storage

            clear_settings_cache()

    def _generation_with_image_and_research(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        album_image_id: uuid.UUID,
    ) -> CarouselGeneration:
        """Insert generation 2 with one image the later upload must not change."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation: CarouselGeneration = CarouselGeneration(
            id=new_row_id(),
            carousel_id=carousel.id,
            generation_number=2,
            album_id=carousel.album_id,
        )
        generation.images = [
            CarouselGenerationImage(
                id=new_row_id(),
                generation_id=generation.id,
                position=0,
                album_image_id=album_image_id,
            ),
        ]
        carousel.generations.append(generation)
        session.add(generation)
        session.flush()

        return generation

    def _copy_research_onto_generation(
        self,
        session: Session,
        generation_id: uuid.UUID,
        research: ResearchItem,
    ) -> None:
        """Store the original research text on generation 2."""

        generation: CarouselGeneration | None = session.get(CarouselGeneration, generation_id)
        assert generation is not None
        generation.research_items.append(
            CarouselGenerationResearch(
                id=new_row_id(),
                generation_id=generation.id,
                position=0,
                research_item_id=research.id,
                title=research.title,
                body=research.body,
            ),
        )
        session.flush()

    def _snapshot_image_ids(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        generation_number: int,
    ) -> list[uuid.UUID | None]:
        """Return copied image ids for one generation, in position order."""

        generation: CarouselGeneration = self._generation_by_number(
            session,
            carousel_id,
            generation_number,
        )
        image_ids: list[uuid.UUID | None] = [
            image.album_image_id
            for image in sorted(list(generation.images), key=_position)
        ]

        return image_ids

    def _generation_image_ids(
        self,
        session: Session,
        generation_id: uuid.UUID,
    ) -> list[uuid.UUID | None]:
        """Return one generation's copied image ids."""

        generation: CarouselGeneration | None = session.get(CarouselGeneration, generation_id)
        assert generation is not None
        image_ids: list[uuid.UUID | None] = [
            image.album_image_id
            for image in sorted(list(generation.images), key=_position)
        ]

        return image_ids

    def _snapshot_research_bodies(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        generation_number: int,
    ) -> list[str]:
        """Return copied research bodies for one generation."""

        generation: CarouselGeneration = self._generation_by_number(
            session,
            carousel_id,
            generation_number,
        )
        bodies: list[str] = [
            research.body
            for research in sorted(list(generation.research_items), key=_position)
        ]

        return bodies

    def _generation_research(
        self,
        session: Session,
        generation_id: uuid.UUID,
    ) -> tuple[str, str, uuid.UUID | None]:
        """Return the one copied research title, body, and library id."""

        generation: CarouselGeneration | None = session.get(CarouselGeneration, generation_id)
        assert generation is not None
        session.refresh(generation)
        copied: list[CarouselGenerationResearch] = list(generation.research_items)

        self.assertEqual(len(copied), 1)
        research_row: tuple[str, str, uuid.UUID | None] = (
            copied[0].title,
            copied[0].body,
            copied[0].research_item_id,
        )

        return research_row

    def _generation_by_number(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        generation_number: int,
    ) -> CarouselGeneration:
        """Return one numbered snapshot on a carousel."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None

        for generation in list(carousel.generations):

            if generation.generation_number == generation_number:

                return generation

        self.fail(f"generation {generation_number} is missing")

    def _assert_snapshot_slides(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        expected: list[tuple[str, SlideTextStatus, str, str | None]],
    ) -> None:
        """The current snapshot slides match name, status, value, and draft."""

        generation: CarouselGeneration = self._current_generation_for(session, carousel_id)
        actual: list[tuple[str, SlideTextStatus, str, str | None]] = []

        for slide in sorted(list(generation.slides), key=_position):
            copied_texts: list[CarouselGenerationSlideText] = list(slide.texts)
            value: str = ""
            draft_value: str | None = None

            for copied_text in copied_texts:

                if copied_text.value != "" or copied_text.draft_value not in (None, ""):
                    value = copied_text.value
                    draft_value = copied_text.draft_value

            if value == "" and draft_value in (None, "") and len(copied_texts) > 0:
                value = copied_texts[0].value
                draft_value = copied_texts[0].draft_value

            actual.append((slide.name, slide.text_status, value, draft_value))

        self.assertEqual(actual, expected)

    def _assert_exclusion_pair(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        first_slide_id: uuid.UUID,
        second_slide_id: uuid.UUID,
    ) -> None:
        """Both directions of the pair are on the current snapshot."""

        generation: CarouselGeneration = self._current_generation_for(session, carousel_id)
        pairs: set[tuple[uuid.UUID | None, uuid.UUID | None]] = set()

        for slide in list(generation.slides):

            for exclusion in list(slide.exclusions):
                pairs.add((
                    slide.source_slide_id,
                    exclusion.excluded_generation_slide.source_slide_id,
                ))

        self.assertEqual(
            pairs,
            {
                (first_slide_id, second_slide_id),
                (second_slide_id, first_slide_id),
            },
        )

    def _assert_empty_element_on_snapshot(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        element_id: uuid.UUID,
    ) -> None:
        """Every current snapshot slide stores an empty value for the new element."""

        generation: CarouselGeneration = self._current_generation_for(session, carousel_id)

        self.assertGreater(len(list(generation.slides)), 0)

        for slide in list(generation.slides):
            matched: list[CarouselGenerationSlideText] = [
                copied_text
                for copied_text in list(slide.texts)
                if copied_text.skeleton_element_id == element_id
            ]

            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0].value, "")

    def _batch_statuses(self, session: Session, carousel_id: uuid.UUID) -> list[str]:
        """Return draft-batch statuses for one carousel."""

        batches: list[SlideDraftBatch] = list(
            session.scalars(
                select(SlideDraftBatch).where(SlideDraftBatch.carousel_id == carousel_id),
            ).all(),
        )
        statuses: list[str] = [batch.status for batch in batches]

        return statuses

    def _assert_write_snapshot(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        album_id: uuid.UUID,
    ) -> None:
        """Generation 1 has the saved instruction, research, and album images."""

        generation: CarouselGeneration = self._current_generation_for(session, carousel_id)
        image_ids: list[uuid.UUID | None] = [
            image.album_image_id
            for image in sorted(list(generation.images), key=_position)
        ]

        self.assertEqual(generation.generation_number, 1)
        self.assertEqual(generation.album_id, album_id)
        self.assertEqual(self._instruction_bodies_for(session, carousel_id), ["Keep the tide."])
        self.assertEqual(self._research_titles_for(session, carousel_id), [FIRST_RESEARCH_TITLE])
        self.assertEqual(len(image_ids), 2)
        self.assertEqual(image_ids[0], generation.images[0].album_image_id)

    def _current_generation_for(
        self,
        session: Session,
        carousel_id: uuid.UUID,
    ) -> CarouselGeneration:
        """Return the snapshot for the carousel's current number."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation: CarouselGeneration = self._current_generation(session, carousel)

        return generation

    def _instruction_bodies_for(self, session: Session, carousel_id: uuid.UUID) -> list[str]:
        """Return copied instruction bodies for the current generation."""

        generation: CarouselGeneration = self._current_generation_for(session, carousel_id)
        bodies: list[str] = [
            instruction.body
            for instruction in sorted(list(generation.instructions), key=_position)
        ]

        return bodies

    def _research_titles_for(self, session: Session, carousel_id: uuid.UUID) -> list[str]:
        """Return copied research titles for the current generation."""

        generation: CarouselGeneration = self._current_generation_for(session, carousel_id)
        titles: list[str] = [
            research.title
            for research in sorted(list(generation.research_items), key=_position)
        ]

        return titles

    def _assert_full_snapshot(self, session: Session, carousel_id: uuid.UUID) -> None:
        """The current snapshot matches the two documents, images, and slides."""

        carousel: Carousel = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation: CarouselGeneration = self._current_generation(session, carousel)
        bodies: list[str] = [
            instruction.body
            for instruction in sorted(list(generation.instructions), key=_position)
        ]
        research_rows: list[tuple[str, str]] = [
            (research.title, research.body)
            for research in sorted(list(generation.research_items), key=_position)
        ]
        image_ids: list[uuid.UUID | None] = [
            image.album_image_id
            for image in sorted(list(generation.images), key=_position)
        ]
        album_image_ids: list[uuid.UUID] = [
            image.id for image in sorted(list(carousel.album.images), key=_position)
        ]
        slides: list[CarouselGenerationSlideView] = [
            _slide_view(slide)
            for slide in sorted(list(generation.slides), key=_position)
        ]
        exclusion_pairs: set[tuple[uuid.UUID | None, uuid.UUID | None]] = set()

        for slide in list(generation.slides):

            for exclusion in list(slide.exclusions):
                exclusion_pairs.add((
                    slide.source_slide_id,
                    exclusion.excluded_generation_slide.source_slide_id,
                ))

        self.assertEqual(generation.album_id, carousel.album_id)
        self.assertEqual(bodies, [BLANK_BODY, KEPT_BODY])
        self.assertEqual(
            research_rows,
            [
                (FIRST_RESEARCH_TITLE, FIRST_RESEARCH_BODY),
                (SECOND_RESEARCH_TITLE, SECOND_RESEARCH_BODY),
            ],
        )
        self.assertEqual(image_ids, album_image_ids)
        self.assertEqual(len(slides), 2)
        self.assertEqual(slides[0].name, "Quay")
        self.assertEqual(slides[0].text_status, SlideTextStatus.LIVE)
        self.assertEqual(slides[0].value, LIVE_VALUE)
        self.assertIsNone(slides[0].draft_value)
        self.assertEqual(slides[0].album_image_id, album_image_ids[0])
        self.assertEqual(slides[1].name, "Draft quay")
        self.assertEqual(slides[1].text_status, SlideTextStatus.DRAFT)
        self.assertEqual(slides[1].value, "")
        self.assertEqual(slides[1].draft_value, DRAFT_VALUE)
        self.assertEqual(slides[1].album_image_id, album_image_ids[1])
        self.assertEqual(
            exclusion_pairs,
            {
                (slides[0].source_slide_id, slides[1].source_slide_id),
                (slides[1].source_slide_id, slides[0].source_slide_id),
            },
        )
        self.assertEqual(len(list(carousel.instructions)), 2)
        self.assertEqual(len(list(carousel.research_links)), 2)
        self.assertEqual(len(list(carousel.album.images)), 2)

    def _assert_empty_snapshot(self, session: Session, carousel_id: uuid.UUID) -> None:
        """A carousel with no album and no research stores empty child lists."""

        carousel: Carousel = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation: CarouselGeneration = self._current_generation(session, carousel)

        self.assertIsNone(carousel.album_id)
        self.assertIsNone(generation.album_id)
        self.assertEqual(list(generation.instructions), [])
        self.assertEqual(list(generation.research_items), [])
        self.assertEqual(list(generation.images), [])
        self.assertEqual(list(generation.slides), [])
        self.assertEqual(carousel.generation_number, 1)

    def _assert_older_generation(self, session: Session, generation_id: uuid.UUID) -> None:
        """Generation 2 still has the body it was given."""

        generation: CarouselGeneration | None = session.get(CarouselGeneration, generation_id)

        self.assertIsNotNone(generation)
        assert generation is not None
        bodies: list[str] = [instruction.body for instruction in list(generation.instructions)]

        self.assertEqual(generation.generation_number, 2)
        self.assertEqual(bodies, [OLDER_BODY])

    def _full_carousel(self, session: Session, element: SkeletonElement) -> Carousel:
        """Store two of each working row, including one blank instruction."""

        album: Album = Album(id=new_row_id(), name="Harbor", slug=f"harbor-{uuid.uuid4().hex[:8]}")
        first_image: AlbumImage = _album_image(album.id, 0, "albums/generation-probe-a.png")
        second_image: AlbumImage = _album_image(album.id, 1, "albums/generation-probe-b.png")
        album.images = [first_image, second_image]
        first_research: ResearchItem = ResearchItem(
            id=new_row_id(),
            title=FIRST_RESEARCH_TITLE,
            slug=f"tides-{uuid.uuid4().hex[:8]}",
            body=FIRST_RESEARCH_BODY,
        )
        second_research: ResearchItem = ResearchItem(
            id=new_row_id(),
            title=SECOND_RESEARCH_TITLE,
            slug=f"quay-{uuid.uuid4().hex[:8]}",
            body=SECOND_RESEARCH_BODY,
        )
        carousel: Carousel = Carousel(
            id=new_row_id(),
            skeleton_id=element.skeleton_id,
            name="Harbor",
            slug=f"harbor-{uuid.uuid4().hex[:8]}",
            album_id=album.id,
            generation_number=1,
            editor_step=3,
        )
        carousel.album = album
        carousel.instructions = [
            CarouselInstruction(
                id=new_row_id(),
                carousel_id=carousel.id,
                position=0,
                body=BLANK_BODY,
            ),
            CarouselInstruction(
                id=new_row_id(),
                carousel_id=carousel.id,
                position=1,
                body=KEPT_BODY,
            ),
        ]
        carousel.research_links = [
            CarouselResearchItem(
                id=new_row_id(),
                carousel_id=carousel.id,
                research_item_id=first_research.id,
                position=0,
            ),
            CarouselResearchItem(
                id=new_row_id(),
                carousel_id=carousel.id,
                research_item_id=second_research.id,
                position=1,
            ),
        ]
        carousel.research_links[0].research_item = first_research
        carousel.research_links[1].research_item = second_research
        live_slide: Slide = _slide(
            carousel.id,
            0,
            "Quay",
            SlideTextStatus.LIVE,
            first_image.id,
        )
        draft_slide: Slide = _slide(
            carousel.id,
            1,
            "Draft quay",
            SlideTextStatus.DRAFT,
            second_image.id,
        )
        live_slide.element_texts = [
            _element_text(live_slide.id, element.id, LIVE_VALUE, None),
        ]
        draft_slide.element_texts = [
            _element_text(draft_slide.id, element.id, "", DRAFT_VALUE),
        ]
        live_slide.exclusions = [
            SlideExclusion(
                id=new_row_id(),
                slide_id=live_slide.id,
                excluded_slide_id=draft_slide.id,
            ),
        ]
        draft_slide.exclusions = [
            SlideExclusion(
                id=new_row_id(),
                slide_id=draft_slide.id,
                excluded_slide_id=live_slide.id,
            ),
        ]
        carousel.slides = [live_slide, draft_slide]
        session.add(album)
        session.add(first_research)
        session.add(second_research)
        session.add(carousel)
        session.flush()

        return carousel

    def _empty_carousel(self, session: Session, skeleton_id: uuid.UUID) -> Carousel:
        """Store a carousel with no album, research, instructions, or slides."""

        carousel: Carousel = Carousel(
            id=new_row_id(),
            skeleton_id=skeleton_id,
            name="Empty",
            slug=f"empty-{uuid.uuid4().hex[:8]}",
            album_id=None,
            generation_number=1,
            editor_step=0,
        )
        session.add(carousel)
        session.flush()

        return carousel

    def _older_generation(self, session: Session, carousel: Carousel) -> CarouselGeneration:
        """Insert generation 2 with a body the replace must not change."""

        generation: CarouselGeneration = CarouselGeneration(
            id=new_row_id(),
            carousel_id=carousel.id,
            generation_number=2,
            album_id=None,
        )
        generation.instructions = [
            CarouselGenerationInstruction(
                id=new_row_id(),
                generation_id=generation.id,
                position=0,
                body=OLDER_BODY,
            ),
        ]
        carousel.generations.append(generation)
        session.add(generation)
        session.flush()

        return generation

    def _stale_current_generation(self, session: Session, carousel: Carousel) -> None:
        """Put a wrong body on generation 1 so replace has to delete it."""

        generation: CarouselGeneration = CarouselGeneration(
            id=new_row_id(),
            carousel_id=carousel.id,
            generation_number=1,
            album_id=None,
        )
        generation.instructions = [
            CarouselGenerationInstruction(
                id=new_row_id(),
                generation_id=generation.id,
                position=0,
                body=STALE_BODY,
            ),
        ]
        carousel.generations.append(generation)
        session.add(generation)
        session.flush()

    def _text_element(self, session: Session) -> SkeletonElement:
        """Store one text element the slide texts can point at."""

        skeleton: Skeleton = Skeleton(
            id=new_row_id(),
            name="Probe paper",
            slug=f"probe-paper-{uuid.uuid4().hex[:8]}",
            advertisement_type=AdvertisementType.CAROUSEL,
            status=SkeletonStatus.DRAFT,
            background_kind=BackgroundKind.COLOR,
        )
        element: SkeletonElement = SkeletonElement(
            id=new_row_id(),
            skeleton_id=skeleton.id,
            band=SkeletonElementBand.MIDDLE,
            sort_order=0,
            content_kind=SkeletonElementContentKind.TEXT,
            name="Claim",
            font_family="Georgia",
            font_size=48,
            font_color="#111111",
            alignment=SkeletonElementAlignment.LEFT,
        )
        skeleton.elements = [element]
        session.add(skeleton)
        session.flush()

        return element

    def _current_generation(self, session: Session, carousel: Carousel) -> CarouselGeneration:
        """Return the snapshot whose number matches the carousel."""

        for generation in list(carousel.generations):

            if generation.generation_number == carousel.generation_number:

                return generation

        self.fail("current generation is missing")

    def _working_slide_copies(self, session: Session, carousel_id: uuid.UUID) -> list[SlideCopy]:
        """Return the working slides in the shape a snapshot copy uses."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None
        copies: list[SlideCopy] = []

        for slide in sorted(list(carousel.slides), key=_position):
            texts: tuple[SlideTextCopy, ...] = tuple(
                sorted(
                    (
                        (
                            element_text.skeleton_element_id,
                            element_text.value,
                            element_text.draft_value,
                        )
                        for element_text in list(slide.element_texts)
                    ),
                    key=_text_identity,
                ),
            )
            copies.append((slide.id, slide.name, slide.text_status, texts))

        return copies

    def _copied_slides(
        self,
        session: Session,
        carousel_id: uuid.UUID,
        generation_number: int,
    ) -> list[SlideCopy]:
        """Return one snapshot's slides in the same shape as the working rows."""

        generation: CarouselGeneration = self._generation_by_number(
            session,
            carousel_id,
            generation_number,
        )
        copies: list[SlideCopy] = []

        for slide in sorted(list(generation.slides), key=_position):
            texts: tuple[SlideTextCopy, ...] = tuple(
                sorted(
                    (
                        (
                            copied_text.skeleton_element_id,
                            copied_text.value,
                            copied_text.draft_value,
                        )
                        for copied_text in list(slide.texts)
                    ),
                    key=_text_identity,
                ),
            )
            copies.append((slide.source_slide_id, slide.name, slide.text_status, texts))

        return copies

    def _assembly_ids(self, session: Session, carousel_id: uuid.UUID) -> list[uuid.UUID]:
        """Return the assembly ids stored for one carousel."""

        assemblies: list[CarouselAssembly] = list(
            session.scalars(
                select(CarouselAssembly).where(CarouselAssembly.carousel_id == carousel_id),
            ).all(),
        )
        assembly_ids: list[uuid.UUID] = [assembly.id for assembly in assemblies]

        return assembly_ids

    def _publish_counts(self, session: Session) -> tuple[int, int, int]:
        """Return artifact, campaign-carousel, and post-job counts."""

        artifact_count: int = _table_count(session, Artifact)
        campaign_count: int = _table_count(session, CampaignCarousel)
        post_job_count: int = _table_count(session, PostJob)
        counts: tuple[int, int, int] = (artifact_count, campaign_count, post_job_count)

        return counts

    def _working_slide_ids(self, session: Session, carousel_id: uuid.UUID) -> set[uuid.UUID]:
        """Return the working slide ids. The snapshot must not delete them."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None
        slide_ids: set[uuid.UUID] = {slide.id for slide in list(carousel.slides)}

        return slide_ids

    def _generation_number(self, session: Session, carousel_id: uuid.UUID) -> int:
        """Return the stored generation number."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation_number: int = carousel.generation_number

        return generation_number

    def _foreign_counts(self, session: Session) -> tuple[int, int, int]:
        """Return artifact, campaign-carousel, and draft-batch counts."""

        artifact_count: int = _table_count(session, Artifact)
        campaign_count: int = _table_count(session, CampaignCarousel)
        batch_count: int = _table_count(session, SlideDraftBatch)
        counts: tuple[int, int, int] = (artifact_count, campaign_count, batch_count)

        return counts


SlideTextCopy = tuple[uuid.UUID, str, str | None]
SlideCopy = tuple[uuid.UUID | None, str, SlideTextStatus, tuple[SlideTextCopy, ...]]


class CarouselGenerationSlideView:
    """The copied slide fields the assertion compares."""

    def __init__(
        self,
        source_slide_id: uuid.UUID | None,
        name: str,
        text_status: SlideTextStatus,
        album_image_id: uuid.UUID | None,
        value: str,
        draft_value: str | None,
    ) -> None:
        self.source_slide_id: uuid.UUID | None = source_slide_id
        self.name: str = name
        self.text_status: SlideTextStatus = text_status
        self.album_image_id: uuid.UUID | None = album_image_id
        self.value: str = value
        self.draft_value: str | None = draft_value


def _slide_view(slide: CarouselGenerationSlide) -> CarouselGenerationSlideView:
    """Read one copied slide into the fields the test compares."""

    copied: CarouselGenerationSlide = slide
    copied_texts: list[CarouselGenerationSlideText] = list(copied.texts)
    element_text: CarouselGenerationSlideText | None = None

    if len(copied_texts) > 0:
        element_text = copied_texts[0]

    value: str = "" if element_text is None else element_text.value
    draft_value: str | None = None if element_text is None else element_text.draft_value
    view: CarouselGenerationSlideView = CarouselGenerationSlideView(
        copied.source_slide_id,
        copied.name,
        copied.text_status,
        copied.album_image_id,
        value,
        draft_value,
    )

    return view


def _album_image(album_id: uuid.UUID, position: int, relative_path: str) -> AlbumImage:
    """Return one stored album image. The file itself is not written."""

    image: AlbumImage = AlbumImage(
        id=new_row_id(),
        album_id=album_id,
        position=position,
        relative_path=relative_path,
        media_type=SlideImageMediaType.PNG,
        byte_size=8,
        width=8,
        height=8,
        license=SlideImageLicense.CC0,
        source="probe",
        license_note="",
        intake=SlideImageIntake.UPLOAD,
    )

    return image


def _reader_client(session: Session) -> TestClient:
    """Sign-in client that reads and writes through the test session."""

    application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield session

    application.dependency_overrides[get_our_database_session] = override_database_session
    application.include_router(api_v1_router)

    return TestClient(application)


def _upload(filename: str) -> UploadFile:
    """Return an upload of a tiny JPEG."""

    upload: UploadFile = UploadFile(file=io.BytesIO(_jpeg_bytes()), filename=filename)

    return upload


def _jpeg_bytes() -> bytes:
    """Return a tiny JPEG the intake checks accept."""

    buffer: io.BytesIO = io.BytesIO()
    image: Image.Image = Image.new("RGB", (8, 8), (20, 80, 140))
    image.save(buffer, format="JPEG")

    return buffer.getvalue()


def _image_write(image_id: uuid.UUID) -> AlbumImageWrite:
    """Return the license fields patch_album requires for one image."""

    image_write: AlbumImageWrite = AlbumImageWrite(
        id=image_id,
        license=SlideImageLicense.CC0,
        source="bench",
        license_note="",
        alt_text=None,
    )

    return image_write


def _slide_write(
    element_id: uuid.UUID,
    name: str,
    value: str,
    excluded_slide_ids: list[uuid.UUID] | None = None,
) -> SlideWriteRequest:
    """Return a slide write for the one text element."""

    request: SlideWriteRequest = SlideWriteRequest(
        name=name,
        texts=[SlideElementTextWrite(skeleton_element_id=element_id, value=value)],
        excluded_slide_ids=[] if excluded_slide_ids is None else excluded_slide_ids,
    )

    return request


def _slide(
    carousel_id: uuid.UUID,
    position: int,
    name: str,
    text_status: SlideTextStatus,
    album_image_id: uuid.UUID,
) -> Slide:
    """Return one working slide."""

    slide: Slide = Slide(
        id=new_row_id(),
        carousel_id=carousel_id,
        position=position,
        name=name,
        text_status=text_status,
        album_image_id=album_image_id,
    )

    return slide


def _element_text(
    slide_id: uuid.UUID,
    element_id: uuid.UUID,
    value: str,
    draft_value: str | None,
) -> SlideElementText:
    """Return one working element text."""

    element_text: SlideElementText = SlideElementText(
        id=new_row_id(),
        slide_id=slide_id,
        skeleton_element_id=element_id,
        value=value,
        draft_value=draft_value,
    )

    return element_text


def _text_identity(copied_text: tuple[uuid.UUID, str, str | None]) -> str:
    """Return the skeleton element id used to order copied texts."""

    identity: str = str(copied_text[0])

    return identity


def _stored_file_count(directory: str) -> int:
    """Return how many files the artifact directory holds."""

    file_count: int = 0

    for path in Path(directory).rglob("*"):

        if path.is_file():
            file_count = file_count + 1

    return file_count


def _position(row: object) -> int:
    """Return a stored position."""

    position: int = int(getattr(row, "position"))

    return position


def _table_count(session: Session, model: type[object]) -> int:
    """Return how many rows one mapped table holds."""

    counted: int = int(session.scalar(select(func.count()).select_from(model)) or 0)

    return counted


if __name__ == "__main__":
    unittest.main()
