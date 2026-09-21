"""Hidden campaign slug / hashtag derived from the operator-facing name."""

from __future__ import annotations

import re
import unicodedata


SLUG_FALLBACK: str = "campaign"
NON_SLUG_CHARACTER_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")
REPEATED_HYPHEN_PATTERN: re.Pattern[str] = re.compile(r"-{2,}")


def slugify_campaign_name(campaign_name: str) -> str:
    """Turn a campaign name into a lowercase hyphenated slug.

    Args:
        campaign_name: Operator-facing name (for example ``My Campaign``).

    Returns:
        A slug such as ``my-campaign``. Falls back to ``campaign`` when
        the name has no letters or digits.
    """

    stripped_name: str = campaign_name.strip()
    normalized_name: str = unicodedata.normalize("NFKD", stripped_name)
    ascii_name: str = normalized_name.encode("ascii", "ignore").decode("ascii")
    lowered_name: str = ascii_name.lower()
    hyphenated_name: str = NON_SLUG_CHARACTER_PATTERN.sub("-", lowered_name)
    collapsed_name: str = REPEATED_HYPHEN_PATTERN.sub("-", hyphenated_name)
    campaign_slug: str = collapsed_name.strip("-")

    if campaign_slug == "":

        return SLUG_FALLBACK

    return campaign_slug


def hashtag_from_campaign_slug(campaign_slug: str) -> str:
    """Return the stored internal hashtag for a slug.

    Args:
        campaign_slug: Slug such as ``my-campaign``.

    Returns:
        ``#my-campaign``.
    """

    stripped_slug: str = campaign_slug.strip().lstrip("#")
    campaign_hashtag: str = f"#{stripped_slug}"

    return campaign_hashtag


def allocate_unique_campaign_slug(
    requested_slug: str,
    taken_slugs: set[str],
) -> str:
    """Return ``requested_slug``, or ``requested-slug-2`` if taken.

    Args:
        requested_slug: Slug derived from the campaign name.
        taken_slugs: Existing ``campaigns.slug`` values.

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
