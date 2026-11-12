"""The carousel detail returns instruction documents. The list does not."""

import os
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone

os.environ.setdefault("TWERVA_ENV", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.carousels import get_carousel
from app.api.v1.router import api_v1_router
from app.api.v1.schemas import CarouselReadResponse
from app.auth.passwords import hash_plain_password
from app.carousels.default_carousel import (
    DEFAULT_ALBUM_SKELETON_ID,
    DEFAULT_ALBUM_SLUG,
)
from app.carousels.slide_skeleton import CarouselStepState
from app.db import get_our_database_session
from app.models.carousel import Carousel, CarouselInstruction
from app.models.enums import OpsUserRole
from app.models.ops_user import OpsUser
from app.models.skeleton import Skeleton
from app.settings import clear_settings_cache
from tests.test_carousels import _default_source_from_catalog, _paper_skeleton, _session_get


READER_USERNAME: str = "reader-agent"
READER_PASSWORD: str = "correct-horse-battery"
COPIED_INSPIRATION: str = "A lamp on the quay"
COPIED_RULES: str = "Keep the tide in the caption"
FIRST_BODY: str = "Open with the quay."
SECOND_BODY: str = "Close on the tide."
LIST_ITEM_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "skeleton_id",
        "name",
        "slug",
        "album_id",
        "generation_number",
        "editor_step",
        "slide_count",
        "created_at",
        "updated_at",
    },
)


def _copied_instruction_body(inspiration: str, rules: str) -> str:
    """Return the document the copy revision stores for two column values."""

    body: str = (
        "## Inspiration\n"
        "\n"
        f"{inspiration}\n"
        "\n"
        "## Rules\n"
        "\n"
        f"{rules}\n"
    )

    return body


class _ScalarResult:
    """Stand-in for ``session.scalars(...).all()`` and ``.first()``."""

    def __init__(self, rows: list[object]) -> None:
        self._rows: list[object] = rows

    def all(self) -> list[object]:
        """Return every row."""

        return list(self._rows)

    def first(self) -> object | None:
        """Return the first row, or None when the query matched nothing."""

        if len(self._rows) == 0:

            return None

        return self._rows[0]


class _InstructionReadSession:
    """Enough of a session to log in a reader and reload two carousels."""

    def __init__(
        self,
        reader: OpsUser,
        carousels: list[Carousel],
        skeleton: Skeleton,
    ) -> None:
        self.ops_users: list[OpsUser] = [reader]
        self.carousels: list[Carousel] = carousels
        self.skeleton: Skeleton = skeleton

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        """Return a user, carousel, or skeleton by id."""

        if model is OpsUser:
            for stored_user in self.ops_users:
                if stored_user.id == row_id:

                    return stored_user

            return None

        if model is Carousel:
            for stored_carousel in self.carousels:
                if stored_carousel.id == row_id:

                    return stored_carousel

            return None

        if model is Skeleton and row_id == self.skeleton.id:

            return self.skeleton

        return None

    def scalars(self, statement: object) -> _ScalarResult:
        """Return the reader for a login query, otherwise the carousels."""

        sql: str = str(statement)

        if "ops_users" in sql:
            username: str | None = _bound_username(statement)
            matched_users: list[OpsUser] = [
                stored_user
                for stored_user in self.ops_users
                if username is None or stored_user.username == username
            ]

            return _ScalarResult(matched_users)

        return _ScalarResult(list(self.carousels))


def _bound_username(statement: object) -> str | None:
    """Return the username bound on a login query, when there is one."""

    if not hasattr(statement, "compile"):

        return None

    compiled_statement = statement.compile()
    compiled_parameters: dict[str, object] = dict(
        getattr(compiled_statement, "params", {}) or {},
    )

    for parameter_value in compiled_parameters.values():
        if isinstance(parameter_value, str):

            return parameter_value

    return None


def _reader() -> OpsUser:
    """Return a reader that can sign in."""

    now: datetime = datetime.now(timezone.utc)
    reader: OpsUser = OpsUser(
        id=uuid.uuid4(),
        username=READER_USERNAME,
        password_hash=hash_plain_password(READER_PASSWORD),
        role=OpsUserRole.READER,
        created_at=now,
        updated_at=now,
    )

    return reader


def _copied_carousel() -> tuple[Carousel, uuid.UUID]:
    """Return a carousel whose guidance was copied into one document."""

    now: datetime = datetime.now(timezone.utc)
    carousel_id: uuid.UUID = uuid.uuid4()
    document_id: uuid.UUID = uuid.uuid4()
    carousel: Carousel = Carousel(
        id=carousel_id,
        skeleton_id=DEFAULT_ALBUM_SKELETON_ID,
        name="Copied guidance",
        slug="copied-guidance",
        inspiration=COPIED_INSPIRATION,
        rules=COPIED_RULES,
        generation_number=1,
        editor_step=3,
        created_at=now,
        updated_at=now,
    )
    document: CarouselInstruction = CarouselInstruction(
        id=document_id,
        carousel_id=carousel_id,
        position=0,
        body=_copied_instruction_body(COPIED_INSPIRATION, COPIED_RULES),
    )
    carousel.slides = []
    carousel.research_links = []
    carousel.instructions = [document]

    return carousel, document_id


def _ordered_carousel() -> Carousel:
    """Return two documents stored out of position order."""

    now: datetime = datetime.now(timezone.utc)
    carousel_id: uuid.UUID = uuid.uuid4()
    carousel: Carousel = Carousel(
        id=carousel_id,
        skeleton_id=DEFAULT_ALBUM_SKELETON_ID,
        name="Two documents",
        slug="two-documents",
        inspiration="",
        rules="",
        generation_number=1,
        editor_step=0,
        created_at=now,
        updated_at=now,
    )
    later: CarouselInstruction = CarouselInstruction(
        id=uuid.uuid4(),
        carousel_id=carousel_id,
        position=1,
        body=SECOND_BODY,
    )
    earlier: CarouselInstruction = CarouselInstruction(
        id=uuid.uuid4(),
        carousel_id=carousel_id,
        position=0,
        body=FIRST_BODY,
    )
    carousel.slides = []
    carousel.research_links = []
    carousel.instructions = [later, earlier]

    return carousel


class CarouselInstructionReadTests(unittest.TestCase):
    """Detail includes the copied document. The list shape stays the same."""

    def test_a_copied_carousel_reloads_its_one_document_in_order(self) -> None:
        """GET returns the copied body at position 0. The columns stay."""

        carousel: Carousel
        document_id: uuid.UUID
        carousel, document_id = _copied_carousel()
        skeleton: Skeleton = _paper_skeleton()
        fake_session: _InstructionReadSession = _InstructionReadSession(
            _reader(),
            [carousel],
            skeleton,
        )

        loaded: CarouselReadResponse = get_carousel(carousel.id, fake_session)  # type: ignore[arg-type]

        self.assertEqual(len(loaded.instructions), 1)
        self.assertEqual(loaded.instructions[0].id, document_id)
        self.assertEqual(loaded.instructions[0].position, 0)
        self.assertEqual(
            loaded.instructions[0].body,
            _copied_instruction_body(COPIED_INSPIRATION, COPIED_RULES),
        )
        self.assertEqual(loaded.inspiration, COPIED_INSPIRATION)
        self.assertEqual(loaded.rules, COPIED_RULES)
        self.assertEqual(loaded.steps.instructions, CarouselStepState.LOCKED)

    def test_documents_reload_in_position_order(self) -> None:
        """A later row stored first still reloads as position 0 then 1."""

        carousel: Carousel = _ordered_carousel()
        skeleton: Skeleton = _paper_skeleton()
        session_get = _session_get(carousel, skeleton)

        loaded: CarouselReadResponse = get_carousel(carousel.id, _GetSession(session_get))

        self.assertEqual(
            [(item.position, item.body) for item in loaded.instructions],
            [(0, FIRST_BODY), (1, SECOND_BODY)],
        )
        self.assertEqual(loaded.steps.instructions, CarouselStepState.LOCKED)

    def test_default_reloads_an_empty_instruction_list(self) -> None:
        """Default has no copied document. Inspiration and rules stay blank."""

        carousel: Carousel = _default_source_from_catalog()
        skeleton: Skeleton = _paper_skeleton()
        loaded: CarouselReadResponse = get_carousel(
            carousel.id,
            _GetSession(_session_get(carousel, skeleton)),
        )

        self.assertEqual(carousel.slug, DEFAULT_ALBUM_SLUG)
        self.assertEqual(loaded.instructions, [])
        self.assertEqual(loaded.inspiration, "")
        self.assertEqual(loaded.rules, "")
        self.assertEqual(loaded.steps.instructions, CarouselStepState.LOCKED)


class _GetSession:
    """``session.get`` adapter for one carousel and its skeleton."""

    def __init__(
        self,
        get_row: object,
    ) -> None:
        self._get_row = get_row

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        """Delegate to the stand-in from the carousel read tests."""

        found: object | None = self._get_row(model, row_id)  # type: ignore[operator]

        return found


class ReaderInstructionDetailTests(unittest.TestCase):
    """A reader can GET the detail. The list route does not grow a field."""

    def setUp(self) -> None:
        """Sign in a reader against the copied carousel and Default."""

        self.previous_secret: str | None = os.environ.get("SESSION_SECRET")
        self.previous_secure: str | None = os.environ.get("SESSION_COOKIE_SECURE")
        os.environ["SESSION_SECRET"] = "test-session-secret-not-for-production"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        clear_settings_cache()
        copied: Carousel
        self.document_id: uuid.UUID
        copied, self.document_id = _copied_carousel()
        self.copied: Carousel = copied
        self.default_carousel: Carousel = _default_source_from_catalog()
        self.skeleton: Skeleton = _paper_skeleton()
        self.session: _InstructionReadSession = _InstructionReadSession(
            _reader(),
            [self.default_carousel, self.copied],
            self.skeleton,
        )
        self.test_client: TestClient = _build_client(self.session)
        login_response = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": READER_USERNAME, "password": READER_PASSWORD},
        )

        self.assertEqual(login_response.status_code, 200)

    def tearDown(self) -> None:
        """Close the client and restore the session env."""

        self.test_client.close()

        if self.previous_secret is None:
            os.environ.pop("SESSION_SECRET", None)
        else:
            os.environ["SESSION_SECRET"] = self.previous_secret

        if self.previous_secure is None:
            os.environ.pop("SESSION_COOKIE_SECURE", None)
        else:
            os.environ["SESSION_COOKIE_SECURE"] = self.previous_secure

        clear_settings_cache()

    def test_a_reader_can_get_the_detail_and_the_list_shape_stays(self) -> None:
        """The detail has the document. Each list item has the old keys."""

        detail_response = self.test_client.get(f"/api/v1/carousels/{self.copied.id}")
        default_response = self.test_client.get(
            f"/api/v1/carousels/{self.default_carousel.id}",
        )
        list_response = self.test_client.get("/api/v1/carousels")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        detail: dict[str, object] = detail_response.json()
        default_detail: dict[str, object] = default_response.json()
        instructions: list[dict[str, object]] = list(detail["instructions"])  # type: ignore[arg-type]
        default_instructions: list[object] = list(default_detail["instructions"])  # type: ignore[arg-type]
        list_items: list[dict[str, object]] = list_response.json()

        self.assertEqual(len(instructions), 1)
        self.assertEqual(instructions[0]["id"], str(self.document_id))
        self.assertEqual(instructions[0]["position"], 0)
        self.assertEqual(
            instructions[0]["body"],
            _copied_instruction_body(COPIED_INSPIRATION, COPIED_RULES),
        )
        self.assertEqual(detail["inspiration"], COPIED_INSPIRATION)
        self.assertEqual(detail["rules"], COPIED_RULES)
        self.assertEqual(detail["steps"]["instructions"], "locked")  # type: ignore[index]
        self.assertEqual(default_detail["slug"], DEFAULT_ALBUM_SLUG)
        self.assertEqual(default_instructions, [])
        self.assertEqual(default_detail["inspiration"], "")
        self.assertEqual(default_detail["rules"], "")
        self.assertGreaterEqual(len(list_items), 1)

        for list_item in list_items:
            self.assertEqual(set(list_item.keys()), set(LIST_ITEM_KEYS))
            self.assertNotIn("instructions", list_item)
            self.assertNotIn("research", list_item)
            self.assertNotIn("steps", list_item)


def _build_client(session: _InstructionReadSession) -> TestClient:
    """Mount ``/api/v1`` with the instruction read session."""

    test_application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield session  # type: ignore[misc]

    test_application.dependency_overrides[get_our_database_session] = (
        override_database_session
    )
    test_application.include_router(api_v1_router)
    test_client: TestClient = TestClient(test_application)

    return test_client


if __name__ == "__main__":
    unittest.main()
