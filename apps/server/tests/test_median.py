"""Median helper (1.7b-ii) — no Postgres required."""

import unittest

from app.metrics.median import calculate_median_of_numbers


class MedianHelperTests(unittest.TestCase):
    """1.7b-ii: empty, odd, even, unsorted, and single-value cases."""

    def test_empty_list_returns_none(self) -> None:
        """Empty cluster / no views snapshots → JSON null, not zero."""

        empty_median: float | None = calculate_median_of_numbers([])

        self.assertIsNone(empty_median)

    def test_single_value_is_the_median(self) -> None:
        """One views count is returned as float."""

        single_median: float | None = calculate_median_of_numbers([7])

        self.assertEqual(single_median, 7.0)

    def test_odd_count_uses_middle_after_sort(self) -> None:
        """Unsorted odd list uses the middle sorted value."""

        odd_median: float | None = calculate_median_of_numbers([30, 10, 20])

        self.assertEqual(odd_median, 20.0)

    def test_even_count_averages_the_two_central_values(self) -> None:
        """Even length uses the mean of the two middle sorted values."""

        even_median: float | None = calculate_median_of_numbers([10, 30])

        self.assertEqual(even_median, 20.0)

    def test_even_count_can_produce_a_half(self) -> None:
        """Integer views can still yield a .5 median."""

        half_median: float | None = calculate_median_of_numbers([1, 2])

        self.assertEqual(half_median, 1.5)

    def test_does_not_mutate_the_input_list(self) -> None:
        """Caller list stays in original order."""

        original_values: list[int | float] = [9, 1, 5]
        calculated_median: float | None = calculate_median_of_numbers(original_values)

        self.assertEqual(calculated_median, 5.0)
        self.assertEqual(original_values, [9, 1, 5])


if __name__ == "__main__":
    unittest.main()
