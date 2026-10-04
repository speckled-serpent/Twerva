"""Theme text sources (1.10e-i). No wrap and no HTTP."""

import unittest
import uuid

from app.models.enums import SourceType, ThemeElementTextSource
from app.models.source_item import SourceItem
from app.themes.sources import resolve_theme_text


class ThemeTextSourceTests(unittest.TestCase):
    """One Spotmu source item resolves to one string per text source."""

    def test_maps_a_fake_spotmu_source_item(self) -> None:
        """Title, heading, three bullets as one block, and the public URL.

        Empty and whitespace-only bullets are omitted. A null heading
        and a null URL resolve to blank strings.
        """

        source_item: SourceItem = _fake_spotmu_source_item(
            title="Example Spotmu interest",
            interest_heading="What this example lane is about",
            overview_bullets=["one", "", "  ", "two", "three"],
            canonical_url="https://spotmu.com/interest/example",
        )
        title_text: str = resolve_theme_text(
            source_item,
            ThemeElementTextSource.TITLE,
        )
        heading_text: str = resolve_theme_text(
            source_item,
            ThemeElementTextSource.INTEREST_HEADING,
        )
        bullet_block: str = resolve_theme_text(
            source_item,
            ThemeElementTextSource.OVERVIEW_BULLETS,
        )
        url_text: str = resolve_theme_text(
            source_item,
            ThemeElementTextSource.CANONICAL_URL,
        )
        blank_source_item: SourceItem = _fake_spotmu_source_item(
            title="Heading missing",
            interest_heading=None,
            overview_bullets=[],
            canonical_url=None,
        )
        blank_heading: str = resolve_theme_text(
            blank_source_item,
            ThemeElementTextSource.INTEREST_HEADING,
        )
        blank_url: str = resolve_theme_text(
            blank_source_item,
            ThemeElementTextSource.CANONICAL_URL,
        )
        empty_bullets: str = resolve_theme_text(
            blank_source_item,
            ThemeElementTextSource.OVERVIEW_BULLETS,
        )

        self.assertEqual(source_item.source_type, SourceType.SPOTMU_INTEREST)
        self.assertEqual(title_text, "Example Spotmu interest")
        self.assertEqual(heading_text, "What this example lane is about")
        self.assertIsInstance(bullet_block, str)
        self.assertEqual(bullet_block, "one\ntwo\nthree")
        self.assertEqual(bullet_block.count("\n"), 2)
        self.assertEqual(url_text, "https://spotmu.com/interest/example")
        self.assertEqual(blank_heading, "")
        self.assertEqual(blank_url, "")
        self.assertEqual(empty_bullets, "")

    def test_disallowed_key_never_appears_in_the_enum(self) -> None:
        """The text-source enum is only the four Spotmu fields."""

        source_values: set[str] = {
            member.value for member in ThemeElementTextSource
        }

        self.assertEqual(
            source_values,
            {"title", "interest_heading", "overview_bullets", "canonical_url"},
        )
        self.assertNotIn("caption", source_values)
        self.assertNotIn("body", source_values)
        self.assertNotIn("external_key", source_values)


def _fake_spotmu_source_item(
    title: str,
    interest_heading: str | None,
    overview_bullets: list[str],
    canonical_url: str | None,
) -> SourceItem:
    """Build an in-memory Spotmu source item. Nothing is written."""

    source_item: SourceItem = SourceItem(
        brand_id=uuid.uuid4(),
        source_type=SourceType.SPOTMU_INTEREST,
        external_key="example",
        title=title,
        interest_heading=interest_heading,
        overview_bullets=overview_bullets,
        canonical_url=canonical_url,
    )

    return source_item


if __name__ == "__main__":
    unittest.main()
