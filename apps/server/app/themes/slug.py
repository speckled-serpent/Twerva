"""Hidden theme slug derived from the operator-facing name."""

from __future__ import annotations

import re
import unicodedata


SLUG_FALLBACK: str = "theme"
NON_SLUG_CHARACTER_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")
REPEATED_HYPHEN_PATTERN: re.Pattern[str] = re.compile(r"-{2,}")


def slugify_theme_name(theme_name: str) -> str:
    """Turn a theme name into a lowercase hyphenated slug.

    Args:
        theme_name: Operator-facing name (for example ``Spotmu Paper``).

    Returns:
        A slug such as ``spotmu-paper``. Falls back to ``theme`` when
        the name has no letters or digits.
    """

    stripped_name: str = theme_name.strip()
    normalized_name: str = unicodedata.normalize("NFKD", stripped_name)
    ascii_name: str = normalized_name.encode("ascii", "ignore").decode("ascii")
    lowered_name: str = ascii_name.lower()
    hyphenated_name: str = NON_SLUG_CHARACTER_PATTERN.sub("-", lowered_name)
    collapsed_name: str = REPEATED_HYPHEN_PATTERN.sub("-", hyphenated_name)
    theme_slug: str = collapsed_name.strip("-")

    if theme_slug == "":

        return SLUG_FALLBACK

    return theme_slug


def allocate_unique_theme_slug(requested_slug: str, taken_slugs: set[str]) -> str:
    """Return ``requested_slug``, or ``requested-slug-2`` if taken.

    Args:
        requested_slug: Slug derived from the theme name.
        taken_slugs: Existing ``themes.slug`` values.

    Returns:
        A slug that is not in ``taken_slugs``.
    """

    if requested_slug not in taken_slugs:

        return requested_slug

    suffix_number: int = 2

    while True:
        candidate_slug: str = f"{requested_slug}-{suffix_number}"

        if candidate_slug not in taken_slugs:

            return candidate_slug

        suffix_number += 1
