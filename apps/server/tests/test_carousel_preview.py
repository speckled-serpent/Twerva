"""Auth-gated slide images, template registry, and generate template_id."""

from __future__ import annotations

import os
import unittest
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.api.v1.router import api_v1_router
from app.api.v1.schemas import CarouselGenerateRequest
from app.auth.passwords import hash_plain_password
from app.db import get_our_database_session
from app.generate.carousel import (
    CANVAS_HEIGHT_PIXELS,
    CANVAS_WIDTH_PIXELS,
    CarouselSourceFields,
    render_carousel_from_source_fields,
)
from app.generate.errors import CarouselUnknownTemplateError
from app.generate.templates import (
    DEFAULT_CAROUSEL_TEMPLATE_ID,
    TEMPLATE_ID_SPOTMU_BOLD_V1,
    TEMPLATE_ID_SPOTMU_PAPER_V1,
    list_carousel_templates,
    resolve_carousel_template,
)
from app.models import Artifact, OpsUser
from app.models.enums import ArtifactStatus, OpsUserRole
from app.settings import clear_settings_cache
from app.storage.artifacts import write_artifact_slide_png_bytes


ADMIN_USERNAME: str = "admin"
READER_USERNAME: str = "reader-agent"
CORRECT_PASSWORD: str = "correct-horse-battery"
PNG_MAGIC: bytes = b"\x89PNG"
PNG_MEDIA_TYPE_PREFIX: str = "image/png"


class _FakeScalarResult:
    """Stand-in for `session.scalars(...).first()`."""

    def __init__(self, ops_user: OpsUser | None) -> None:

        self.ops_user: OpsUser | None = ops_user

    def first(self) -> OpsUser | None:

        return self.ops_user


class _FakePreviewDatabaseSession:
    """In-memory session for ops auth plus one Artifact row."""

    def __init__(self, ops_users: list[OpsUser], artifact: Artifact | None = None) -> None:

        self.ops_users_by_id: dict[uuid.UUID, OpsUser] = {
            ops_user.id: ops_user for ops_user in ops_users
        }
        self.ops_users_by_username: dict[str, OpsUser] = {
            ops_user.username: ops_user for ops_user in ops_users
        }
        self.artifact: Artifact | None = artifact
        self.commit_count: int = 0

    def scalars(self, statement: object) -> _FakeScalarResult:
        """Return the ops user whose username appears in the compiled SQL."""

        compiled_parameters: dict[str, object] = {}

        if hasattr(statement, "compile"):
            compiled_statement = statement.compile()
            compiled_parameters = dict(getattr(compiled_statement, "params", {}) or {})

        parameter_values: list[object] = list(compiled_parameters.values())

        for ops_user in self.ops_users_by_username.values():

            if ops_user.username in parameter_values:
                matching_result: _FakeScalarResult = _FakeScalarResult(ops_user)

                return matching_result

        empty_result: _FakeScalarResult = _FakeScalarResult(None)

        return empty_result

    def get(self, model: object, row_id: uuid.UUID) -> OpsUser | Artifact | None:

        if model is OpsUser:

            return self.ops_users_by_id.get(row_id)

        if model is Artifact:

            if self.artifact is None:

                return None

            if self.artifact.id != row_id:

                return None

            return self.artifact

        return None

    def add(self, row: object) -> None:

        del row

    def commit(self) -> None:

        self.commit_count += 1

    def refresh(self, row: object) -> None:

        del row

    def rollback(self) -> None:

        return


def _build_ops_user(
    username: str,
    role: OpsUserRole,
) -> OpsUser:
    """Return an in-memory ops user."""

    now: datetime = datetime.now(timezone.utc)
    ops_user: OpsUser = OpsUser(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_plain_password(CORRECT_PASSWORD),
        role=role,
        created_at=now,
        updated_at=now,
    )

    return ops_user


def _build_preview_test_client(fake_session: _FakePreviewDatabaseSession) -> TestClient:
    """Mount `/api/v1` with the fake session dependency."""

    test_application: FastAPI = FastAPI()

    def override_database_session() -> Generator[Session, None, None]:

        yield fake_session  # type: ignore[misc]

    test_application.dependency_overrides[get_our_database_session] = (
        override_database_session
    )
    test_application.include_router(api_v1_router)
    test_client: TestClient = TestClient(test_application)

    return test_client


class CarouselTemplateRegistryTests(unittest.TestCase):
    """Restricted Spotmu templates: at least two named variants."""

    def test_registry_lists_paper_and_bold(self) -> None:
        """GET-shaped registry includes both locked template ids."""

        carousel_templates = list_carousel_templates()
        template_ids: list[str] = [
            carousel_template.template_id for carousel_template in carousel_templates
        ]

        self.assertGreaterEqual(len(carousel_templates), 2)
        self.assertIn(TEMPLATE_ID_SPOTMU_PAPER_V1, template_ids)
        self.assertIn(TEMPLATE_ID_SPOTMU_BOLD_V1, template_ids)
        self.assertEqual(DEFAULT_CAROUSEL_TEMPLATE_ID, TEMPLATE_ID_SPOTMU_PAPER_V1)

    def test_blank_template_id_resolves_to_paper(self) -> None:
        """None or blank uses the current paper look."""

        default_template = resolve_carousel_template(None)
        blank_template = resolve_carousel_template("   ")

        self.assertEqual(default_template.template_id, TEMPLATE_ID_SPOTMU_PAPER_V1)
        self.assertEqual(blank_template.template_id, TEMPLATE_ID_SPOTMU_PAPER_V1)

    def test_unknown_template_id_raises(self) -> None:
        """Freeform / unknown ids are rejected."""

        with self.assertRaises(CarouselUnknownTemplateError):
            resolve_carousel_template("custom_brand_designer")


class CarouselTemplateRenderTests(unittest.TestCase):
    """Paper and bold share canvas rules but differ visually."""

    def test_paper_and_bold_are_visually_distinct(self) -> None:
        """Same copy, different background pixel at the corner."""

        source_fields: CarouselSourceFields = CarouselSourceFields(
            title="Template contrast",
            interest_heading="Two Spotmu looks",
            overview_bullets=["one claim"],
            canonical_url="https://spotmu.com/interest/template-contrast",
            external_key="template-contrast",
        )

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            paper_result = render_carousel_from_source_fields(
                source_fields,
                uuid.uuid4(),
                storage_directory,
                template_id=TEMPLATE_ID_SPOTMU_PAPER_V1,
            )
            bold_result = render_carousel_from_source_fields(
                source_fields,
                uuid.uuid4(),
                storage_directory,
                template_id=TEMPLATE_ID_SPOTMU_BOLD_V1,
            )
            paper_path: Path = storage_directory / paper_result.slides[0].asset_ref
            bold_path: Path = storage_directory / bold_result.slides[0].asset_ref
            paper_image: Image.Image = Image.open(paper_path)
            bold_image: Image.Image = Image.open(bold_path)
            paper_corner: tuple[int, ...] = tuple(paper_image.getpixel((8, 8)))
            bold_corner: tuple[int, ...] = tuple(bold_image.getpixel((8, 8)))

            self.assertEqual(paper_image.size, (CANVAS_WIDTH_PIXELS, CANVAS_HEIGHT_PIXELS))
            self.assertEqual(bold_image.size, (CANVAS_WIDTH_PIXELS, CANVAS_HEIGHT_PIXELS))
            self.assertNotEqual(paper_corner, bold_corner)
            paper_image.close()
            bold_image.close()


class CarouselPreviewHttpTests(unittest.TestCase):
    """Image GET 401/200, template list, generate with template_id."""

    def setUp(self) -> None:
        """Build admin + reader, a draft artifact, and a tmp store."""

        clear_settings_cache()
        self.temporary_directory: TemporaryDirectory[str] = TemporaryDirectory()
        self.storage_directory: Path = Path(self.temporary_directory.name)
        os.environ["ARTIFACT_STORAGE_DIR"] = str(self.storage_directory)
        clear_settings_cache()
        self.admin_user: OpsUser = _build_ops_user(ADMIN_USERNAME, OpsUserRole.ADMIN)
        self.reader_user: OpsUser = _build_ops_user(READER_USERNAME, OpsUserRole.READER)
        now: datetime = datetime.now(timezone.utc)
        self.artifact_id: uuid.UUID = uuid.uuid4()
        self.brand_id: uuid.UUID = uuid.uuid4()
        self.source_item_id: uuid.UUID = uuid.uuid4()
        relative_asset_reference: str = write_artifact_slide_png_bytes(
            self.artifact_id,
            0,
            "cover",
            _minimal_png_bytes(),
            self.storage_directory,
        )
        self.artifact: Artifact = Artifact(
            id=self.artifact_id,
            brand_id=self.brand_id,
            source_item_id=self.source_item_id,
            cluster_id=None,
            status=ArtifactStatus.DRAFT,
            format="carousel",
            caption="Preview caption",
            cta_url="https://spotmu.com/interest/preview",
            slides=[
                {
                    "role": "cover",
                    "text": "Preview",
                    "asset_ref": relative_asset_reference,
                },
            ],
            template_id=TEMPLATE_ID_SPOTMU_PAPER_V1,
            created_at=now,
            updated_at=now,
        )
        self.fake_session: _FakePreviewDatabaseSession = _FakePreviewDatabaseSession(
            [self.admin_user, self.reader_user],
            self.artifact,
        )
        self.test_client: TestClient = _build_preview_test_client(self.fake_session)

    def tearDown(self) -> None:
        """Close the client and drop the tmp store."""

        self.test_client.close()
        self.temporary_directory.cleanup()
        os.environ.pop("ARTIFACT_STORAGE_DIR", None)
        clear_settings_cache()

    def test_slide_image_without_cookie_returns_401(self) -> None:
        """Unauthenticated GET of a slide PNG is 401."""

        image_response = self.test_client.get(
            f"/api/v1/artifacts/{self.artifact_id}/slides/0/image",
        )

        self.assertEqual(image_response.status_code, 401)

    def test_slide_image_with_session_returns_200_png(self) -> None:
        """Authenticated GET streams the PNG bytes from local storage."""

        self._login(ADMIN_USERNAME)
        image_response = self.test_client.get(
            f"/api/v1/artifacts/{self.artifact_id}/slides/0/image",
        )

        self.assertEqual(image_response.status_code, 200)
        self.assertIn(PNG_MEDIA_TYPE_PREFIX, image_response.headers.get("content-type", ""))
        self.assertTrue(image_response.content.startswith(PNG_MAGIC))

    def test_reader_can_get_slide_image(self) -> None:
        """Readers may GET previews; write is not required."""

        self._login(READER_USERNAME)
        image_response = self.test_client.get(
            f"/api/v1/artifacts/{self.artifact_id}/slides/0/image",
        )

        self.assertEqual(image_response.status_code, 200)
        self.assertTrue(image_response.content.startswith(PNG_MAGIC))

    def test_missing_slide_index_returns_404(self) -> None:
        """Out-of-range index is 404, not an empty 200."""

        self._login(ADMIN_USERNAME)
        image_response = self.test_client.get(
            f"/api/v1/artifacts/{self.artifact_id}/slides/9/image",
        )

        self.assertEqual(image_response.status_code, 404)

    def test_template_list_returns_spotmu_variants(self) -> None:
        """GET /generate/templates lists the restricted registry."""

        self._login(READER_USERNAME)
        templates_response = self.test_client.get("/api/v1/generate/templates")

        self.assertEqual(templates_response.status_code, 200)
        template_payloads: list[object] = templates_response.json()
        self.assertIsInstance(template_payloads, list)
        self.assertGreaterEqual(len(template_payloads), 2)
        template_ids: list[str] = [
            str(template_payload["template_id"])
            for template_payload in template_payloads
            if isinstance(template_payload, dict)
        ]

        self.assertIn(TEMPLATE_ID_SPOTMU_PAPER_V1, template_ids)
        self.assertIn(TEMPLATE_ID_SPOTMU_BOLD_V1, template_ids)

    def test_generate_carousel_accepts_template_id(self) -> None:
        """POST /generate/carousel forwards optional template_id."""

        now: datetime = datetime.now(timezone.utc)
        created_artifact: Artifact = Artifact(
            id=uuid.uuid4(),
            brand_id=self.brand_id,
            source_item_id=self.source_item_id,
            cluster_id=None,
            status=ArtifactStatus.DRAFT,
            format="carousel",
            caption="Bold caption",
            cta_url="https://spotmu.com/interest/preview",
            slides=[{"role": "cover", "text": "Bold", "asset_ref": "x/0_cover.png"}],
            template_id=TEMPLATE_ID_SPOTMU_BOLD_V1,
            created_at=now,
            updated_at=now,
        )
        generate_request: CarouselGenerateRequest = CarouselGenerateRequest(
            source_item_id=self.source_item_id,
            template_id=TEMPLATE_ID_SPOTMU_BOLD_V1,
        )

        self.assertEqual(generate_request.template_id, TEMPLATE_ID_SPOTMU_BOLD_V1)
        self._login(ADMIN_USERNAME)

        with patch(
            "app.api.v1.generate.generate_carousel_artifact_draft",
            return_value=created_artifact,
        ) as mocked_generate:
            generate_response = self.test_client.post(
                "/api/v1/generate/carousel",
                json={
                    "source_item_id": str(self.source_item_id),
                    "template_id": TEMPLATE_ID_SPOTMU_BOLD_V1,
                },
            )

        self.assertEqual(generate_response.status_code, 201)
        self.assertEqual(
            generate_response.json()["template_id"],
            TEMPLATE_ID_SPOTMU_BOLD_V1,
        )
        mocked_generate.assert_called_once()
        call_keyword_arguments: dict[str, object] = mocked_generate.call_args.kwargs

        self.assertEqual(
            call_keyword_arguments.get("template_id"),
            TEMPLATE_ID_SPOTMU_BOLD_V1,
        )

    def test_reader_cannot_generate_carousel(self) -> None:
        """Readers stay write-blocked on generate (existing RBAC)."""

        self._login(READER_USERNAME)
        generate_response = self.test_client.post(
            "/api/v1/generate/carousel",
            json={
                "source_item_id": str(self.source_item_id),
                "template_id": TEMPLATE_ID_SPOTMU_PAPER_V1,
            },
        )

        self.assertEqual(generate_response.status_code, 403)

    def _login(self, username: str) -> None:
        """Establish a session cookie for `username`."""

        login_response = self.test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": CORRECT_PASSWORD},
        )

        self.assertEqual(login_response.status_code, 200)


def _minimal_png_bytes() -> bytes:
    """Return a tiny valid PNG for FileResponse tests."""

    canvas_image: Image.Image = Image.new("RGB", (8, 8), "#F6F1E8")
    png_buffer: BytesIO = BytesIO()
    canvas_image.save(png_buffer, format="PNG")
    png_bytes: bytes = png_buffer.getvalue()
    canvas_image.close()

    return png_bytes


if __name__ == "__main__":
    unittest.main()
