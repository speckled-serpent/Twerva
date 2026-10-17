"""Hidden skeleton slug derived from the operator-facing name."""

from __future__ import annotations

import re
import unicodedata


SLUG_FALLBACK: str = "skeleton"
NON_SLUG_CHARACTER_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")
REPEATED_HYPHEN_PATTERN: re.Pattern[str] = re.compile(r"-{2,}")


def slugify_skeleton_name(skeleton_name: str) -> str:
    """Turn a skeleton name into a lowercase hyphenated slug.

    Args:
        skeleton_name: Operator-facing name (for example ``Spotmu Paper``).

    Returns:
        A slug such as ``spotmu-paper``. Falls back to ``skeleton`` when
        the name has no letters or digits.
    """

    stripped_name: str = skeleton_name.strip()
    normalized_name: str = unicodedata.normalize("NFKD", stripped_name)
    ascii_name: str = normalized_name.encode("ascii", "ignore").decode("ascii")
    lowered_name: str = ascii_name.lower()
    hyphenated_name: str = NON_SLUG_CHARACTER_PATTERN.sub("-", lowered_name)
    collapsed_name: str = REPEATED_HYPHEN_PATTERN.sub("-", hyphenated_name)
    skeleton_slug: str = collapsed_name.strip("-")

    if skeleton_slug == "":

        return SLUG_FALLBACK

    return skeleton_slug


def allocate_unique_skeleton_slug(requested_slug: str, taken_slugs: set[str]) -> str:
    """Return ``requested_slug``, or ``requested-slug-2`` if taken.

    Args:
        requested_slug: Slug derived from the skeleton name.
        taken_slugs: Existing ``skeletons.slug`` values.

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
