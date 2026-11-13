"""Draw one live slide with the skeleton. A blocked frame still writes a PNG."""

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from PIL import Image

from app.carousels.final_render import (
    AssembledFrameRender,
    render_assembled_frame,
    slide_fill_from_live_slide,
)
from app.carousels.slide_skeleton import SlideSkeletonFill
from app.models.album import AlbumImage
from app.models.carousel import Slide, SlideElementText
from app.models.enums import (
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
from app.models.skeleton import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
    Skeleton,
)
from app.models.skeleton_element import SkeletonElement
from app.skeletons.layout import SKELETON_FRAME_HEIGHT_PIXELS, SKELETON_FRAME_WIDTH_PIXELS


PNG_SIGNATURE: bytes = b"\x89PNG\r\n\x1a\n"
CREATED_AT: datetime = datetime(2026, 11, 13, tzinfo=timezone.utc)
LIVE_TEXT: str = "Reviewed line"
DRAFT_TEXT: str = "Not the live line"
MISSING_IMAGE_PATH: str = "backgrounds/missing.png"


class SlideFillTests(unittest.TestCase):
    """Live text is the fill. Draft text and a missing image stay out."""

    def test_live_value_is_kept_and_draft_value_is_ignored(self) -> None:
        """The fill uses ``Reviewed line`` and the album path."""

        element_id: uuid.UUID = uuid.uuid4()
        slide: Slide = _slide()
        slide.element_texts = [_element_text(slide, element_id, LIVE_TEXT, DRAFT_TEXT)]
        slide.album_image = _album_image("albums/harbor.png")
        fill: SlideSkeletonFill = slide_fill_from_live_slide(slide)

        self.assertEqual(fill.text_by_element_id, {element_id: LIVE_TEXT})
        self.assertNotIn(DRAFT_TEXT, fill.text_by_element_id.values())
        self.assertEqual(fill.slide_image_relative_path, "albums/harbor.png")

    def test_a_slide_with_no_album_image_has_a_null_path(self) -> None:
        """No album image leaves the fill path null."""

        slide: Slide = _slide()
        fill: SlideSkeletonFill = slide_fill_from_live_slide(slide)

        self.assertEqual(fill.text_by_element_id, {})
        self.assertIsNone(fill.slide_image_relative_path)


class RenderAssembledFrameTests(unittest.TestCase):
    """The skeleton drawer writes the PNG. No artifact row is created."""

    def test_a_color_skeleton_writes_an_unblocked_png(self) -> None:
        """Reviewed text on a color frame is a PNG and is not blocked."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _color_skeleton()
            text_element: SkeletonElement = _text_element(skeleton)
            skeleton.elements.append(text_element)
            slide: Slide = _slide()
            slide.element_texts = [
                _element_text(slide, text_element.id, LIVE_TEXT, DRAFT_TEXT),
            ]
            rendered: AssembledFrameRender = _render(skeleton, slide, storage)
            png_path: Path = storage / rendered.asset_ref

            self.assertFalse(rendered.blocked)
            self.assertIsNone(rendered.block_reason)
            self.assertTrue(png_path.is_file())
            self.assertEqual(png_path.read_bytes()[:8], PNG_SIGNATURE)
            self.assertEqual(
                _image_size(png_path),
                (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS),
            )

    def test_a_missing_picture_is_blocked_and_still_writes_the_png(self) -> None:
        """A picture path that is not on disk is missing_asset, and the file exists."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            skeleton: Skeleton = _color_skeleton()
            skeleton.background_kind = BackgroundKind.PICTURE
            skeleton.background_color = None
            skeleton.background_asset_ref = MISSING_IMAGE_PATH
            slide: Slide = _slide()
            slide.album_image = _album_image(MISSING_IMAGE_PATH)
            rendered: AssembledFrameRender = _render(skeleton, slide, storage)
            png_path: Path = storage / rendered.asset_ref

            self.assertTrue(rendered.blocked)
            self.assertEqual(rendered.block_reason, "missing_asset")
            self.assertTrue(png_path.is_file())
            self.assertEqual(png_path.read_bytes()[:8], PNG_SIGNATURE)

    def test_an_overlap_is_blocked_and_still_writes_the_png(self) -> None:
        """Top through middle is overlap, and the PNG is still written."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            _solid_png(storage / "images" / "top.png", 10, 10, (255, 0, 0))
            _solid_png(storage / "images" / "middle.png", 10, 10, (0, 0, 255))
            skeleton: Skeleton = _color_skeleton()
            skeleton.elements.append(
                _image_element(skeleton, SkeletonElementBand.TOP, "images/top.png"),
            )
            skeleton.elements.append(
                _image_element(skeleton, SkeletonElementBand.MIDDLE, "images/middle.png"),
            )
            slide: Slide = _slide()
            slide.album_image = _album_image("images/top.png")
            rendered: AssembledFrameRender = _render(skeleton, slide, storage)
            png_path: Path = storage / rendered.asset_ref

            self.assertTrue(rendered.blocked)
            self.assertEqual(rendered.block_reason, "overlap")
            self.assertTrue(png_path.is_file())
            self.assertEqual(png_path.read_bytes()[:8], PNG_SIGNATURE)


def _render(skeleton: Skeleton, slide: Slide, storage: Path) -> AssembledFrameRender:
    """Draw one frame into the temporary store."""

    rendered: AssembledFrameRender = render_assembled_frame(
        skeleton,
        slide,
        storage,
        uuid.uuid4(),
        uuid.uuid4(),
    )

    return rendered


def _color_skeleton() -> Skeleton:
    """A paper color skeleton with no elements yet."""

    skeleton: Skeleton = Skeleton(
        id=uuid.uuid4(),
        name="Harbor",
        slug="harbor-final",
        advertisement_type=AdvertisementType.CAROUSEL,
        status=SkeletonStatus.LIVE,
        page_margin=DEFAULT_PAGE_MARGIN,
        element_gap=DEFAULT_ELEMENT_GAP,
        element_margin=DEFAULT_ELEMENT_MARGIN,
        background_kind=BackgroundKind.COLOR,
        background_color=DEFAULT_BACKGROUND_COLOR,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    return skeleton


def _text_element(skeleton: Skeleton) -> SkeletonElement:
    """One text element whose live value is the frame copy."""

    text_element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=skeleton.id,
        band=SkeletonElementBand.TOP,
        sort_order=0,
        content_kind=SkeletonElementContentKind.TEXT,
        name="Title",
        text_source=None,
        font_family="DejaVu Sans",
        font_size=64,
        font_color="#112233",
        alignment=SkeletonElementAlignment.LEFT,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    return text_element


def _image_element(
    skeleton: Skeleton,
    band: SkeletonElementBand,
    image_asset_ref: str,
) -> SkeletonElement:
    """One image element. The slide fill replaces the stored path when drawing."""

    image_element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=skeleton.id,
        band=band,
        sort_order=0,
        content_kind=SkeletonElementContentKind.IMAGE,
        name="Photo",
        text_source=None,
        image_asset_ref=image_asset_ref,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    return image_element


def _slide() -> Slide:
    """A live slide with no texts and no image until the test sets them."""

    slide: Slide = Slide(
        id=uuid.uuid4(),
        carousel_id=uuid.uuid4(),
        position=0,
        name="Quay",
        text_status=SlideTextStatus.LIVE,
    )

    return slide


def _element_text(
    slide: Slide,
    element_id: uuid.UUID,
    value: str,
    draft_value: str,
) -> SlideElementText:
    """One stored text. The draft string must not become the fill."""

    element_text: SlideElementText = SlideElementText(
        id=uuid.uuid4(),
        slide_id=slide.id,
        skeleton_element_id=element_id,
        value=value,
        draft_value=draft_value,
    )

    return element_text


def _album_image(relative_path: str) -> AlbumImage:
    """An album image pointer. The file may or may not exist."""

    album_image: AlbumImage = AlbumImage(
        id=uuid.uuid4(),
        album_id=uuid.uuid4(),
        position=0,
        relative_path=relative_path,
        media_type=SlideImageMediaType.PNG,
        byte_size=10,
        width=10,
        height=10,
        license=SlideImageLicense.CC0,
        source="probe",
        license_note="",
        intake=SlideImageIntake.UPLOAD,
    )

    return album_image


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


def _image_size(path: Path) -> tuple[int, int]:
    """Return the PNG size."""

    with Image.open(path) as image:
        image_size: tuple[int, int] = image.size

    return image_size


if __name__ == "__main__":
    unittest.main()
