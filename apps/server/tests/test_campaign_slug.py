"""Campaign name → slug / hashtag helpers."""

import unittest

from app.campaigns.slug import (
    allocate_unique_campaign_slug,
    hashtag_from_campaign_slug,
    slugify_campaign_name,
)


class CampaignSlugTests(unittest.TestCase):
    """Hidden slug and hashtag stay stable and unique."""

    def test_slugify_campaign_name_hyphenates_and_lowercases(self) -> None:
        """`My Campaign` becomes `my-campaign`."""

        campaign_slug: str = slugify_campaign_name("My Campaign")

        self.assertEqual(campaign_slug, "my-campaign")

    def test_slugify_campaign_name_strips_punctuation(self) -> None:
        """Punctuation collapses to a single hyphen."""

        campaign_slug: str = slugify_campaign_name("  Spring / Launch!!  ")

        self.assertEqual(campaign_slug, "spring-launch")

    def test_slugify_campaign_name_falls_back_when_empty(self) -> None:
        """Names without letters or digits become `campaign`."""

        campaign_slug: str = slugify_campaign_name("!!!")

        self.assertEqual(campaign_slug, "campaign")

    def test_hashtag_from_campaign_slug_prefixes_hash(self) -> None:
        """Stored hashtag is `#slug`."""

        campaign_hashtag: str = hashtag_from_campaign_slug("my-campaign")

        self.assertEqual(campaign_hashtag, "#my-campaign")

    def test_allocate_unique_campaign_slug_appends_suffix(self) -> None:
        """Taken slugs get `-2`, then `-3`."""

        taken_slugs: set[str] = {"my-campaign", "my-campaign-2"}
        allocated_slug: str = allocate_unique_campaign_slug(
            "my-campaign",
            taken_slugs,
        )

        self.assertEqual(allocated_slug, "my-campaign-3")


if __name__ == "__main__":
    unittest.main()
