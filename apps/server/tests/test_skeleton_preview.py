"""Stateless skeleton preview. One frame, no skeleton row, no artifact, no post job."""

import base64
import io
import os
import tempfile
import unittest

os.environ.setdefault("TWERVA_ENV", "test")
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

from app.api.v1.schemas import (
    SkeletonElementCreateRequest,
    SkeletonPreviewElementRequest,
    SkeletonPreviewRequest,
    SkeletonPreviewResponse,
)
from app.api.v1.skeleton_samples import create_skeleton_preview
from app.models import BackgroundKind
from app.models.enums import (
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
)
from app.models.skeleton import DEFAULT_BACKGROUND_COLOR
from app.skeletons.layout import SKELETON_FRAME_HEIGHT_PIXELS, SKELETON_FRAME_WIDTH_PIXELS
from app.skeletons.background import (
    GRADIENT_ANGLE_DETAIL,
    GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
    GRADIENT_OFFSET_DETAIL,
    default_skeleton_gradient,
    gradient_stop_color_detail,
)
from app.skeletons.samples import BACKGROUND_COLOR_MISSING_DETAIL


PAPER: tuple[int, int, int, int] = (0xF6, 0xF1, 0xE8, 255)


class SkeletonPreviewTests(unittest.TestCase):
    """Preview renders the payload and leaves the database alone."""

    def test_clear_preview_returns_png_without_rows(self) -> None:
        """A paper frame with one text element is a 1080×1920 PNG and stores nothing."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                background_color=DEFAULT_BACKGROUND_COLOR,
                elements=[_text_element_request(SkeletonElementBand.TOP, 64)],
            )

            response: SkeletonPreviewResponse = _preview(preview_request, storage)
            image: Image.Image = _decoded_image(response)

            self.assertFalse(response.blocked)
            self.assertIsNone(response.block_reason)
            self.assertEqual(image.size, (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
            self.assertEqual(image.getpixel((0, 0)), PAPER)
            self._assert_nothing_stored(storage)

    def test_missing_font_still_renders(self) -> None:
        """An unknown family uses the sample font fallback and is not an error."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            text_request: SkeletonElementCreateRequest = _text_element_request(
                SkeletonElementBand.MIDDLE,
                32,
            )
            text_request.font_family = "No Such Preview Face"
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                elements=[text_request],
            )

            response: SkeletonPreviewResponse = _preview(preview_request, storage)

            self.assertFalse(response.blocked)
            self.assertEqual(_decoded_image(response).size, (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(storage)

    def test_overlap_is_blocked_and_stores_nothing(self) -> None:
        """Tall top and middle text block the frame and leave no rows."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                page_margin=0,
                element_gap=0,
                element_margin=0,
                elements=[
                    _text_element_request(SkeletonElementBand.TOP, 800),
                    _text_element_request(SkeletonElementBand.MIDDLE, 800),
                ],
            )

            response: SkeletonPreviewResponse = _preview(preview_request, storage)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "overlap")
            self.assertEqual(len(response.overlaps), 1)
            self.assertEqual(response.overlaps[0].band_a, SkeletonElementBand.TOP)
            self.assertEqual(response.overlaps[0].band_b, SkeletonElementBand.MIDDLE)
            self.assertEqual(_decoded_image(response).size, (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(storage)

    def test_missing_asset_is_blocked_and_stores_nothing(self) -> None:
        """A picture background with no file blocks and writes no preview file."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref="backgrounds/missing.png",
            )

            response: SkeletonPreviewResponse = _preview(preview_request, storage)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "missing_asset")
            self.assertIn("missing", (response.detail or "").lower())
            self.assertEqual(_decoded_image(response).size, (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(storage)

    def test_blank_color_is_measure_error_and_stores_nothing(self) -> None:
        """A blank color blocks with a measure error and inserts nothing."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                background_kind=BackgroundKind.COLOR,
                background_color="",
            )

            response: SkeletonPreviewResponse = _preview(preview_request, storage)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "measure_error")
            self.assertEqual(response.detail, BACKGROUND_COLOR_MISSING_DETAIL)
            self.assertEqual(_decoded_image(response).size, (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
            self._assert_nothing_stored(storage)

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
                    preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                        background_kind=BackgroundKind.GRADIENT,
                        background_gradient=gradient_payload,
                    )

                    response: SkeletonPreviewResponse = _preview(
                        preview_request,
                        storage,
                    )

                    self.assertTrue(response.blocked)
                    self.assertEqual(response.block_reason, "measure_error")
                    self.assertEqual(response.detail, expected_detail)

    def test_default_gradient_blends_end_to_end(self) -> None:
        """The editor default is dark at the top and light at the bottom."""

        default_gradient: dict[str, object] = default_skeleton_gradient()

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                background_kind=BackgroundKind.GRADIENT,
                background_color=None,
                background_gradient=default_gradient,
            )

            response: SkeletonPreviewResponse = _preview(preview_request, storage)

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
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                elements=[
                    SkeletonElementCreateRequest(
                        name="Title",
                        band=SkeletonElementBand.TOP,
                        content_kind=SkeletonElementContentKind.TEXT,
                        text_source=SkeletonElementTextSource.TITLE,
                        font_size=32,
                        font_color="#112233",
                        alignment=SkeletonElementAlignment.LEFT,
                    ),
                ],
            )

            with self.assertRaises(HTTPException) as preview_error:
                _preview(preview_request, storage)

            self.assertEqual(preview_error.exception.status_code, 400)
            self._assert_nothing_stored(storage)

    def test_preview_text_is_drawn_without_a_source_item(self) -> None:
        """Stand-in text changes the PNG. No source item is loaded."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            empty_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                elements=[
                    _text_element_request(SkeletonElementBand.TOP, 48, preview_text=""),
                ],
            )
            filled_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                elements=[
                    _text_element_request(
                        SkeletonElementBand.TOP,
                        48,
                        preview_text="Lorem ipsum dolor sit amet",
                    ),
                ],
            )

            empty_response: SkeletonPreviewResponse = _preview(empty_request, storage)
            filled_response: SkeletonPreviewResponse = _preview(filled_request, storage)

            self.assertFalse(empty_response.blocked)
            self.assertFalse(filled_response.blocked)
            self.assertNotEqual(
                empty_response.image_png_base64,
                filled_response.image_png_base64,
            )
            self._assert_nothing_stored(storage)

    def test_create_body_rejects_preview_text(self) -> None:
        """preview_text is not a field on a stored element."""

        with self.assertRaises(ValidationError):
            SkeletonElementCreateRequest(
                name="Title",
                band=SkeletonElementBand.TOP,
                content_kind=SkeletonElementContentKind.TEXT,
                font_family="DejaVu Sans",
                font_size=32,
                font_color="#112233",
                alignment=SkeletonElementAlignment.LEFT,
                preview_text="Lorem",
            )

    def _assert_nothing_stored(self, storage: Path) -> None:
        """No preview file is written."""

        written_files: list[Path] = [
            path for path in storage.rglob("*") if path.is_file()
        ]
        self.assertEqual(written_files, [])


def _preview(
    preview_request: SkeletonPreviewRequest,
    storage: Path,
) -> SkeletonPreviewResponse:
    """POST one preview against this store. No database session."""

    settings: MagicMock = MagicMock()
    settings.artifact_storage_dir = str(storage)

    with patch("app.api.v1.skeleton_samples.get_settings", return_value=settings):
        response: SkeletonPreviewResponse = create_skeleton_preview(preview_request)

    return response


def _decoded_image(response: SkeletonPreviewResponse) -> Image.Image:
    """Decode the inline PNG."""

    png_bytes: bytes = base64.b64decode(response.image_png_base64)
    image: Image.Image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    return image


def _text_element_request(
    band: SkeletonElementBand,
    font_size: int,
    preview_text: str | None = None,
) -> SkeletonPreviewElementRequest:
    """One valid text element. Family may be missing on this machine."""

    text_request: SkeletonPreviewElementRequest = SkeletonPreviewElementRequest(
        name="Title",
        band=band,
        content_kind=SkeletonElementContentKind.TEXT,
        text_source=SkeletonElementTextSource.TITLE,
        font_family="DejaVu Sans",
        font_size=font_size,
        font_color="#112233",
        alignment=SkeletonElementAlignment.LEFT,
        preview_text=preview_text,
    )

    return text_request


if __name__ == "__main__":
    unittest.main()
