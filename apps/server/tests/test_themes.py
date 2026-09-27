"""Theme create validation and list serialization without Postgres."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.themes import (
    THEME_NAME_REQUIRED_DETAIL,
    create_theme,
    get_theme_by_id,
    list_themes,
)
from app.api.v1.schemas import ThemeCreateRequest, ThemeReadResponse
from app.models.enums import AdvertisementType
from app.models.theme import Theme
from app.themes.slug import allocate_unique_theme_slug, slugify_theme_name


class ThemeCreateValidationTests(unittest.TestCase):
    """Create rejects a blank name and an unknown template before any write."""

    def test_empty_name_fails_schema_validation(self) -> None:
        """A zero-length name never reaches the handler."""

        with self.assertRaises(ValidationError):
            ThemeCreateRequest(name="")

    def test_blank_theme_name_is_rejected(self) -> None:
        """Whitespace-only name returns HTTP 400 and does not persist."""

        fake_session: MagicMock = MagicMock()
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(name="   ")

        with self.assertRaises(HTTPException) as raised_http:
            create_theme(theme_create_request, fake_session, None)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, THEME_NAME_REQUIRED_DETAIL)
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()

    def test_unknown_template_key_is_rejected(self) -> None:
        """A template id outside the carousel registry returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(
            name="Night Shift",
            template_key="not_a_template",
        )

        with self.assertRaises(HTTPException) as raised_http:
            create_theme(theme_create_request, fake_session, None)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertIn("Unknown carousel template", str(raised_http.exception.detail))
        fake_session.add.assert_not_called()

    def test_create_defaults_to_carousel_without_template(self) -> None:
        """A named theme persists carousel, a slug, and a null template key."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(name="  Harbor  ")
        operator_id: uuid.UUID = uuid.uuid4()
        current_ops_operator: MagicMock = MagicMock()
        current_ops_operator.id = operator_id
        fake_session.refresh.side_effect = _assign_persisted_timestamps

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            theme_read_response: ThemeReadResponse = create_theme(
                theme_create_request,
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(theme_read_response.name, "Harbor")
        self.assertEqual(theme_read_response.slug, "harbor")
        self.assertEqual(
            theme_read_response.advertisement_type,
            AdvertisementType.CAROUSEL,
        )
        self.assertIsNone(theme_read_response.template_key)
        self.assertEqual(theme_read_response.created_by, operator_id)
        fake_session.add.assert_called_once()

    def test_blank_template_key_is_stored_as_null(self) -> None:
        """Whitespace template_key is treated as omitted."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(
            name="Harbor",
            template_key="   ",
        )
        fake_session.refresh.side_effect = _assign_persisted_timestamps

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            theme_read_response: ThemeReadResponse = create_theme(
                theme_create_request,
                fake_session,
                None,
            )

        self.assertIsNone(theme_read_response.template_key)
        added_theme: Theme = fake_session.add.call_args.args[0]
        self.assertIsNone(added_theme.template_key)

    def test_known_template_key_is_stored(self) -> None:
        """spotmu_bold_v1 is accepted and returned on the read model."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = ["harbor"]
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(
            name="Harbor",
            template_key="spotmu_bold_v1",
        )
        fake_session.refresh.side_effect = _assign_persisted_timestamps

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            theme_read_response: ThemeReadResponse = create_theme(
                theme_create_request,
                fake_session,
                None,
            )

        self.assertEqual(theme_read_response.slug, "harbor-2")
        self.assertEqual(theme_read_response.template_key, "spotmu_bold_v1")

    def test_missing_theme_returns_404(self) -> None:
        """GET by id raises HTTP 404 when the row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_theme_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            get_theme_by_id(missing_theme_id, fake_session)

        self.assertEqual(raised_http.exception.status_code, 404)


class ThemeListTests(unittest.TestCase):
    """List returns the rows the query produced, newest-query order kept."""

    def test_list_themes_serializes_query_rows(self) -> None:
        """GET list maps name, advertisement type, and template key."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        bold_theme: Theme = _theme_row(
            name="Spotmu Bold v1",
            slug="spotmu-bold-v1",
            template_key="spotmu_bold_v1",
            created_at=created_at,
        )
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = [bold_theme, paper_theme]

        listed_themes: list[ThemeReadResponse] = list_themes(fake_session)

        self.assertEqual(
            [theme.name for theme in listed_themes],
            ["Spotmu Bold v1", "Spotmu Paper v1"],
        )
        self.assertEqual(
            listed_themes[0].advertisement_type,
            AdvertisementType.CAROUSEL,
        )
        self.assertEqual(listed_themes[0].template_key, "spotmu_bold_v1")
        self.assertEqual(listed_themes[1].template_key, "spotmu_paper_v1")
        self.assertEqual(len(listed_themes), 2)


class ThemeSlugTests(unittest.TestCase):
    """Slug derivation matches the campaign hyphen rules with a theme fallback."""

    def test_slugify_theme_name(self) -> None:
        """Spaces and punctuation become a single hyphenated slug."""

        theme_slug: str = slugify_theme_name("  Spotmu Paper v1! ")

        self.assertEqual(theme_slug, "spotmu-paper-v1")

    def test_slugify_falls_back_when_name_has_no_letters(self) -> None:
        """Punctuation-only names use the theme fallback slug."""

        theme_slug: str = slugify_theme_name("!!!")

        self.assertEqual(theme_slug, "theme")

    def test_allocate_unique_theme_slug_appends_suffix(self) -> None:
        """A taken slug gets -2."""

        allocated_slug: str = allocate_unique_theme_slug(
            "harbor",
            {"harbor"},
        )

        self.assertEqual(allocated_slug, "harbor-2")


def _assign_persisted_timestamps(theme: Theme) -> None:
    """Fill server-default columns the handler reads after refresh."""

    persisted_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    theme.id = uuid.uuid4()
    theme.created_at = persisted_at
    theme.updated_at = persisted_at


def _theme_row(
    name: str,
    slug: str,
    template_key: str | None,
    created_at: datetime,
) -> Theme:
    """Build an in-memory Theme for list serialization."""

    theme: Theme = Theme(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        advertisement_type=AdvertisementType.CAROUSEL,
        template_key=template_key,
        created_by=None,
        created_at=created_at,
        updated_at=created_at,
    )

    return theme
