"""Resolve one theme text element from a Spotmu source item.

Reads ``title``, ``interest_heading``, ``overview_bullets``, or
``canonical_url``. Overview bullets become one block, not one frame
per bullet. This module does not wrap text or call HTTP.
"""

from __future__ import annotations

from typing import assert_never

from app.models.enums import ThemeElementTextSource
from app.models.source_item import SourceItem


def resolve_theme_text(
    source_item: SourceItem,
    text_source: ThemeElementTextSource,
) -> str:
    """Return the text for one theme element.

    ``interest_heading`` and ``canonical_url`` are blank when null.
    ``overview_bullets`` is the non-empty strings joined with newlines
    into one block. No other source key is read.

    Args:
        source_item: Spotmu interest row (or the same four columns).
        text_source: Which of the four Spotmu fields this element uses.

    Returns:
        The resolved string. Missing heading, URL, or bullets are ``""``.
    """

    if text_source == ThemeElementTextSource.TITLE:

        title_text: str = source_item.title

        return title_text

    if text_source == ThemeElementTextSource.INTEREST_HEADING:

        heading_text: str = _blank_when_null(source_item.interest_heading)

        return heading_text

    if text_source == ThemeElementTextSource.OVERVIEW_BULLETS:

        bullet_block: str = _overview_bullets_block(source_item.overview_bullets)

        return bullet_block

    if text_source == ThemeElementTextSource.CANONICAL_URL:

        url_text: str = _blank_when_null(source_item.canonical_url)

        return url_text

    assert_never(text_source)


def _blank_when_null(field_value: str | None) -> str:
    """Return ``field_value``, or a blank string when it is null."""

    if field_value is None:

        return ""

    return field_value


def _overview_bullets_block(overview_bullets: list[str] | None) -> str:
    """Join non-empty bullets with newlines. Blank lines are omitted.

    Args:
        overview_bullets: Stored bullet strings, or null.

    Returns:
        One block. Empty when there are no non-empty bullets.
    """

    if overview_bullets is None:

        return ""

    bullet_lines: list[str] = []

    for raw_bullet in overview_bullets:
        stripped_bullet: str = raw_bullet.strip()

        if stripped_bullet == "":

            continue

        bullet_lines.append(stripped_bullet)

    joined_block: str = "\n".join(bullet_lines)

    return joined_block
