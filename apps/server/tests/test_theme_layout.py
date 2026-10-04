"""Theme layout math (1.10d-i). No fonts, files, or overlap policy."""

import unittest
import uuid

from app.models.enums import ThemeElementBand
from app.themes.layout import (
    THEME_FRAME_HEIGHT_PIXELS,
    THEME_FRAME_WIDTH_PIXELS,
    ContentArea,
    LayoutElement,
    LayoutRectangle,
    ThemeLayout,
    place_theme_elements,
)


TOP_FIRST_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
TOP_SECOND_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")
MIDDLE_FIRST_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000011")
MIDDLE_SECOND_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000012")
MIDDLE_THIRD_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000013")
BOTTOM_FIRST_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000021")
BOTTOM_SECOND_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000022")


class ThemeLayoutTests(unittest.TestCase):
    """Top from the top, bottom from the bottom, middle centered as a group."""

    def test_single_top_element(self) -> None:
        """One top element starts at the page margin and spans the content width.

        Content height 50 and element margin 12 make a rectangle 74 tall.
        The unused gap is not added above it.
        """

        top_element: LayoutElement = LayoutElement(
            element_id=TOP_FIRST_ID,
            band=ThemeElementBand.TOP,
            sort_order=0,
            content_height=50,
        )
        placed_layout: ThemeLayout = place_theme_elements(
            THEME_FRAME_WIDTH_PIXELS,
            THEME_FRAME_HEIGHT_PIXELS,
            96,
            40,
            12,
            [top_element],
        )
        expected_layout: ThemeLayout = ThemeLayout(
            content_area=ContentArea(x=96, y=96, width=888, height=888),
            rectangles=(
                LayoutRectangle(
                    element_id=TOP_FIRST_ID,
                    x=96,
                    y=96,
                    width=888,
                    height=74,
                ),
            ),
        )

        self.assertEqual(placed_layout, expected_layout)
        self._assert_layout_uses_ints(placed_layout)

    def test_two_top_elements_put_gap_only_between_them(self) -> None:
        """Gap sits between the two rectangles, not above the first or inside the margin.

        Input order is the reverse of ``sort_order``. The list is not mutated.
        """

        later_element: LayoutElement = LayoutElement(
            element_id=TOP_SECOND_ID,
            band=ThemeElementBand.TOP,
            sort_order=1,
            content_height=40,
        )
        earlier_element: LayoutElement = LayoutElement(
            element_id=TOP_FIRST_ID,
            band=ThemeElementBand.TOP,
            sort_order=0,
            content_height=120,
        )
        input_elements: list[LayoutElement] = [later_element, earlier_element]
        placed_layout: ThemeLayout = place_theme_elements(
            THEME_FRAME_WIDTH_PIXELS,
            THEME_FRAME_HEIGHT_PIXELS,
            96,
            16,
            0,
            input_elements,
        )
        expected_layout: ThemeLayout = ThemeLayout(
            content_area=ContentArea(x=96, y=96, width=888, height=888),
            rectangles=(
                LayoutRectangle(
                    element_id=TOP_FIRST_ID,
                    x=96,
                    y=96,
                    width=888,
                    height=120,
                ),
                LayoutRectangle(
                    element_id=TOP_SECOND_ID,
                    x=96,
                    y=232,
                    width=888,
                    height=40,
                ),
            ),
        )
        first_rectangle: LayoutRectangle = placed_layout.rectangles[0]
        second_rectangle: LayoutRectangle = placed_layout.rectangles[1]
        gap_between: int = second_rectangle.y - (first_rectangle.y + first_rectangle.height)

        self.assertEqual(placed_layout, expected_layout)
        self.assertEqual(gap_between, 16)
        self.assertEqual(first_rectangle.y, 96)
        self.assertEqual(input_elements, [later_element, earlier_element])
        self._assert_layout_uses_ints(placed_layout)

    def test_two_bottom_elements_stack_upward(self) -> None:
        """The first bottom element is the lowest. The next one sits above it.

        Element margin 10 is inside each rectangle. Gap 20 is between them,
        not below the lowest element.
        """

        upper_element: LayoutElement = LayoutElement(
            element_id=BOTTOM_SECOND_ID,
            band=ThemeElementBand.BOTTOM,
            sort_order=1,
            content_height=60,
        )
        lowest_element: LayoutElement = LayoutElement(
            element_id=BOTTOM_FIRST_ID,
            band=ThemeElementBand.BOTTOM,
            sort_order=0,
            content_height=40,
        )
        placed_layout: ThemeLayout = place_theme_elements(
            THEME_FRAME_WIDTH_PIXELS,
            THEME_FRAME_HEIGHT_PIXELS,
            96,
            20,
            10,
            [upper_element, lowest_element],
        )
        expected_layout: ThemeLayout = ThemeLayout(
            content_area=ContentArea(x=96, y=96, width=888, height=888),
            rectangles=(
                LayoutRectangle(
                    element_id=BOTTOM_FIRST_ID,
                    x=96,
                    y=924,
                    width=888,
                    height=60,
                ),
                LayoutRectangle(
                    element_id=BOTTOM_SECOND_ID,
                    x=96,
                    y=824,
                    width=888,
                    height=80,
                ),
            ),
        )
        lowest_rectangle: LayoutRectangle = placed_layout.rectangles[0]
        upper_rectangle: LayoutRectangle = placed_layout.rectangles[1]
        lowest_bottom: int = lowest_rectangle.y + lowest_rectangle.height
        gap_between: int = lowest_rectangle.y - (upper_rectangle.y + upper_rectangle.height)

        self.assertEqual(placed_layout, expected_layout)
        self.assertEqual(lowest_bottom, THEME_FRAME_HEIGHT_PIXELS - 96)
        self.assertEqual(gap_between, 20)
        self._assert_layout_uses_ints(placed_layout)

    def test_three_middle_elements_are_centered_as_a_group(self) -> None:
        """The middle block is centered, and the odd leftover pixel goes below it.

        Heights 28, 38, and 49 plus two gaps of 10 make a block of 135.
        Content height 888 leaves 753 pixels. Floor division puts 376
        above the block and 377 below it, so the block top is 472.
        That is not the position that would center the first or last element.
        """

        middle_elements: list[LayoutElement] = [
            LayoutElement(
                element_id=MIDDLE_THIRD_ID,
                band=ThemeElementBand.MIDDLE,
                sort_order=2,
                content_height=41,
            ),
            LayoutElement(
                element_id=MIDDLE_FIRST_ID,
                band=ThemeElementBand.MIDDLE,
                sort_order=0,
                content_height=20,
            ),
            LayoutElement(
                element_id=MIDDLE_SECOND_ID,
                band=ThemeElementBand.MIDDLE,
                sort_order=1,
                content_height=30,
            ),
        ]
        placed_layout: ThemeLayout = place_theme_elements(
            THEME_FRAME_WIDTH_PIXELS,
            THEME_FRAME_HEIGHT_PIXELS,
            96,
            10,
            4,
            middle_elements,
        )
        expected_layout: ThemeLayout = ThemeLayout(
            content_area=ContentArea(x=96, y=96, width=888, height=888),
            rectangles=(
                LayoutRectangle(
                    element_id=MIDDLE_FIRST_ID,
                    x=96,
                    y=472,
                    width=888,
                    height=28,
                ),
                LayoutRectangle(
                    element_id=MIDDLE_SECOND_ID,
                    x=96,
                    y=510,
                    width=888,
                    height=38,
                ),
                LayoutRectangle(
                    element_id=MIDDLE_THIRD_ID,
                    x=96,
                    y=558,
                    width=888,
                    height=49,
                ),
            ),
        )
        content_area: ContentArea = placed_layout.content_area
        first_rectangle: LayoutRectangle = placed_layout.rectangles[0]
        last_rectangle: LayoutRectangle = placed_layout.rectangles[2]
        content_bottom: int = content_area.y + content_area.height
        block_bottom: int = last_rectangle.y + last_rectangle.height
        space_above: int = first_rectangle.y - content_area.y
        space_below: int = content_bottom - block_bottom
        content_center: int = content_area.y + (content_area.height // 2)
        first_only_y: int = content_center - (first_rectangle.height // 2)
        last_only_y: int = content_center - (last_rectangle.height // 2)

        self.assertEqual(placed_layout, expected_layout)
        self.assertEqual(space_above, 376)
        self.assertEqual(space_below, 377)
        self.assertNotEqual(first_rectangle.y, first_only_y)
        self.assertNotEqual(last_rectangle.y, last_only_y)
        self._assert_layout_uses_ints(placed_layout)

    def test_one_band_theme_places_only_that_band(self) -> None:
        """A middle-only theme still centers that band and adds no other rectangles."""

        middle_element: LayoutElement = LayoutElement(
            element_id=MIDDLE_FIRST_ID,
            band=ThemeElementBand.MIDDLE,
            sort_order=0,
            content_height=100,
        )
        placed_layout: ThemeLayout = place_theme_elements(
            THEME_FRAME_WIDTH_PIXELS,
            THEME_FRAME_HEIGHT_PIXELS,
            96,
            22,
            0,
            [middle_element],
        )
        expected_layout: ThemeLayout = ThemeLayout(
            content_area=ContentArea(x=96, y=96, width=888, height=888),
            rectangles=(
                LayoutRectangle(
                    element_id=MIDDLE_FIRST_ID,
                    x=96,
                    y=490,
                    width=888,
                    height=100,
                ),
            ),
        )

        self.assertEqual(placed_layout, expected_layout)
        self.assertEqual(len(placed_layout.rectangles), 1)
        self._assert_layout_uses_ints(placed_layout)

    def test_zero_elements_returns_no_rectangles(self) -> None:
        """Zero elements is valid. The content area is still the inset frame."""

        placed_layout: ThemeLayout = place_theme_elements(
            THEME_FRAME_WIDTH_PIXELS,
            THEME_FRAME_HEIGHT_PIXELS,
            100,
            12,
            8,
            [],
        )
        expected_layout: ThemeLayout = ThemeLayout(
            content_area=ContentArea(x=100, y=100, width=880, height=880),
            rectangles=(),
        )

        self.assertEqual(placed_layout, expected_layout)
        self._assert_layout_uses_ints(placed_layout)

    def test_bands_place_independently(self) -> None:
        """A tall top element does not push middle or bottom.

        The top rectangle runs from 96 to 796. Middle stays at the group
        center (490) instead of moving below that top. Bottom stays
        page-margin up from the frame bottom.
        """

        elements: list[LayoutElement] = [
            LayoutElement(
                element_id=BOTTOM_FIRST_ID,
                band=ThemeElementBand.BOTTOM,
                sort_order=0,
                content_height=50,
            ),
            LayoutElement(
                element_id=TOP_FIRST_ID,
                band=ThemeElementBand.TOP,
                sort_order=0,
                content_height=700,
            ),
            LayoutElement(
                element_id=MIDDLE_FIRST_ID,
                band=ThemeElementBand.MIDDLE,
                sort_order=0,
                content_height=100,
            ),
        ]
        placed_layout: ThemeLayout = place_theme_elements(
            THEME_FRAME_WIDTH_PIXELS,
            THEME_FRAME_HEIGHT_PIXELS,
            96,
            8,
            0,
            elements,
        )
        expected_layout: ThemeLayout = ThemeLayout(
            content_area=ContentArea(x=96, y=96, width=888, height=888),
            rectangles=(
                LayoutRectangle(
                    element_id=TOP_FIRST_ID,
                    x=96,
                    y=96,
                    width=888,
                    height=700,
                ),
                LayoutRectangle(
                    element_id=MIDDLE_FIRST_ID,
                    x=96,
                    y=490,
                    width=888,
                    height=100,
                ),
                LayoutRectangle(
                    element_id=BOTTOM_FIRST_ID,
                    x=96,
                    y=934,
                    width=888,
                    height=50,
                ),
            ),
        )

        self.assertEqual(placed_layout, expected_layout)
        self._assert_layout_uses_ints(placed_layout)

    def _assert_layout_uses_ints(self, placed_layout: ThemeLayout) -> None:
        """Rectangles and the content area are integers, not floats."""

        content_area: ContentArea = placed_layout.content_area

        self._assert_int(content_area.x)
        self._assert_int(content_area.y)
        self._assert_int(content_area.width)
        self._assert_int(content_area.height)

        for rectangle in placed_layout.rectangles:
            self._assert_int(rectangle.x)
            self._assert_int(rectangle.y)
            self._assert_int(rectangle.width)
            self._assert_int(rectangle.height)

    def _assert_int(self, pixel_value: int) -> None:
        """Reject bools and floats. ``bool`` is a subclass of ``int``."""

        self.assertIsInstance(pixel_value, int)
        self.assertNotIsInstance(pixel_value, bool)


if __name__ == "__main__":
    unittest.main()
