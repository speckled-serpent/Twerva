"""Skeleton sample previews (1.10g-i). One frame, no artifact, no post job."""

import os
import tempfile
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.responses import FileResponse
from PIL import Image

from app.api.v1.schemas import SkeletonSampleRequest, SkeletonSampleResponse
from app.api.v1.skeleton_samples import create_skeleton_sample, get_skeleton_sample_image
from app.models import (
    AdvertisementType,
    Artifact,
    BackgroundKind,
    PostJob,
    SourceItem,
    SourceType,
    Skeleton,
    SkeletonElement,
    SkeletonStatus,
)
from app.models.enums import (
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
)
from app.models.skeleton import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
)
from app.skeletons.layout import SKELETON_FRAME_HEIGHT_PIXELS, SKELETON_FRAME_WIDTH_PIXELS


PAPER: tuple[int, int, int, int] = (0xF6, 0xF1, 0xE8, 255)
CREATED_AT: datetime = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


class SkeletonSampleTests(unittest.TestCase):
    """Samples write a preview PNG and leave artifacts, post jobs, and status alone."""

    def test_draft_color_preview_writes_png_without_artifact_or_post_job(self) -> None:
        """A Spotmu draft writes one 1080×1920 preview and no artifact or post job."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item(
                "Harbor light",
                SourceType.SPOTMU_INTEREST,
            )
            text_element: SkeletonElement = _text_element(
                skeleton,
                SkeletonElementBand.TOP,
                SkeletonElementTextSource.TITLE,
                rectangle_color=None,
            )
            skeleton.elements.append(text_element)
            session: _SampleMemorySession
            response: SkeletonSampleResponse
            session, response = _create_sample(skeleton, source_item, storage)

            self.assertFalse(response.blocked)
            self.assertIsNone(response.block_reason)
            self.assertIsNone(response.detail)
            self.assertEqual(response.overlaps, [])
            self.assertEqual(skeleton.status, SkeletonStatus.DRAFT)
            self.assertEqual(skeleton.updated_at, CREATED_AT)
            self._assert_no_artifact_or_post_job(session)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)
            self.assertTrue(preview_path.is_file())
            self.assertEqual(_image_size(preview_path), (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
            self.assertEqual(_pixel(preview_path, 0, 0), PAPER)
            self.assertTrue(_has_different_pixel(preview_path, PAPER, 96, 96, 500, 220))
            image_response: FileResponse = _get_image(
                skeleton,
                response.preview_id,
                storage,
            )

            self.assertEqual(image_response.media_type, "image/png")
            self.assertEqual(Path(str(image_response.path)), preview_path.resolve())

    def test_live_colliding_layout_is_blocked_overlap_and_still_renders(self) -> None:
        """A tall top through middle blocks, keeps Live, and still writes the PNG."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.LIVE)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            _solid_png(storage / "images" / "top.png", 10, 10, (255, 0, 0))
            _solid_png(storage / "images" / "middle.png", 10, 10, (0, 0, 255))
            top_element: SkeletonElement = _image_element(
                skeleton,
                SkeletonElementBand.TOP,
                "images/top.png",
                rectangle_color=None,
            )
            middle_element: SkeletonElement = _image_element(
                skeleton,
                SkeletonElementBand.MIDDLE,
                "images/middle.png",
                rectangle_color=None,
            )
            skeleton.elements.append(top_element)
            skeleton.elements.append(middle_element)
            session: _SampleMemorySession
            response: SkeletonSampleResponse
            session, response = _create_sample(skeleton, source_item, storage)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "overlap")
            self.assertEqual(response.detail, "top overlaps middle.")
            self.assertEqual(len(response.overlaps), 1)
            self.assertEqual(response.overlaps[0].band_a, SkeletonElementBand.TOP)
            self.assertEqual(response.overlaps[0].band_b, SkeletonElementBand.MIDDLE)
            self.assertEqual(
                response.overlaps[0].element_ids,
                [top_element.id, middle_element.id],
            )
            self.assertEqual(skeleton.status, SkeletonStatus.LIVE)
            self.assertEqual(skeleton.updated_at, CREATED_AT)
            self._assert_no_artifact_or_post_job(session)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertTrue(preview_path.is_file())
            self.assertEqual(_image_size(preview_path), (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
            self.assertEqual(_pixel(preview_path, 0, 0), PAPER)

    def test_non_spotmu_source_is_400_and_writes_no_file(self) -> None:
        """A brand product is rejected before a preview file is written."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Lamp", SourceType.BRAND_PRODUCT)
            skeleton.elements.append(
                _text_element(
                    skeleton,
                    SkeletonElementBand.TOP,
                    SkeletonElementTextSource.TITLE,
                    rectangle_color=None,
                ),
            )

            with self.assertRaises(HTTPException) as caught:
                _create_sample(skeleton, source_item, storage)

            self.assertEqual(caught.exception.status_code, 400)
            self.assertEqual(
                caught.exception.detail,
                "Source item must be a Spotmu interest.",
            )
            self.assertFalse((storage / "skeleton-previews").exists())
            self.assertEqual(skeleton.status, SkeletonStatus.DRAFT)

    def test_missing_picture_does_not_invent_a_fill(self) -> None:
        """A missing background file blocks and leaves the frame transparent."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            skeleton.background_kind = BackgroundKind.PICTURE
            skeleton.background_color = None
            skeleton.background_asset_ref = "backgrounds/missing.png"
            source_item: SourceItem = _source_item(
                "Harbor light",
                SourceType.SPOTMU_INTEREST,
            )
            session: _SampleMemorySession
            response: SkeletonSampleResponse
            session, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(
                storage,
                skeleton.id,
                response.preview_id,
            )

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "missing_asset")
            self.assertEqual(response.detail, "Background image file is missing.")
            self.assertEqual(response.overlaps, [])
            self.assertTrue(preview_path.is_file())
            self.assertEqual(_pixel(preview_path, 0, 0), (0, 0, 0, 0))
            self.assertEqual(skeleton.status, SkeletonStatus.DRAFT)
            self._assert_no_artifact_or_post_job(session)

    def test_gradient_runs_from_the_first_stop(self) -> None:
        """0° puts the first stop at the bottom. 90° puts it at the left."""

        cases: tuple[
            tuple[float, tuple[int, int], tuple[int, int], tuple[int, int, int, int], tuple[int, int, int, int]],
            ...,
        ] = (
            (
                90,
                (0, SKELETON_FRAME_HEIGHT_PIXELS // 2),
                (SKELETON_FRAME_WIDTH_PIXELS - 1, SKELETON_FRAME_HEIGHT_PIXELS // 2),
                (255, 0, 0, 255),
                (0, 0, 255, 255),
            ),
            (
                0,
                (SKELETON_FRAME_WIDTH_PIXELS // 2, SKELETON_FRAME_HEIGHT_PIXELS - 1),
                (SKELETON_FRAME_WIDTH_PIXELS // 2, 0),
                (255, 0, 0, 255),
                (0, 0, 255, 255),
            ),
        )

        for angle_deg, start_pixel, end_pixel, start_color, end_color in cases:
            with self.subTest(angle_deg=angle_deg):
                with tempfile.TemporaryDirectory() as storage_directory:
                    storage: Path = Path(storage_directory)
                    skeleton: Skeleton = _skeleton_row(SkeletonStatus.LIVE)
                    skeleton.background_kind = BackgroundKind.GRADIENT
                    skeleton.background_color = None
                    skeleton.background_gradient = {
                        "angle_deg": angle_deg,
                        "stops": [
                            {"offset": 0, "color": "#FF0000"},
                            {"offset": 1, "color": "#0000FF"},
                        ],
                    }
                    source_item: SourceItem = _source_item(
                        "Harbor light",
                        SourceType.SPOTMU_INTEREST,
                    )
                    session: _SampleMemorySession
                    response: SkeletonSampleResponse
                    session, response = _create_sample(skeleton, source_item, storage)
                    preview_path: Path = _preview_path(
                        storage,
                        skeleton.id,
                        response.preview_id,
                    )

                    self.assertFalse(response.blocked)
                    self.assertIsNone(response.block_reason)
                    self.assertEqual(
                        _pixel(preview_path, start_pixel[0], start_pixel[1]),
                        start_color,
                    )
                    self.assertEqual(
                        _pixel(preview_path, end_pixel[0], end_pixel[1]),
                        end_color,
                    )
                    self.assertEqual(skeleton.status, SkeletonStatus.LIVE)
                    self._assert_no_artifact_or_post_job(session)

    def test_picture_background_scales_to_fill(self) -> None:
        """A picture covers the frame with the file. It does not tile a gap."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            _solid_png(storage / "backgrounds" / "red.png", 8, 4, (255, 0, 0))
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            skeleton.background_kind = BackgroundKind.PICTURE
            skeleton.background_color = DEFAULT_BACKGROUND_COLOR
            skeleton.background_asset_ref = "backgrounds/red.png"
            source_item: SourceItem = _source_item(
                "Harbor light",
                SourceType.SPOTMU_INTEREST,
            )
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(
                storage,
                skeleton.id,
                response.preview_id,
            )

            self.assertFalse(response.blocked)
            self.assertEqual(_pixel(preview_path, 0, 0), (255, 0, 0, 255))
            self.assertEqual(
                _pixel(
                    preview_path,
                    SKELETON_FRAME_WIDTH_PIXELS - 1,
                    SKELETON_FRAME_HEIGHT_PIXELS - 1,
                ),
                (255, 0, 0, 255),
            )

    def test_image_element_is_drawn_and_clear_rectangle_is_not_filled(self) -> None:
        """A PNG fills its content box. A null rectangle color leaves the background."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            _solid_png(storage / "images" / "red.png", 20, 10, (255, 0, 0))
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            source_item.interest_heading = None
            image_element: SkeletonElement = _image_element(
                skeleton,
                SkeletonElementBand.TOP,
                "images/red.png",
                rectangle_color=None,
            )
            clear_text: SkeletonElement = _text_element(
                skeleton,
                SkeletonElementBand.BOTTOM,
                SkeletonElementTextSource.INTEREST_HEADING,
                rectangle_color=None,
            )
            skeleton.elements.append(image_element)
            skeleton.elements.append(clear_text)
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertFalse(response.blocked)
            self.assertEqual(_pixel(preview_path, 0, 0), PAPER)
            self.assertEqual(_pixel(preview_path, 96, 96), (255, 0, 0, 255))
            self.assertEqual(_pixel(preview_path, 96, 984), PAPER)

    def test_colored_rectangle_fills_when_text_is_blank(self) -> None:
        """A hex rectangle is drawn. Blank heading text adds no glyphs."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            source_item.interest_heading = None
            text_element: SkeletonElement = _text_element(
                skeleton,
                SkeletonElementBand.TOP,
                SkeletonElementTextSource.INTEREST_HEADING,
                rectangle_color="#00FF00",
            )
            skeleton.elements.append(text_element)
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertFalse(response.blocked)
            self.assertEqual(_pixel(preview_path, 96, 96), (0, 255, 0, 255))
            self.assertEqual(_pixel(preview_path, 0, 0), PAPER)

    def test_missing_image_file_blocks_without_a_guessed_fill(self) -> None:
        """A missing element image is missing_asset and does not paint a stand-in."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            skeleton.elements.append(
                _image_element(
                    skeleton,
                    SkeletonElementBand.TOP,
                    "images/missing.png",
                    rectangle_color="#FF00FF",
                ),
            )
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "missing_asset")
            self.assertEqual(response.detail, "image file is missing")
            self.assertEqual(_pixel(preview_path, 0, 0), PAPER)
            self.assertEqual(_pixel(preview_path, 96, 96), PAPER)

    def test_unreadable_image_is_measure_error(self) -> None:
        """A file Pillow cannot read blocks as measure_error and skips the rectangle."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            bad_path: Path = storage / "images" / "bad.png"
            bad_path.parent.mkdir(parents=True, exist_ok=True)
            bad_path.write_bytes(b"not a png")
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            skeleton.elements.append(
                _image_element(
                    skeleton,
                    SkeletonElementBand.TOP,
                    "images/bad.png",
                    rectangle_color="#FF00FF",
                ),
            )
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertTrue(response.blocked)
            self.assertEqual(response.block_reason, "measure_error")
            self.assertEqual(response.detail, "image file could not be read")
            self.assertEqual(_pixel(preview_path, 96, 96), PAPER)

    def test_svg_image_draws_its_rectangle_and_does_not_block(self) -> None:
        """An SVG is measured and the rectangle is filled. Vectors are not rasterized."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            svg_path: Path = storage / "images" / "mark.svg"
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>',
                encoding="utf-8",
            )
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            skeleton.elements.append(
                _image_element(
                    skeleton,
                    SkeletonElementBand.TOP,
                    "images/mark.svg",
                    rectangle_color="#00FF00",
                ),
            )
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertFalse(response.blocked)
            self.assertIsNone(response.block_reason)
            self.assertEqual(_pixel(preview_path, 96, 96), (0, 255, 0, 255))

    def test_overview_bullets_stay_one_frame(self) -> None:
        """Three bullets are one text block and one preview file."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            source_item.overview_bullets = ["First", "Second", "Third"]
            skeleton.elements.append(
                _text_element(
                    skeleton,
                    SkeletonElementBand.MIDDLE,
                    SkeletonElementTextSource.OVERVIEW_BULLETS,
                    rectangle_color=None,
                ),
            )
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_files: list[Path] = list(storage.rglob("*.png"))

            self.assertFalse(response.blocked)
            self.assertEqual(len(preview_files), 1)
            self.assertEqual(
                preview_files[0],
                _preview_path(storage, skeleton.id, response.preview_id),
            )

    def test_missing_skeleton_or_preview_image_is_404(self) -> None:
        """GET and POST miss with 404 and do not write a file for an unknown skeleton."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            missing_skeleton_id: uuid.UUID = uuid.uuid4()
            session: _SampleMemorySession = _SampleMemorySession(skeleton, source_item)
            settings: MagicMock = _settings(storage)

            with patch("app.api.v1.skeleton_samples.get_settings", return_value=settings):
                with self.assertRaises(HTTPException) as missing_skeleton:
                    create_skeleton_sample(
                        missing_skeleton_id,
                        SkeletonSampleRequest(source_item_id=source_item.id),
                        session,
                    )

                with self.assertRaises(HTTPException) as missing_source:
                    create_skeleton_sample(
                        skeleton.id,
                        SkeletonSampleRequest(source_item_id=uuid.uuid4()),
                        session,
                    )

                with self.assertRaises(HTTPException) as missing_image:
                    get_skeleton_sample_image(
                        skeleton.id,
                        uuid.uuid4(),
                        session,
                    )

            self.assertEqual(missing_skeleton.exception.status_code, 404)
            self.assertEqual(missing_source.exception.status_code, 404)
            self.assertEqual(missing_image.exception.status_code, 404)
            self.assertFalse((storage / "skeleton-previews").exists())
            self._assert_no_artifact_or_post_job(session)

    def test_rectangle_opacity_blends_over_the_background(self) -> None:
        """A 50% green rectangle blends over red and does not stay solid."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            skeleton.background_color = "#FF0000"
            skeleton.page_margin = 0
            skeleton.element_margin = 0
            skeleton.element_gap = 0
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            text_element: SkeletonElement = _text_element(
                skeleton,
                SkeletonElementBand.TOP,
                SkeletonElementTextSource.TITLE,
                rectangle_color="#00FF00",
                rectangle_opacity=50,
                rectangle_radius=0,
            )
            skeleton.elements.append(text_element)
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)
            blended_pixel: tuple[int, int, int, int] = _pixel(preview_path, 1000, 12)

            self.assertFalse(response.blocked)
            self.assertEqual(blended_pixel, (127, 128, 0, 255))
            self.assertNotEqual(blended_pixel, (0, 255, 0, 255))

    def test_blank_rectangle_color_stays_clear_when_opacity_is_set(self) -> None:
        """Opacity does not invent a fill when the rectangle color is blank."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            skeleton.background_color = "#FF0000"
            skeleton.page_margin = 0
            skeleton.element_margin = 0
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            text_element: SkeletonElement = _text_element(
                skeleton,
                SkeletonElementBand.TOP,
                SkeletonElementTextSource.TITLE,
                rectangle_color=None,
                rectangle_opacity=50,
                rectangle_radius=40,
            )
            skeleton.elements.append(text_element)
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertEqual(_pixel(preview_path, 1000, 12), (255, 0, 0, 255))

    def test_rectangle_radius_rounds_the_corner_and_clamps(self) -> None:
        """A large radius leaves the corner on the background and fills inside."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            skeleton.background_color = "#0000FF"
            skeleton.page_margin = 0
            skeleton.element_margin = 0
            source_item: SourceItem = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            rounded_element: SkeletonElement = _text_element(
                skeleton,
                SkeletonElementBand.TOP,
                SkeletonElementTextSource.TITLE,
                rectangle_color="#FFFFFF",
                rectangle_opacity=100,
                rectangle_radius=5000,
            )
            skeleton.elements.append(rounded_element)
            response: SkeletonSampleResponse
            _, response = _create_sample(skeleton, source_item, storage)
            preview_path: Path = _preview_path(storage, skeleton.id, response.preview_id)

            self.assertFalse(response.blocked)
            self.assertEqual(_pixel(preview_path, 0, 0), (0, 0, 255, 255))
            self.assertEqual(_pixel(preview_path, 900, 20), (255, 255, 255, 255))

        with tempfile.TemporaryDirectory() as storage_directory:
            storage = Path(storage_directory)
            skeleton = _skeleton_row(SkeletonStatus.DRAFT)
            skeleton.background_color = "#0000FF"
            skeleton.page_margin = 0
            skeleton.element_margin = 0
            source_item = _source_item("Harbor light", SourceType.SPOTMU_INTEREST)
            square_element: SkeletonElement = _text_element(
                skeleton,
                SkeletonElementBand.TOP,
                SkeletonElementTextSource.TITLE,
                rectangle_color="#FFFFFF",
                rectangle_opacity=100,
                rectangle_radius=0,
            )
            skeleton.elements.append(square_element)
            response_square: SkeletonSampleResponse
            _, response_square = _create_sample(skeleton, source_item, storage)
            square_path: Path = _preview_path(storage, skeleton.id, response_square.preview_id)

            self.assertEqual(_pixel(square_path, 0, 0), (255, 255, 255, 255))

    def _assert_no_artifact_or_post_job(self, session: "_SampleMemorySession") -> None:
        """The handler must not insert an artifact or a post job, or commit."""

        for added_row in session.added:
            self.assertNotIsInstance(added_row, Artifact)
            self.assertNotIsInstance(added_row, PostJob)

        self.assertEqual(session.added, [])
        self.assertEqual(session.commit_count, 0)


class _SampleMemorySession:
    """In-memory skeleton and carousel lookup. Records inserts. Not a database."""

    def __init__(self, skeleton: Skeleton, source_item: SourceItem | None) -> None:

        self.skeleton: Skeleton = skeleton
        self.source_item: SourceItem | None = source_item
        self.added: list[object] = []
        self.commit_count: int = 0

    def get(self, model: type[object], key: uuid.UUID) -> Skeleton | SourceItem | None:
        """Return the skeleton or source item when the id matches."""

        if model is Skeleton and key == self.skeleton.id:

            return self.skeleton

        if (
            model is SourceItem
            and self.source_item is not None
            and key == self.source_item.id
        ):

            return self.source_item

        return None

    def add(self, row: object) -> None:
        """Record an insert the sample handler must not make."""

        self.added.append(row)

    def commit(self) -> None:
        """Record a commit the sample handler must not make."""

        self.commit_count += 1


def _create_sample(
    skeleton: Skeleton,
    source_item: SourceItem,
    storage: Path,
) -> tuple[_SampleMemorySession, SkeletonSampleResponse]:
    """POST one sample against the in-memory session and this store."""

    session: _SampleMemorySession = _SampleMemorySession(skeleton, source_item)
    settings: MagicMock = _settings(storage)

    with patch("app.api.v1.skeleton_samples.get_settings", return_value=settings):
        response: SkeletonSampleResponse = create_skeleton_sample(
            skeleton.id,
            SkeletonSampleRequest(source_item_id=source_item.id),
            session,
        )

    return session, response


def _get_image(skeleton: Skeleton, preview_id: uuid.UUID, storage: Path) -> FileResponse:
    """GET the preview PNG through the handler."""

    session: _SampleMemorySession = _SampleMemorySession(skeleton, None)
    settings: MagicMock = _settings(storage)

    with patch("app.api.v1.skeleton_samples.get_settings", return_value=settings):
        image_response: FileResponse = get_skeleton_sample_image(
            skeleton.id,
            preview_id,
            session,
        )

    return image_response


def _settings(storage: Path) -> MagicMock:
    """Point ARTIFACT_STORAGE_DIR at the test directory."""

    settings: MagicMock = MagicMock()
    settings.artifact_storage_dir = str(storage)

    return settings


def _skeleton_row(status: SkeletonStatus) -> Skeleton:
    """Build an in-memory carousel skeleton. Nothing is written."""

    skeleton: Skeleton = Skeleton(
        id=uuid.uuid4(),
        name="Harbor",
        slug="harbor",
        advertisement_type=AdvertisementType.CAROUSEL,
        template_key="spotmu_paper_v1",
        status=status,
        page_margin=DEFAULT_PAGE_MARGIN,
        element_gap=DEFAULT_ELEMENT_GAP,
        element_margin=DEFAULT_ELEMENT_MARGIN,
        background_kind=BackgroundKind.COLOR,
        background_color=DEFAULT_BACKGROUND_COLOR,
        background_gradient=None,
        background_asset_ref=None,
        created_by=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    return skeleton


def _source_item(title: str, source_type: SourceType) -> SourceItem:
    """Build an in-memory source item. Nothing is written."""

    source_item: SourceItem = SourceItem(
        id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
        source_type=source_type,
        external_key="example",
        title=title,
        interest_heading="Evening",
        overview_bullets=["One"],
        canonical_url="https://example.test/harbor",
    )

    return source_item


def _text_element(
    skeleton: Skeleton,
    band: SkeletonElementBand,
    text_source: SkeletonElementTextSource,
    rectangle_color: str | None,
    rectangle_opacity: int | None = None,
    rectangle_radius: int | None = None,
    font_family: str = "DejaVu Sans",
    font_size: int = 64,
) -> SkeletonElement:
    """Build one text element. Family is a face installed on this machine."""

    text_element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=skeleton.id,
        band=band,
        sort_order=0,
        content_kind=SkeletonElementContentKind.TEXT,
        name="Title",
        rectangle_color=rectangle_color,
        text_source=text_source,
        font_family=font_family,
        font_size=font_size,
        font_color="#112233",
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        font_weight=None,
        alignment=SkeletonElementAlignment.LEFT,
        image_asset_ref=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    if rectangle_opacity is not None:
        text_element.rectangle_opacity = rectangle_opacity

    if rectangle_radius is not None:
        text_element.rectangle_radius = rectangle_radius

    return text_element


def _image_element(
    skeleton: Skeleton,
    band: SkeletonElementBand,
    image_asset_ref: str,
    rectangle_color: str | None,
) -> SkeletonElement:
    """Build one image element. The file may or may not exist yet."""

    image_element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=skeleton.id,
        band=band,
        sort_order=0,
        content_kind=SkeletonElementContentKind.IMAGE,
        name="Image",
        rectangle_color=rectangle_color,
        text_source=None,
        font_family=None,
        font_size=None,
        font_color=None,
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        font_weight=None,
        alignment=None,
        image_asset_ref=image_asset_ref,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    return image_element


def _solid_png(
    path: Path,
    width: int,
    height: int,
    color: tuple[int, int, int],
) -> None:
    """Write a solid PNG under the test store."""

    path.parent.mkdir(parents=True, exist_ok=True)
    image: Image.Image = Image.new("RGB", (width, height), color)
    image.save(path, format="PNG")


def _preview_path(storage: Path, skeleton_id: uuid.UUID, preview_id: uuid.UUID) -> Path:
    """Return the preview path the handler is supposed to write."""

    preview_path: Path = storage / "skeleton-previews" / str(skeleton_id) / f"{preview_id}.png"

    return preview_path


def _image_size(path: Path) -> tuple[int, int]:
    """Return the PNG size."""

    with Image.open(path) as image:
        image_size: tuple[int, int] = image.size

    return image_size


def _pixel(path: Path, x: int, y: int) -> tuple[int, int, int, int]:
    """Return one RGBA pixel."""

    with Image.open(path) as image:
        rgba_image: Image.Image = image.convert("RGBA")
        raw_pixel: object = rgba_image.getpixel((x, y))

    if not isinstance(raw_pixel, tuple) or len(raw_pixel) != 4:
        raise AssertionError(raw_pixel)

    red: int = int(raw_pixel[0])
    green: int = int(raw_pixel[1])
    blue: int = int(raw_pixel[2])
    alpha: int = int(raw_pixel[3])

    return red, green, blue, alpha


def _has_different_pixel(
    path: Path,
    background: tuple[int, int, int, int],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> bool:
    """True when any pixel in the box is not the background."""

    with Image.open(path) as image:
        rgba_image: Image.Image = image.convert("RGBA")

        for pixel_y in range(y0, y1):

            for pixel_x in range(x0, x1):
                raw_pixel: object = rgba_image.getpixel((pixel_x, pixel_y))

                if raw_pixel != background:

                    return True

    return False


if __name__ == "__main__":
    unittest.main()
