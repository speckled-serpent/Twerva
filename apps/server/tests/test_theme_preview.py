"""Stateless theme preview. One frame, no theme row, no artifact, no post job."""

import base64
import io
import os
import tempfile
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from PIL import Image

from app.api.v1.schemas import ThemeElementCreateRequest, ThemePreviewRequest, ThemePreviewResponse
from app.api.v1.theme_samples import create_theme_preview
from app.models import (
    Artifact,
    BackgroundKind,
    PostJob,
    SourceItem,
    SourceType,
    Theme,
    ThemeElement,
)
from app.models.enums import (
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
)
from app.models.theme import DEFAULT_BACKGROUND_COLOR
from app.themes.layout import THEME_FRAME_HEIGHT_PIXELS, THEME_FRAME_WIDTH_PIXELS
from app.themes.background import (
    GRADIENT_ANGLE_DETAIL,
    GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
    GRADIENT_OFFSET_DETAIL,
    default_theme_gradient,
    gradient_stop_color_detail,
)
from app.themes.samples import BACKGROUND_COLOR_MISSING_DETAIL


PAPER: tuple[int, int, int, int] = (0xF6, 0xF1, 0xE8, 255)


class ThemePreviewTests(unittest.TestCase):
    """Preview renders the payload and leaves the database alone."""

    def test_clear_preview_returns_png_without_rows(self) -> None:
        """A paper frame with one text element is a 1080×1920 PNG and stores nothing."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_color=DEFAULT_BACKGROUND_COLOR,
                elements=[_text_element_request(ThemeElementBand.TOP, 64)],
            )

            response: ThemePreviewResponse = _preview(preview_request, session, storage)
            image: Image.Image = _decoded_image(response)

            self.assertFalse(response.blocked)
            self.assertIsNone(response.block_reason)
            self.assertEqual(image.size, (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS))
            self.assertEqual(image.getpixel((0, 0)), PAPER)
            self._assert_nothing_stored(session, storage)

    def test_missing_font_still_renders(self) -> None:
        """An unknown family uses the sample font fallback and is not an error."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            text_request: ThemeElementCreateRequest = _text_element_request(
                ThemeElementBand.MIDDLE,
                32,
            )
            text_request.font_family = "No Such Preview Face"
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                elements=[text_request],
            )

            response: ThemePreviewResponse = _preview(preview_request, session, storage)

            self.assertFalse(response.blocked)
            self.assertEqual(_decoded_image(response).size, (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(session, storage)

    def test_overlap_is_blocked_and_stores_nothing(self) -> None:
        """Tall top and middle text block the frame and leave no rows."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                page_margin=0,
                element_gap=0,
                element_margin=0,
                elements=[
                    _text_element_request(ThemeElementBand.TOP, 800),
                    _text_element_request(ThemeElementBand.MIDDLE, 800),
                ],
            )

            response: ThemePreviewResponse = _preview(preview_request, session, storage)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "overlap")
            self.assertEqual(len(response.overlaps), 1)
            self.assertEqual(response.overlaps[0].band_a, ThemeElementBand.TOP)
            self.assertEqual(response.overlaps[0].band_b, ThemeElementBand.MIDDLE)
            self.assertEqual(_decoded_image(response).size, (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(session, storage)

    def test_missing_asset_is_blocked_and_stores_nothing(self) -> None:
        """A picture background with no file blocks and writes no preview file."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref="backgrounds/missing.png",
            )

            response: ThemePreviewResponse = _preview(preview_request, session, storage)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "missing_asset")
            self.assertIn("missing", (response.detail or "").lower())
            self.assertEqual(_decoded_image(response).size, (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(session, storage)

    def test_blank_color_is_measure_error_and_stores_nothing(self) -> None:
        """A blank color blocks with a measure error and inserts nothing."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.COLOR,
                background_color="",
            )

            response: ThemePreviewResponse = _preview(preview_request, session, storage)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "measure_error")
            self.assertEqual(response.detail, BACKGROUND_COLOR_MISSING_DETAIL)
            self.assertEqual(_decoded_image(response).size, (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(session, storage)

    def test_gradient_preview_names_the_problem(self) -> None:
        """A bad gradient blocks with the same sentence the form shows."""

        cases: list[tuple[dict[str, object], str]] = [
            (
                {
                    "angle_deg": 180,
                    "stops": [{"offset": 0, "color": "#112233"}],
                },
                GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
            ),
            (
                {
                    "angle_deg": 400,
                    "stops": [
                        {"offset": 0, "color": "#112233"},
                        {"offset": 1, "color": "#AABBCC"},
                    ],
                },
                GRADIENT_ANGLE_DETAIL,
            ),
            (
                {
                    "angle_deg": 180,
                    "stops": [
                        {"offset": 0, "color": "#112233"},
                        {"offset": 1.5, "color": "#AABBCC"},
                    ],
                },
                GRADIENT_OFFSET_DETAIL,
            ),
            (
                {
                    "angle_deg": 180,
                    "stops": [
                        {"offset": 0, "color": "#112233"},
                        {"offset": 1, "color": "zzzz"},
                    ],
                },
                gradient_stop_color_detail(2),
            ),
        ]

        for gradient_payload, expected_detail in cases:
            with self.subTest(expected_detail=expected_detail):
                with tempfile.TemporaryDirectory() as storage_directory:
                    storage: Path = Path(storage_directory)
                    source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
                    session: _PreviewMemorySession = _PreviewMemorySession(source_item)
                    preview_request: ThemePreviewRequest = ThemePreviewRequest(
                        source_item_id=source_item.id,
                        background_kind=BackgroundKind.GRADIENT,
                        background_gradient=gradient_payload,
                    )

                    response: ThemePreviewResponse = _preview(
                        preview_request,
                        session,
                        storage,
                    )

                    self.assertTrue(response.blocked)
                    self.assertEqual(response.block_reason, "measure_error")
                    self.assertEqual(response.detail, expected_detail)

    def test_default_gradient_blends_end_to_end(self) -> None:
        """The editor default is dark at the top and light at the bottom."""

        default_gradient: dict[str, object] = default_theme_gradient()

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.GRADIENT,
                background_color=None,
                background_gradient=default_gradient,
            )

            response: ThemePreviewResponse = _preview(preview_request, session, storage)

            self.assertFalse(response.blocked)
            image: Image.Image = _decoded_image(response)
            top_pixel: tuple[int, ...] = image.getpixel((540, 80))
            bottom_pixel: tuple[int, ...] = image.getpixel((540, 1840))

            self.assertLess(abs(top_pixel[0] - 0x4A), 8)
            self.assertGreater(bottom_pixel[0], top_pixel[0] + 40)

    def test_invalid_element_stores_nothing(self) -> None:
        """A text element without a family is 400 and does not render."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                elements=[
                    ThemeElementCreateRequest(
                        band=ThemeElementBand.TOP,
                        content_kind=ThemeElementContentKind.TEXT,
                        text_source=ThemeElementTextSource.TITLE,
                        font_size=32,
                        font_color="#112233",
                        alignment=ThemeElementAlignment.LEFT,
                    ),
                ],
            )

            with self.assertRaises(HTTPException) as preview_error:
                _preview(preview_request, session, storage)

            self.assertEqual(preview_error.exception.status_code, 400)
            self._assert_nothing_stored(session, storage)

    def test_non_spotmu_source_stores_nothing(self) -> None:
        """A brand product source is 400 and does not render."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item: SourceItem = _source_item(SourceType.BRAND_PRODUCT)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
            )

            with self.assertRaises(HTTPException) as preview_error:
                _preview(preview_request, session, storage)

            self.assertEqual(preview_error.exception.status_code, 400)
            self.assertIn("Spotmu", preview_error.exception.detail)
            self._assert_nothing_stored(session, storage)

    def _assert_nothing_stored(
        self,
        session: "_PreviewMemorySession",
        storage: Path,
    ) -> None:
        """No theme, artifact, post job, commit, or preview file."""

        for added_row in session.added:
            self.assertNotIsInstance(added_row, (Theme, ThemeElement, Artifact, PostJob))

        self.assertEqual(session.added, [])
        self.assertEqual(session.commit_count, 0)
        written_files: list[Path] = [
            path for path in storage.rglob("*") if path.is_file()
        ]
        self.assertEqual(written_files, [])


class _PreviewMemorySession:
    """Source lookup that records inserts. Not a database."""

    def __init__(self, source_item: SourceItem) -> None:

        self.source_item: SourceItem = source_item
        self.added: list[object] = []
        self.commit_count: int = 0

    def get(self, model: type[object], key: uuid.UUID) -> SourceItem | None:
        """Return the source item when the id matches."""

        if model is SourceItem and key == self.source_item.id:

            return self.source_item

        return None

    def add(self, row: object) -> None:
        """Record an insert the preview handler must not make."""

        self.added.append(row)

    def commit(self) -> None:
        """Record a commit the preview handler must not make."""

        self.commit_count += 1


def _preview(
    preview_request: ThemePreviewRequest,
    session: _PreviewMemorySession,
    storage: Path,
) -> ThemePreviewResponse:
    """POST one preview against the in-memory session and this store."""

    settings: MagicMock = MagicMock()
    settings.artifact_storage_dir = str(storage)

    with patch("app.api.v1.theme_samples.get_settings", return_value=settings):
        response: ThemePreviewResponse = create_theme_preview(preview_request, session)

    return response


def _decoded_image(response: ThemePreviewResponse) -> Image.Image:
    """Decode the inline PNG."""

    png_bytes: bytes = base64.b64decode(response.image_png_base64)
    image: Image.Image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    return image


def _source_item(source_type: SourceType) -> SourceItem:
    """Build an in-memory source item. Nothing is written."""

    source_item: SourceItem = SourceItem(
        id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
        source_type=source_type,
        external_key="example",
        title="Harbor light",
        interest_heading="Evening",
        overview_bullets=["One"],
        canonical_url="https://example.test/harbor",
    )

    return source_item


def _text_element_request(
    band: ThemeElementBand,
    font_size: int,
) -> ThemeElementCreateRequest:
    """One valid text element. Family may be missing on this machine."""

    text_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
        band=band,
        content_kind=ThemeElementContentKind.TEXT,
        text_source=ThemeElementTextSource.TITLE,
        font_family="DejaVu Sans",
        font_size=font_size,
        font_color="#112233",
        alignment=ThemeElementAlignment.LEFT,
    )

    return text_request


if __name__ == "__main__":
    unittest.main()
