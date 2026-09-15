"""Median helper for cluster view rollups (1.7b)."""


def calculate_median_of_numbers(values: list[int | float]) -> float | None:
    """Return the statistical median, or None when `values` is empty.

    Odd-length lists use the middle value after sorting. Even-length
    lists use the mean of the two central values (may be a half, e.g.
    2.5). Empty input is documented empty behavior for cluster summary:
    `median_views` is JSON `null`, not zero.

    Args:
        values: Unordered view (or other) counts. May be empty.

    Returns:
        Median as float, or None when there are no values.
    """

    value_count: int = len(values)

    if value_count == 0:
        return None

    sorted_values: list[float] = sorted(float(value) for value in values)
    middle_index: int = value_count // 2
    remainder: int = value_count % 2

    if remainder == 1:
        odd_median: float = sorted_values[middle_index]

        return odd_median

    lower_middle: float = sorted_values[middle_index - 1]
    upper_middle: float = sorted_values[middle_index]
    even_median: float = (lower_middle + upper_middle) / 2.0

    return even_median
