"""Global slide-count default. It is not a skeleton column."""

import os
import random
import unittest

os.environ.setdefault("TWERVA_ENV", "test")

from app.global_settings import (
    SLIDE_COUNT_DEFAULT_HIGH,
    SLIDE_COUNT_DEFAULT_LOW,
    slide_count_or_global_default,
)
from app.models.skeleton import Skeleton


class _FixedPicker(random.Random):
    """Returns one prepared integer and records the requested bounds."""

    def __init__(self, value: int) -> None:
        super().__init__(0)
        self.value: int = value
        self.bounds: tuple[int, int] | None = None

    def randint(self, low: int, high: int) -> int:
        self.bounds = (low, high)

        return self.value


class GlobalSlideCountDefaultTests(unittest.TestCase):
    """The built-in count is a random 5–8 only when nothing else is set."""

    def test_bounds_are_five_through_eight(self) -> None:
        """The global default is the inclusive range 5 to 8."""

        self.assertEqual(SLIDE_COUNT_DEFAULT_LOW, 5)
        self.assertEqual(SLIDE_COUNT_DEFAULT_HIGH, 8)

    def test_unset_count_draws_inside_the_global_range(self) -> None:
        """A missing count asks the picker for a value from 5 to 8."""

        low_picker: _FixedPicker = _FixedPicker(5)
        high_picker: _FixedPicker = _FixedPicker(8)

        self.assertEqual(slide_count_or_global_default(None, low_picker), 5)
        self.assertEqual(low_picker.bounds, (5, 8))
        self.assertEqual(slide_count_or_global_default(None, high_picker), 8)
        self.assertEqual(high_picker.bounds, (5, 8))

    def test_seeded_draws_stay_inside_the_global_range(self) -> None:
        """Repeated draws without an explicit count stay in 5 to 8."""

        seeded_picker: random.Random = random.Random(15)
        chosen_counts: list[int] = [
            slide_count_or_global_default(None, seeded_picker)
            for _draw in range(40)
        ]

        self.assertEqual(len(chosen_counts), 40)

        for chosen_count in chosen_counts:
            self.assertGreaterEqual(chosen_count, SLIDE_COUNT_DEFAULT_LOW)
            self.assertLessEqual(chosen_count, SLIDE_COUNT_DEFAULT_HIGH)

    def test_a_set_count_is_kept(self) -> None:
        """Two, four, and nine stay as set. The default does not replace them."""

        picker: _FixedPicker = _FixedPicker(8)

        self.assertEqual(slide_count_or_global_default(2, picker), 2)
        self.assertEqual(slide_count_or_global_default(4, picker), 4)
        self.assertEqual(slide_count_or_global_default(9, picker), 9)
        self.assertIsNone(picker.bounds)

    def test_skeleton_has_no_slide_count_column(self) -> None:
        """Per-skeleton overrides are later, so the skeleton gains no column."""

        column_names: set[str] = set(Skeleton.__table__.columns.keys())

        self.assertNotIn("slide_count", column_names)
        self.assertNotIn("slide_count_default", column_names)
        self.assertNotIn("default_slide_count", column_names)


if __name__ == "__main__":
    unittest.main()
