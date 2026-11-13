"""Generate a draft set from instructions, research, and the album."""

import os
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.carousel_text import (
    accept_slide_draft_batch,
    generate_slide_collection,
)
from app.api.v1.carousel_writes import create_carousel, create_slide
from app.api.v1.carousels import get_carousel
from app.api.v1.router import api_v1_router
from app.api.v1.schemas import (
    CarouselCreateRequest,
    CarouselReadResponse,
    SlideElementTextWrite,
    SlideReadResponse,
    SlideWriteRequest,
)
from app.auth.passwords import hash_plain_password
from app.carousels.slide_collection import (
    EMPTY_ALBUM_DETAIL,
    EMPTY_BATCH_DETAIL,
    NO_ALBUM_DETAIL,
    NO_INSTRUCTION_TEXT_DETAIL,
    PENDING_BATCH_DETAIL,
)
from app.carousels.slide_skeleton import IMAGE_REQUIRED_DETAIL, CarouselStepState
from app.carousels.slide_text_review import slide_counts_as_live
from app.carousels.text_generation import (
    GENERATE_DISABLED_DETAIL,
    TEXT_GENERATION_FAILED_DETAIL,
    FakeTextGenerationProvider,
    TextGenerationError,
)
from app.db import get_our_database_session
from app.models.album import Album, AlbumImage
from app.models.carousel import (
    Carousel,
    CarouselInstruction,
    CarouselResearchItem,
    Slide,
    SlideDraftBatch,
    SlideElementText,
)
from app.models.enums import (
    BackgroundKind,
    OpsUserRole,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
    SlideTextStatus,
)
from app.models.ops_user import OpsUser
from app.models.research_item import ResearchItem
from app.settings import clear_settings_cache
from tests.test_carousel_writes import _MemoryCarouselSession, _title_element
from tests.test_carousels import _default_source_from_catalog


READER_USERNAME: str = "reader-agent"
READER_PASSWORD: str = "correct-horse-battery"
PATCHED_SLIDE_COUNT: int = 4


class SlideCollectionRouteTests(unittest.TestCase):
    """The collection route drafts a set and leaves older slides alone."""

    def setUp(self) -> None:
        """Point Generate at the fake provider for this case."""

        self.previous_provider: str | None = os.environ.get("TEXT_GENERATION_PROVIDER")
        self.previous_api_key: str | None = os.environ.get("OPENAI_API_KEY")
        os.environ["TEXT_GENERATION_PROVIDER"] = "fake"
        os.environ["OPENAI_API_KEY"] = ""
        clear_settings_cache()

    def tearDown(self) -> None:
        """Restore the provider env and drop the settings cache."""

        self._restore("TEXT_GENERATION_PROVIDER", self.previous_provider)
        self._restore("OPENAI_API_KEY", self.previous_api_key)
        clear_settings_cache()

    def test_generate_appends_the_patched_count_and_a_second_post_is_refused(self) -> None:
        """Two documents, two research items, and two images become one pending set."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element = _title_element(session.skeleton.id)
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = [text_element]
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Harbor set", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        image_ids: list[uuid.UUID] = _attach_album(session, carousel)
        _attach_instructions(carousel, ["Harbor fog", "Keep it short"])
        _attach_research(session, carousel)
        _attach_older_draft(session, carousel, text_element.id)
        generation_number: int = carousel.generation_number

        with patch(
            "app.carousels.slide_collection.slide_count_or_global_default",
            return_value=PATCHED_SLIDE_COUNT,
        ) as patched_count:
            drafted: CarouselReadResponse = generate_slide_collection(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        patched_count.assert_called_once_with(None)
        generated: list[SlideReadResponse] = [
            slide for slide in drafted.slides if slide.name.startswith("Drafted slide ")
        ]
        earlier = next(slide for slide in drafted.slides if slide.name == "Earlier")
        expected_draft: str = "Title. Harbor fog\n\nKeep it short"

        self.assertEqual(len(generated), PATCHED_SLIDE_COUNT)
        self.assertEqual(len(drafted.slides), PATCHED_SLIDE_COUNT + 1)
        self.assertEqual(drafted.live_slide_count, 0)
        self.assertEqual(drafted.generation_number, generation_number)
        self.assertEqual(len(drafted.research), 2)
        self.assertEqual(len(drafted.instructions), 2)
        self.assertIsNotNone(drafted.pending_slide_draft_batch)
        assert drafted.pending_slide_draft_batch is not None
        self.assertEqual(drafted.pending_slide_draft_batch.status, "pending")
        self.assertEqual(drafted.pending_slide_draft_batch.slide_count, PATCHED_SLIDE_COUNT)
        self.assertEqual(drafted.steps.slides, CarouselStepState.DONE)
        self.assertEqual(earlier.text_status, SlideTextStatus.DRAFT)
        self.assertIsNone(earlier.draft_batch_id)
        self.assertEqual(earlier.texts[0].value, "Live leftover")
        self.assertEqual(earlier.draft_texts[0].value, "OLD DRAFT")

        for index, slide in enumerate(generated):
            self.assertEqual(slide.name, f"Drafted slide {index + 1}")
            self.assertEqual(slide.text_status, SlideTextStatus.DRAFT)
            self.assertEqual(slide.texts[0].value, "")
            self.assertEqual(slide.draft_texts[0].value, expected_draft)
            self.assertIn("Harbor fog", slide.draft_texts[0].value)
            self.assertIn("Keep it short", slide.draft_texts[0].value)
            self.assertEqual(slide.draft_batch_id, drafted.pending_slide_draft_batch.id)
            self.assertEqual(slide.excluded_slide_ids, [])
            self.assertEqual(slide.images[0].id, image_ids[index % len(image_ids)])

        with self.assertRaises(HTTPException) as refused:
            generate_slide_collection(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        reloaded: CarouselReadResponse = get_carousel(
            created.id,
            session,  # type: ignore[arg-type]
        )

        self.assertEqual(refused.exception.status_code, 409)
        self.assertEqual(refused.exception.detail, PENDING_BATCH_DETAIL)
        self.assertEqual(len(reloaded.slides), PATCHED_SLIDE_COUNT + 1)

    def test_default_without_instruction_text_is_refused(self) -> None:
        """Default stays six live slides when Generate has no instruction text."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        default_carousel: Carousel = _default_source_from_catalog()
        session.add(default_carousel)

        with self.assertRaises(HTTPException) as refused:
            generate_slide_collection(
                default_carousel.id,
                session,  # type: ignore[arg-type]
                None,
            )

        self.assertEqual(refused.exception.status_code, 400)
        self.assertEqual(refused.exception.detail, NO_INSTRUCTION_TEXT_DETAIL)
        self.assertEqual(len(default_carousel.slides), 6)
        self.assertTrue(
            all(slide_counts_as_live(slide) for slide in default_carousel.slides),
        )

    def test_picture_carousel_without_an_album_is_refused(self) -> None:
        """A picture skeleton with no album does not call the provider."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = [_title_element(session.skeleton.id)]
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="No album", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        _attach_instructions(carousel, ["Harbor fog"])

        with self.assertRaises(HTTPException) as refused:
            generate_slide_collection(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        self.assertEqual(refused.exception.status_code, 400)
        self.assertEqual(refused.exception.detail, NO_ALBUM_DETAIL)
        self.assertEqual(created.slides, [])
        self.assertEqual(len(carousel.slides), 0)

    def test_provider_off_writes_nothing(self) -> None:
        """Generate off is 409 and leaves the carousel without slides."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.elements = [_title_element(session.skeleton.id)]
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Provider off", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        _attach_instructions(carousel, ["Harbor fog"])
        os.environ["TEXT_GENERATION_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = ""
        clear_settings_cache()

        with self.assertRaises(HTTPException) as refused:
            generate_slide_collection(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        self.assertEqual(refused.exception.status_code, 409)
        self.assertEqual(refused.exception.detail, GENERATE_DISABLED_DETAIL)
        self.assertEqual(len(carousel.slides), 0)
        self.assertEqual(list(carousel.draft_batches), [])

    def test_an_empty_album_and_a_provider_failure_write_nothing(self) -> None:
        """No images is 400. A provider error is 502. Neither stores a batch."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = [_title_element(session.skeleton.id)]
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Empty album", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        _attach_instructions(carousel, ["Harbor fog"])
        empty_album: Album = Album(id=uuid.uuid4(), name="Empty", slug="empty-album")
        empty_album.images = []
        session.add(empty_album)
        carousel.album_id = empty_album.id
        carousel.album = empty_album

        with self.assertRaises(HTTPException) as empty:
            generate_slide_collection(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        self.assertEqual(empty.exception.status_code, 400)
        self.assertEqual(empty.exception.detail, EMPTY_ALBUM_DETAIL)
        _attach_album(session, carousel)

        def fail_collection(self: FakeTextGenerationProvider, *args: object) -> None:
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

        with patch.object(
            FakeTextGenerationProvider,
            "draft_slide_collection",
            fail_collection,
        ):
            with self.assertRaises(HTTPException) as failed:
                generate_slide_collection(
                    created.id,
                    session,  # type: ignore[arg-type]
                    None,
                )

        self.assertEqual(failed.exception.status_code, 502)
        self.assertEqual(failed.exception.detail, TEXT_GENERATION_FAILED_DETAIL)
        self.assertEqual(len(carousel.slides), 0)
        self.assertEqual(list(carousel.draft_batches), [])

    def test_a_reader_is_rejected(self) -> None:
        """A reader cannot generate a set."""

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
            response = client.post(f"/api/v1/carousels/{uuid.uuid4()}/slides/generate-collection")
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

    def test_accept_makes_the_set_live_and_leaves_other_slides(self) -> None:
        """Three drafted slides go live. An older draft and a hand slide stay."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element = _title_element(session.skeleton.id)
        session.skeleton.elements = [text_element]
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Accept set", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        _attach_instructions(carousel, ["Harbor fog", "Keep it short"])
        hand: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(
                name="Hand",
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=text_element.id,
                        value="Kept live",
                    ),
                ],
            ),
            session,  # type: ignore[arg-type]
            None,
        )
        _attach_older_draft(session, carousel, text_element.id, position=1)
        generation_number: int = carousel.generation_number

        with patch(
            "app.carousels.slide_collection.slide_count_or_global_default",
            return_value=3,
        ):
            drafted: CarouselReadResponse = generate_slide_collection(
                created.id,
                session,  # type: ignore[arg-type]
                None,
            )

        assert drafted.pending_slide_draft_batch is not None
        batch_id: uuid.UUID = drafted.pending_slide_draft_batch.id
        accepted: CarouselReadResponse = accept_slide_draft_batch(
            created.id,
            batch_id,
            session,  # type: ignore[arg-type]
            None,
        )
        generated: list[SlideReadResponse] = [
            slide for slide in accepted.slides if slide.name.startswith("Drafted slide ")
        ]
        earlier = next(slide for slide in accepted.slides if slide.name == "Earlier")
        kept = next(slide for slide in accepted.slides if slide.id == hand.id)
        expected_value: str = "Title. Harbor fog\n\nKeep it short"
        stored_generated: dict[str, Slide] = {
            slide.name: slide
            for slide in carousel.slides
            if slide.name.startswith("Drafted slide ")
        }

        self.assertEqual(len(generated), 3)
        self.assertIsNone(accepted.pending_slide_draft_batch)
        self.assertEqual(accepted.generation_number, generation_number)
        self.assertEqual(accepted.live_slide_count, 4)
        self.assertEqual(earlier.text_status, SlideTextStatus.DRAFT)
        self.assertIsNone(earlier.draft_batch_id)
        self.assertEqual(earlier.texts[0].value, "Live leftover")
        self.assertEqual(earlier.draft_texts[0].value, "OLD DRAFT")
        self.assertEqual(kept.text_status, SlideTextStatus.LIVE)
        self.assertEqual(kept.texts[0].value, "Kept live")
        self.assertEqual(kept.draft_texts, [])
        self.assertIsNone(kept.draft_batch_id)

        for index, slide in enumerate(generated):
            self.assertEqual(slide.name, f"Drafted slide {index + 1}")
            self.assertEqual(slide.text_status, SlideTextStatus.LIVE)
            self.assertEqual(slide.texts[0].value, expected_value)
            self.assertEqual(slide.draft_texts, [])
            self.assertEqual(slide.draft_batch_id, batch_id)
            self.assertEqual(slide.excluded_slide_ids, [])
            self.assertIsNone(stored_generated[slide.name].element_texts[0].draft_value)
            self.assertIsNone(stored_generated[slide.name].album_image_id)
            self.assertEqual(stored_generated[slide.name].name, slide.name)

        self.assertEqual(carousel.draft_batches[0].status, "accepted")

        with self.assertRaises(HTTPException) as refused:
            accept_slide_draft_batch(
                created.id,
                batch_id,
                session,  # type: ignore[arg-type]
                None,
            )

        reloaded: CarouselReadResponse = get_carousel(
            created.id,
            session,  # type: ignore[arg-type]
        )
        reloaded_earlier = next(slide for slide in reloaded.slides if slide.name == "Earlier")
        reloaded_hand = next(slide for slide in reloaded.slides if slide.id == hand.id)

        self.assertEqual(refused.exception.status_code, 404)
        self.assertEqual(reloaded_earlier.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(reloaded_earlier.texts[0].value, "Live leftover")
        self.assertEqual(reloaded_earlier.draft_texts[0].value, "OLD DRAFT")
        self.assertEqual(reloaded_hand.texts[0].value, "Kept live")
        self.assertIsNone(reloaded.pending_slide_draft_batch)

    def test_accept_refuses_an_empty_set_and_a_picture_slide_without_an_image(self) -> None:
        """No slides stays pending. A picture slide without an image stays draft."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element = _title_element(session.skeleton.id)
        session.skeleton.elements = [text_element]
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Empty set", skeleton_id=session.skeleton.id),
            session,  # type: ignore[arg-type]
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)  # type: ignore[assignment]
        assert carousel is not None
        empty_batch_id: uuid.UUID = uuid.uuid4()
        empty_batch: SlideDraftBatch = SlideDraftBatch(
            id=empty_batch_id,
            carousel_id=carousel.id,
            status="pending",
            slide_count=3,
        )
        empty_batch.carousel = carousel

        with self.assertRaises(HTTPException) as empty:
            accept_slide_draft_batch(
                created.id,
                empty_batch_id,
                session,  # type: ignore[arg-type]
                None,
            )

        self.assertEqual(empty.exception.status_code, 400)
        self.assertEqual(empty.exception.detail, EMPTY_BATCH_DETAIL)
        self.assertEqual(empty_batch.status, "pending")

        session.skeleton.background_kind = BackgroundKind.PICTURE
        picture_batch_id: uuid.UUID = uuid.uuid4()
        picture_batch: SlideDraftBatch = SlideDraftBatch(
            id=picture_batch_id,
            carousel_id=carousel.id,
            status="pending",
            slide_count=1,
        )
        picture_batch.carousel = carousel
        picture_slide: Slide = Slide(
            id=uuid.uuid4(),
            carousel_id=carousel.id,
            position=0,
            name="No image",
            text_status=SlideTextStatus.DRAFT,
            draft_batch_id=picture_batch_id,
        )
        picture_slide.draft_batch = picture_batch
        picture_slide.element_texts = [
            SlideElementText(
                id=uuid.uuid4(),
                slide_id=picture_slide.id,
                skeleton_element_id=text_element.id,
                value="",
                draft_value="Still draft",
            ),
        ]
        picture_slide.exclusions = []
        session.add(picture_slide)

        with self.assertRaises(HTTPException) as missing_image:
            accept_slide_draft_batch(
                created.id,
                picture_batch_id,
                session,  # type: ignore[arg-type]
                None,
            )

        self.assertEqual(missing_image.exception.status_code, 400)
        self.assertEqual(missing_image.exception.detail, IMAGE_REQUIRED_DETAIL)
        self.assertEqual(picture_slide.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(picture_slide.element_texts[0].value, "")
        self.assertEqual(picture_slide.element_texts[0].draft_value, "Still draft")
        self.assertEqual(picture_batch.status, "pending")

    def test_a_reader_cannot_accept_a_set(self) -> None:
        """A reader cannot accept a generated set."""

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
                f"/api/v1/carousels/{uuid.uuid4()}/slide-draft-batches/{uuid.uuid4()}/accept",
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

    def _restore(self, name: str, previous: str | None) -> None:
        """Put one environment variable back."""

        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _attach_album(
    session: _MemoryCarouselSession,
    carousel: Carousel,
) -> list[uuid.UUID]:
    """Attach two images and return their ids in position order."""

    album: Album = Album(id=uuid.uuid4(), name="Harbor", slug=f"harbor-{uuid.uuid4().hex[:8]}")
    first_id: uuid.UUID = uuid.uuid4()
    second_id: uuid.UUID = uuid.uuid4()
    album.images = [
        _image(album.id, first_id, 0, "Night quay"),
        _image(album.id, second_id, 1, "Dunes"),
    ]
    session.add(album)
    carousel.album_id = album.id
    carousel.album = album

    return [first_id, second_id]


def _image(
    album_id: uuid.UUID,
    image_id: uuid.UUID,
    position: int,
    alt_text: str,
) -> AlbumImage:
    """One stored album image. No file bytes."""

    image: AlbumImage = AlbumImage(
        id=image_id,
        album_id=album_id,
        position=position,
        relative_path=f"albums/{image_id}.jpg",
        media_type=SlideImageMediaType.JPEG,
        byte_size=1200,
        width=640,
        height=480,
        alt_text=alt_text,
        license=SlideImageLicense.CC0,
        source="Commons",
        license_note="",
        intake=SlideImageIntake.UPLOAD,
    )

    return image


def _attach_instructions(carousel: Carousel, bodies: list[str]) -> None:
    """Store instruction documents in the given order."""

    documents: list[CarouselInstruction] = []

    for position, body in enumerate(bodies):
        document: CarouselInstruction = CarouselInstruction(
            id=uuid.uuid4(),
            carousel_id=carousel.id,
            position=position,
            body=body,
        )
        documents.append(document)

    carousel.instructions = documents


def _attach_research(session: _MemoryCarouselSession, carousel: Carousel) -> None:
    """Attach two research documents. The bodies stay on the research rows."""

    links: list[CarouselResearchItem] = []

    for position, title in enumerate(("Tide notes", "Quay facts")):
        research_item: ResearchItem = ResearchItem(
            id=uuid.uuid4(),
            title=title,
            slug=f"{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
            body="The water is still." if position == 0 else "",
        )
        session.add(research_item)
        link: CarouselResearchItem = CarouselResearchItem(
            id=uuid.uuid4(),
            carousel_id=carousel.id,
            research_item_id=research_item.id,
            position=position,
        )
        link.research_item = research_item
        links.append(link)

    carousel.research_links = links


def _attach_older_draft(
    session: _MemoryCarouselSession,
    carousel: Carousel,
    skeleton_element_id: uuid.UUID,
    position: int = 0,
) -> None:
    """Add one draft slide that is not part of a generated set."""

    slide: Slide = Slide(
        id=uuid.uuid4(),
        carousel_id=carousel.id,
        position=position,
        name="Earlier",
        text_status=SlideTextStatus.DRAFT,
    )
    slide.element_texts = [
        SlideElementText(
            id=uuid.uuid4(),
            slide_id=slide.id,
            skeleton_element_id=skeleton_element_id,
            value="Live leftover",
            draft_value="OLD DRAFT",
        ),
    ]
    slide.exclusions = []
    session.add(slide)


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
