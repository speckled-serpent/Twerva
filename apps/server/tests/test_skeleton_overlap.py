"""Band overlap (1.10f-i). Coordinates stay where placement put them."""

import unittest
import uuid

from app.models.enums import SkeletonElementBand
from app.skeletons.layout import (
    SKELETON_FRAME_HEIGHT_PIXELS,
    SKELETON_FRAME_WIDTH_PIXELS,
    LayoutElement,
    SkeletonLayout,
    place_skeleton_elements,
)
from app.skeletons.overlap import (
    BandOverlap,
    InstanceOverlap,
    PlacedElement,
    find_band_overlaps,
)


TOP_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000301")
LATER_TOP_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000302")
MIDDLE_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000311")
BOTTOM_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000321")
CLEAR_TOP_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000331")
CLEAR_MIDDLE_ID: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000332")


class SkeletonOverlapTests(unittest.TestCase):
    """Different bands block on area intersection. Edges and same-band stacks do not."""

    def test_tall_top_intersecting_middle_is_blocked_without_moving(self) -> None:
        """A top element that runs through middle blocks that instance.

        Placement stays put: top at 96, middle centered at 910. Middle is
        not moved below the top.
        """

        elements: list[LayoutElement] = [
            LayoutElement(
                element_id=TOP_ID,
                band=SkeletonElementBand.TOP,
                sort_order=0,
                content_height=900,
            ),
            LayoutElement(
                element_id=MIDDLE_ID,
                band=SkeletonElementBand.MIDDLE,
                sort_order=0,
                content_height=100,
            ),
            LayoutElement(
                element_id=BOTTOM_ID,
                band=SkeletonElementBand.BOTTOM,
                sort_order=0,
                content_height=50,
            ),
        ]
        placed_layout: SkeletonLayout = place_skeleton_elements(
            SKELETON_FRAME_WIDTH_PIXELS,
            SKELETON_FRAME_HEIGHT_PIXELS,
            96,
            8,
            0,
            elements,
        )
        placed_elements: tuple[PlacedElement, ...] = _placed_from_layout(
            elements,
            placed_layout,
        )
        top_y_before: int = _element_y(placed_elements, TOP_ID)
        middle_y_before: int = _element_y(placed_elements, MIDDLE_ID)
        bottom_y_before: int = _element_y(placed_elements, BOTTOM_ID)
        overlap_results: tuple[InstanceOverlap, ...] = find_band_overlaps(
            (placed_elements,),
        )
        instance_overlap: InstanceOverlap = overlap_results[0]
        expected_overlap: BandOverlap = BandOverlap(
            band_a=SkeletonElementBand.TOP,
            band_b=SkeletonElementBand.MIDDLE,
            element_ids=(TOP_ID, MIDDLE_ID),
        )

        self.assertEqual(len(overlap_results), 1)
        self.assertTrue(instance_overlap.blocked)
        self.assertEqual(instance_overlap.overlaps, (expected_overlap,))
        self.assertEqual(_element_y(placed_elements, TOP_ID), top_y_before)
        self.assertEqual(_element_y(placed_elements, MIDDLE_ID), middle_y_before)
        self.assertEqual(_element_y(placed_elements, BOTTOM_ID), bottom_y_before)
        self.assertEqual(top_y_before, 96)
        self.assertEqual(middle_y_before, 910)
        self.assertEqual(bottom_y_before, 1774)

    def test_edge_touching_pair_is_allowed(self) -> None:
        """Sharing the edge between top and middle is not an overlap."""

        top_element: PlacedElement = PlacedElement(
            element_id=TOP_ID,
            band=SkeletonElementBand.TOP,
            x=96,
            y=96,
            width=888,
            height=394,
        )
        middle_element: PlacedElement = PlacedElement(
            element_id=MIDDLE_ID,
            band=SkeletonElementBand.MIDDLE,
            x=96,
            y=490,
            width=888,
            height=100,
        )
        overlap_results: tuple[InstanceOverlap, ...] = find_band_overlaps(
            ((top_element, middle_element),),
        )

        self.assertEqual(top_element.y + top_element.height, middle_element.y)
        self.assertFalse(overlap_results[0].blocked)
        self.assertEqual(overlap_results[0].overlaps, ())

    def test_two_instances_flag_only_the_colliding_one(self) -> None:
        """The clear instance stays open when the other frame collides."""

        colliding_inputs: list[LayoutElement] = [
            LayoutElement(
                element_id=TOP_ID,
                band=SkeletonElementBand.TOP,
                sort_order=0,
                content_height=900,
            ),
            LayoutElement(
                element_id=MIDDLE_ID,
                band=SkeletonElementBand.MIDDLE,
                sort_order=0,
                content_height=100,
            ),
        ]
        clear_inputs: list[LayoutElement] = [
            LayoutElement(
                element_id=CLEAR_TOP_ID,
                band=SkeletonElementBand.TOP,
                sort_order=0,
                content_height=40,
            ),
            LayoutElement(
                element_id=CLEAR_MIDDLE_ID,
                band=SkeletonElementBand.MIDDLE,
                sort_order=0,
                content_height=40,
            ),
        ]
        colliding_elements: tuple[PlacedElement, ...] = _place(colliding_inputs)
        clear_elements: tuple[PlacedElement, ...] = _place(clear_inputs)
        overlap_results: tuple[InstanceOverlap, ...] = find_band_overlaps(
            (colliding_elements, clear_elements),
        )

        self.assertEqual(len(overlap_results), 2)
        self.assertTrue(overlap_results[0].blocked)
        self.assertEqual(
            overlap_results[0].overlaps[0].element_ids,
            (TOP_ID, MIDDLE_ID),
        )
        self.assertFalse(overlap_results[1].blocked)
        self.assertEqual(overlap_results[1].overlaps, ())

    def test_same_band_stack_with_gap_is_not_an_overlap(self) -> None:
        """Gap zero and a positive gap inside one band stay unblocked."""

        touching_stack: tuple[PlacedElement, ...] = (
            PlacedElement(
                element_id=TOP_ID,
                band=SkeletonElementBand.TOP,
                x=96,
                y=96,
                width=888,
                height=100,
            ),
            PlacedElement(
                element_id=LATER_TOP_ID,
                band=SkeletonElementBand.TOP,
                x=96,
                y=196,
                width=888,
                height=80,
            ),
        )
        gapped_stack: tuple[PlacedElement, ...] = (
            touching_stack[0],
            PlacedElement(
                element_id=LATER_TOP_ID,
                band=SkeletonElementBand.TOP,
                x=96,
                y=208,
                width=888,
                height=80,
            ),
        )
        overlap_results: tuple[InstanceOverlap, ...] = find_band_overlaps(
            (touching_stack, gapped_stack),
        )

        self.assertFalse(overlap_results[0].blocked)
        self.assertEqual(overlap_results[0].overlaps, ())
        self.assertFalse(overlap_results[1].blocked)
        self.assertEqual(overlap_results[1].overlaps, ())

    def test_zero_elements_is_not_blocked(self) -> None:
        """An empty frame is a valid instance."""

        overlap_results: tuple[InstanceOverlap, ...] = find_band_overlaps(((),))

        self.assertEqual(
            overlap_results,
            (InstanceOverlap(blocked=False, overlaps=()),),
        )


def _placed_from_layout(
    elements: list[LayoutElement],
    placed_layout: SkeletonLayout,
) -> tuple[PlacedElement, ...]:
    """Copy placement onto band-tagged rectangles. The layout is not edited."""

    band_by_id: dict[uuid.UUID, SkeletonElementBand] = {
        element.element_id: element.band
        for element in elements
    }
    placed_elements: list[PlacedElement] = []

    for rectangle in placed_layout.rectangles:
        placed_element: PlacedElement = PlacedElement(
            element_id=rectangle.element_id,
            band=band_by_id[rectangle.element_id],
            x=rectangle.x,
            y=rectangle.y,
            width=rectangle.width,
            height=rectangle.height,
        )
        placed_elements.append(placed_element)

    return tuple(placed_elements)


def _place(elements: list[LayoutElement]) -> tuple[PlacedElement, ...]:
    """Place one frame and tag each rectangle with its band."""

    placed_layout: SkeletonLayout = place_skeleton_elements(
        SKELETON_FRAME_WIDTH_PIXELS,
        SKELETON_FRAME_HEIGHT_PIXELS,
        96,
        0,
        0,
        elements,
    )

    return _placed_from_layout(elements, placed_layout)


def _element_y(placed_elements: tuple[PlacedElement, ...], element_id: uuid.UUID) -> int:
    """Return the placed ``y`` for ``element_id``."""

    for placed_element in placed_elements:

        if placed_element.element_id == element_id:

            return placed_element.y

    raise AssertionError(f"missing element {element_id}")


if __name__ == "__main__":
    unittest.main()
