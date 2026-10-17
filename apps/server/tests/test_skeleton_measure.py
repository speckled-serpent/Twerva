"""Skeleton measurement (1.10e-ii and 1.10e-iii). No overlap and no PNG output."""

import tempfile
import unittest
import uuid
from pathlib import Path

from PIL import Image

from app.models.enums import (
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
)
from app.skeletons.layout import (
    SKELETON_FRAME_HEIGHT_PIXELS,
    SKELETON_FRAME_WIDTH_PIXELS,
    LayoutRectangle,
    SkeletonLayout,
)
from app.skeletons.measure import (
    MeasureProblem,
    MeasureProblemCode,
    SkeletonMeasureElement,
    SkeletonMeasurement,
    measure_skeleton_elements,
)


FIRST_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000101")
LATER_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000102")
OTHER_BAND_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000103")
IMAGE_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000201")

PAGE_MARGIN: int = 96
ELEMENT_GAP: int = 12
ELEMENT_MARGIN: int = 16
FONT_FAMILY: str = "DejaVu Sans"
LONG_TEXT: str = ("alpha " * 40).strip()


class SkeletonTextMeasureTests(unittest.TestCase):
    """Wrap changes height, and only the later sibling in that band moves."""

    def test_long_string_grows_height_and_moves_only_the_later_sibling(self) -> None:
        """A longer top string grows that element and pushes the next top element.

        The first top element stays on the page margin. The later top
        element's own height stays put. A bottom element does not move.
        """

        short_measurement: SkeletonMeasurement = self._measure_top_pair("Hi")
        long_measurement: SkeletonMeasurement = self._measure_top_pair(LONG_TEXT)
        short_first: LayoutRectangle = _rectangle(short_measurement.layout, FIRST_ID)
        long_first: LayoutRectangle = _rectangle(long_measurement.layout, FIRST_ID)
        short_later: LayoutRectangle = _rectangle(short_measurement.layout, LATER_ID)
        long_later: LayoutRectangle = _rectangle(long_measurement.layout, LATER_ID)
        short_bottom: LayoutRectangle = _rectangle(
            short_measurement.layout,
            OTHER_BAND_ID,
        )
        long_bottom: LayoutRectangle = _rectangle(
            long_measurement.layout,
            OTHER_BAND_ID,
        )
        height_delta: int = long_first.height - short_first.height
        later_y_delta: int = long_later.y - short_later.y

        self.assertGreater(height_delta, 0)
        self.assertEqual(later_y_delta, height_delta)
        self.assertEqual(long_later.height, short_later.height)
        self.assertEqual(long_first.y, short_first.y)
        self.assertEqual(long_first.y, PAGE_MARGIN)
        self.assertEqual(long_bottom.y, short_bottom.y)
        self.assertEqual(long_bottom.height, short_bottom.height)
        self.assertEqual(short_measurement.problems, ())
        self.assertEqual(long_measurement.problems, ())

    def test_underline_does_not_change_height(self) -> None:
        """Underline and strikethrough leave the placed rectangles unchanged."""

        plain_measurement: SkeletonMeasurement = self._measure_top_pair(LONG_TEXT)
        underlined_measurement: SkeletonMeasurement = self._measure_top_pair(
            LONG_TEXT,
            underline=True,
        )
        struck_measurement: SkeletonMeasurement = self._measure_top_pair(
            LONG_TEXT,
            strikethrough=True,
        )

        self.assertEqual(plain_measurement.layout, underlined_measurement.layout)
        self.assertEqual(plain_measurement.layout, struck_measurement.layout)
        self.assertEqual(underlined_measurement.problems, ())

    def test_middle_block_recenters_when_text_grows(self) -> None:
        """Growing the first middle element recenters the whole middle block."""

        short_measurement: SkeletonMeasurement = self._measure_pair(
            SkeletonElementBand.MIDDLE,
            "Hi",
        )
        long_measurement: SkeletonMeasurement = self._measure_pair(
            SkeletonElementBand.MIDDLE,
            LONG_TEXT,
        )
        short_first: LayoutRectangle = _rectangle(short_measurement.layout, FIRST_ID)
        long_first: LayoutRectangle = _rectangle(long_measurement.layout, FIRST_ID)
        short_later: LayoutRectangle = _rectangle(short_measurement.layout, LATER_ID)
        long_later: LayoutRectangle = _rectangle(long_measurement.layout, LATER_ID)

        self.assertGreater(long_first.height, short_first.height)
        self.assertNotEqual(long_first.y, short_first.y)
        self.assertEqual(long_later.height, short_later.height)
        self.assertNotEqual(long_later.y, short_later.y)
        _assert_block_is_centered(self, short_measurement.layout)
        _assert_block_is_centered(self, long_measurement.layout)

    def test_bottom_reflows_upward_from_the_lowest_element(self) -> None:
        """A taller lowest element stays on the bottom margin and lifts the next one."""

        short_measurement: SkeletonMeasurement = self._measure_pair(
            SkeletonElementBand.BOTTOM,
            "Hi",
        )
        long_measurement: SkeletonMeasurement = self._measure_pair(
            SkeletonElementBand.BOTTOM,
            LONG_TEXT,
        )
        short_first: LayoutRectangle = _rectangle(short_measurement.layout, FIRST_ID)
        long_first: LayoutRectangle = _rectangle(long_measurement.layout, FIRST_ID)
        short_later: LayoutRectangle = _rectangle(short_measurement.layout, LATER_ID)
        long_later: LayoutRectangle = _rectangle(long_measurement.layout, LATER_ID)
        bottom_edge: int = SKELETON_FRAME_HEIGHT_PIXELS - PAGE_MARGIN
        height_delta: int = long_first.height - short_first.height

        self.assertGreater(height_delta, 0)
        self.assertEqual(short_first.y + short_first.height, bottom_edge)
        self.assertEqual(long_first.y + long_first.height, bottom_edge)
        self.assertEqual(short_later.y - long_later.y, height_delta)
        self.assertEqual(long_later.height, short_later.height)

    def test_font_size_and_bold_and_weight_change_measurement(self) -> None:
        """Size, the bold flag, and a bold weight change height. Empty text is one line."""

        small_height: int = self._only_height("Hi", font_size=12)
        large_height: int = self._only_height("Hi", font_size=48)
        empty_height: int = self._only_height("", font_size=48)
        regular_height: int = self._narrow_height("MM MM", bold=False, font_weight=None)
        bold_height: int = self._narrow_height("MM MM", bold=True, font_weight=None)
        weight_400_height: int = self._narrow_height("MM MM", bold=False, font_weight=400)
        weight_700_height: int = self._narrow_height("MM MM", bold=False, font_weight=700)
        missing_face_height: int = self._only_height(
            "Hi",
            font_size=48,
            font_family="No Such Face",
        )

        self.assertGreater(large_height, small_height)
        self.assertEqual(empty_height, large_height)
        self.assertGreater(bold_height, regular_height)
        self.assertEqual(weight_400_height, regular_height)
        self.assertEqual(weight_700_height, bold_height)
        self.assertEqual(missing_face_height, large_height)

    def test_alignment_does_not_change_the_rectangle(self) -> None:
        """Left and right alignment place the same rectangle."""

        left_height: int = self._only_height(
            LONG_TEXT,
            alignment=SkeletonElementAlignment.LEFT,
        )
        right_height: int = self._only_height(
            LONG_TEXT,
            alignment=SkeletonElementAlignment.RIGHT,
        )

        self.assertEqual(left_height, right_height)

    def _measure_top_pair(
        self,
        first_text: str,
        underline: bool = False,
        strikethrough: bool = False,
    ) -> SkeletonMeasurement:
        """Two top elements and one bottom element."""

        elements: list[SkeletonMeasureElement] = [
            _text_element(
                FIRST_ID,
                SkeletonElementBand.TOP,
                0,
                first_text,
                underline=underline,
                strikethrough=strikethrough,
            ),
            _text_element(LATER_ID, SkeletonElementBand.TOP, 1, "Later"),
            _text_element(OTHER_BAND_ID, SkeletonElementBand.BOTTOM, 0, "Bottom"),
        ]

        return _measure(elements, PAGE_MARGIN, ELEMENT_GAP, ELEMENT_MARGIN)

    def _measure_pair(self, band: SkeletonElementBand, first_text: str) -> SkeletonMeasurement:
        """Two elements in one band. The second text stays ``Later``."""

        elements: list[SkeletonMeasureElement] = [
            _text_element(LATER_ID, band, 1, "Later"),
            _text_element(FIRST_ID, band, 0, first_text),
        ]

        return _measure(elements, PAGE_MARGIN, ELEMENT_GAP, ELEMENT_MARGIN)

    def _only_height(
        self,
        text: str,
        font_size: int = 48,
        font_family: str = FONT_FAMILY,
        alignment: SkeletonElementAlignment = SkeletonElementAlignment.LEFT,
    ) -> int:
        """Rectangle height of one top element."""

        elements: list[SkeletonMeasureElement] = [
            _text_element(
                FIRST_ID,
                SkeletonElementBand.TOP,
                0,
                text,
                font_size=font_size,
                font_family=font_family,
                alignment=alignment,
            ),
        ]
        measurement: SkeletonMeasurement = _measure(
            elements,
            PAGE_MARGIN,
            ELEMENT_GAP,
            ELEMENT_MARGIN,
        )
        rectangle: LayoutRectangle = _rectangle(measurement.layout, FIRST_ID)

        return rectangle.height

    def _narrow_height(
        self,
        text: str,
        bold: bool,
        font_weight: int | None,
    ) -> int:
        """Height when the content width is 200 pixels, between regular and bold."""

        elements: list[SkeletonMeasureElement] = [
            _text_element(
                FIRST_ID,
                SkeletonElementBand.TOP,
                0,
                text,
                bold=bold,
                font_weight=font_weight,
            ),
        ]
        measurement: SkeletonMeasurement = _measure(
            elements,
            page_margin=40,
            element_gap=0,
            element_margin=400,
        )
        rectangle: LayoutRectangle = _rectangle(measurement.layout, FIRST_ID)

        return rectangle.height


class SkeletonImageMeasureTests(unittest.TestCase):
    """PNG, JPEG, and SVG heights. A bad file does not invent a rectangle."""

    def test_png_aspect_ratio_sets_content_height(self) -> None:
        """A 200×50 PNG on a 1000px content width is 250px tall."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_directory: Path = Path(temporary_directory)
            image_path: Path = storage_directory / "wide.png"
            image: Image.Image = Image.new("RGB", (200, 50), (10, 20, 30))
            image.save(image_path, format="PNG")
            measurement: SkeletonMeasurement = _measure_image(
                "wide.png",
                storage_directory,
            )
            rectangle: LayoutRectangle = _rectangle(measurement.layout, IMAGE_ID)

            self.assertEqual(measurement.problems, ())
            self.assertEqual(rectangle.x, 40)
            self.assertEqual(rectangle.y, 40)
            self.assertEqual(rectangle.width, 1000)
            self.assertEqual(rectangle.height, 250)

    def test_jpeg_aspect_ratio_sets_content_height(self) -> None:
        """JPEG uses the same Pillow scale as PNG."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_directory: Path = Path(temporary_directory)
            image_path: Path = storage_directory / "wide.jpg"
            image: Image.Image = Image.new("RGB", (200, 50), (10, 20, 30))
            image.save(image_path, format="JPEG")
            measurement: SkeletonMeasurement = _measure_image(
                "wide.jpg",
                storage_directory,
            )
            rectangle: LayoutRectangle = _rectangle(measurement.layout, IMAGE_ID)

            self.assertEqual(rectangle.height, 250)
            self.assertEqual(measurement.problems, ())

    def test_svg_view_box_sets_content_height(self) -> None:
        """A tiny viewBox of 4×2 scales to half the content width."""

        svg_text: str = (
            '<?xml version="1.0"?>'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 2"></svg>'
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_directory: Path = Path(temporary_directory)
            svg_path: Path = storage_directory / "mark.svg"
            svg_path.write_text(svg_text, encoding="utf-8")
            measurement: SkeletonMeasurement = _measure_image(
                "mark.svg",
                storage_directory,
            )
            rectangle: LayoutRectangle = _rectangle(measurement.layout, IMAGE_ID)

            self.assertEqual(measurement.problems, ())
            self.assertEqual(rectangle.height, 500)
            self.assertEqual(rectangle.width, 1000)

    def test_svg_width_and_height_win_over_view_box(self) -> None:
        """``width`` and ``height`` set the ratio when both are present."""

        svg_text: str = (
            '<svg width="200px" height="50" viewBox="0 0 10 10"></svg>'
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_directory: Path = Path(temporary_directory)
            svg_path: Path = storage_directory / "sized.svg"
            svg_path.write_text(svg_text, encoding="utf-8")
            measurement: SkeletonMeasurement = _measure_image(
                "sized.svg",
                storage_directory,
            )
            rectangle: LayoutRectangle = _rectangle(measurement.layout, IMAGE_ID)

            self.assertEqual(rectangle.height, 250)

    def test_missing_file_returns_the_error_without_a_rectangle(self) -> None:
        """A missing image is a measure problem and adds no rectangle."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_directory: Path = Path(temporary_directory)
            measurement: SkeletonMeasurement = _measure_image(
                "missing.png",
                storage_directory,
            )

            self.assertEqual(measurement.layout.rectangles, ())
            self.assertEqual(len(measurement.problems), 1)
            problem: MeasureProblem = measurement.problems[0]
            self.assertEqual(problem.element_id, IMAGE_ID)
            self.assertEqual(problem.code, MeasureProblemCode.MISSING_ASSET)

    def test_unreadable_file_returns_the_error_without_a_rectangle(self) -> None:
        """Bytes that are not a PNG do not get a guessed size."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_directory: Path = Path(temporary_directory)
            broken_path: Path = storage_directory / "broken.png"
            broken_path.write_text("not a png", encoding="utf-8")
            measurement: SkeletonMeasurement = _measure_image(
                "broken.png",
                storage_directory,
            )

            self.assertEqual(measurement.layout.rectangles, ())
            self.assertEqual(
                measurement.problems[0].code,
                MeasureProblemCode.UNREADABLE_ASSET,
            )

    def test_path_escape_returns_the_error_without_a_rectangle(self) -> None:
        """A ref that walks out of the store is not read."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_directory: Path = Path(temporary_directory) / "store"
            storage_directory.mkdir()
            outside_path: Path = storage_directory.parent / "outside.png"
            outside_image: Image.Image = Image.new("RGB", (200, 50), (1, 2, 3))
            outside_image.save(outside_path, format="PNG")
            measurement: SkeletonMeasurement = _measure_image(
                "../outside.png",
                storage_directory,
            )

            self.assertEqual(measurement.layout.rectangles, ())
            self.assertEqual(
                measurement.problems[0].code,
                MeasureProblemCode.PATH_ESCAPE,
            )
            self.assertTrue(outside_path.is_file())


def _measure(
    elements: list[SkeletonMeasureElement],
    page_margin: int,
    element_gap: int,
    element_margin: int,
    artifact_storage_directory: Path | None = None,
) -> SkeletonMeasurement:
    """Measure a frame. Text tests can pass an empty storage directory."""

    storage_directory: Path = artifact_storage_directory or Path(".")
    measurement: SkeletonMeasurement = measure_skeleton_elements(
        SKELETON_FRAME_WIDTH_PIXELS,
        SKELETON_FRAME_HEIGHT_PIXELS,
        page_margin,
        element_gap,
        element_margin,
        elements,
        storage_directory,
    )

    return measurement


def _measure_image(image_asset_ref: str, storage_directory: Path) -> SkeletonMeasurement:
    """One top image, page margin 40, no element margin. Content width is 1000."""

    image_element: SkeletonMeasureElement = SkeletonMeasureElement(
        element_id=IMAGE_ID,
        band=SkeletonElementBand.TOP,
        sort_order=0,
        content_kind=SkeletonElementContentKind.IMAGE,
        image_asset_ref=image_asset_ref,
    )

    return _measure(
        [image_element],
        page_margin=40,
        element_gap=0,
        element_margin=0,
        artifact_storage_directory=storage_directory,
    )


def _text_element(
    element_id: uuid.UUID,
    band: SkeletonElementBand,
    sort_order: int,
    text: str,
    font_size: int = 48,
    font_family: str = FONT_FAMILY,
    bold: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    font_weight: int | None = None,
    alignment: SkeletonElementAlignment = SkeletonElementAlignment.LEFT,
) -> SkeletonMeasureElement:
    """A text element with resolved copy and a face."""

    element: SkeletonMeasureElement = SkeletonMeasureElement(
        element_id=element_id,
        band=band,
        sort_order=sort_order,
        content_kind=SkeletonElementContentKind.TEXT,
        resolved_text=text,
        font_family=font_family,
        font_size=font_size,
        bold=bold,
        underline=underline,
        strikethrough=strikethrough,
        font_weight=font_weight,
        alignment=alignment,
    )

    return element


def _rectangle(layout: SkeletonLayout, element_id: uuid.UUID) -> LayoutRectangle:
    """Return the placed rectangle for ``element_id``."""

    for rectangle in layout.rectangles:

        if rectangle.element_id == element_id:

            return rectangle

    raise AssertionError(f"missing rectangle for {element_id}")


def _assert_block_is_centered(test_case: unittest.TestCase, layout: SkeletonLayout) -> None:
    """The middle block's leftover pixel, if any, sits below the block."""

    content_top: int = layout.content_area.y
    content_bottom: int = content_top + layout.content_area.height
    block_top: int = min(rectangle.y for rectangle in layout.rectangles)
    block_bottom: int = max(
        rectangle.y + rectangle.height
        for rectangle in layout.rectangles
    )
    space_above: int = block_top - content_top
    space_below: int = content_bottom - block_bottom

    test_case.assertGreaterEqual(space_below, space_above)
    test_case.assertLessEqual(space_below - space_above, 1)


if __name__ == "__main__":
    unittest.main()
