"""Theme create validation and list serialization without Postgres."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.themes import (
    THEME_NAME_REQUIRED_DETAIL,
    THEME_STATUS_REQUIRED_DETAIL,
    create_theme,
    get_theme_by_id,
    list_themes,
    patch_theme_by_id,
    theme_spacing_negative_detail,
    theme_spacing_required_detail,
)
from app.api.v1.schemas import ThemeCreateRequest, ThemePatchRequest, ThemeReadResponse
from app.models.enums import AdvertisementType, ThemeStatus
from app.models.theme import (
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
    Theme,
)
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
        self.assertEqual(theme_read_response.status, ThemeStatus.DRAFT)
        self.assertEqual(theme_read_response.page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(theme_read_response.element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(theme_read_response.element_margin, DEFAULT_ELEMENT_MARGIN)
        self.assertEqual(theme_read_response.created_by, operator_id)
        added_theme: Theme = fake_session.add.call_args.args[0]
        self.assertEqual(added_theme.status, ThemeStatus.DRAFT)
        self.assertEqual(added_theme.page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(added_theme.element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(added_theme.element_margin, DEFAULT_ELEMENT_MARGIN)
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
        self.assertEqual(listed_themes[0].status, ThemeStatus.DRAFT)
        self.assertEqual(listed_themes[1].status, ThemeStatus.DRAFT)
        self.assertEqual(listed_themes[0].page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(listed_themes[0].element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(listed_themes[0].element_margin, DEFAULT_ELEMENT_MARGIN)
        self.assertEqual(listed_themes[1].page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(len(listed_themes), 2)


class ThemeStatusPatchTests(unittest.TestCase):
    """PATCH status round-trips; create ignores a status body."""

    def test_patch_live_then_draft_and_create_by_name_stays_draft(self) -> None:
        """One theme goes live and back to draft; GET returns each value.

        A name-only create, including a body that asks for live, still
        stores draft.
        """

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        current_ops_operator: MagicMock = MagicMock()

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            live_response: ThemeReadResponse = patch_theme_by_id(
                paper_theme.id,
                ThemePatchRequest(status=ThemeStatus.LIVE),
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(live_response.status, ThemeStatus.LIVE)
        self.assertEqual(paper_theme.status, ThemeStatus.LIVE)
        loaded_live: ThemeReadResponse = get_theme_by_id(paper_theme.id, fake_session)
        self.assertEqual(loaded_live.status, ThemeStatus.LIVE)
        self.assertEqual(loaded_live.name, "Spotmu Paper v1")

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            draft_response: ThemeReadResponse = patch_theme_by_id(
                paper_theme.id,
                ThemePatchRequest(status=ThemeStatus.DRAFT),
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(draft_response.status, ThemeStatus.DRAFT)
        loaded_draft: ThemeReadResponse = get_theme_by_id(paper_theme.id, fake_session)
        self.assertEqual(loaded_draft.status, ThemeStatus.DRAFT)

        create_session: MagicMock = MagicMock()
        create_session.scalars.return_value.all.return_value = []
        create_session.refresh.side_effect = _assign_persisted_timestamps
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest.model_validate(
            {"name": "Harbor", "status": "live"},
        )

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            created_theme: ThemeReadResponse = create_theme(
                theme_create_request,
                create_session,
                None,
            )

        self.assertEqual(created_theme.status, ThemeStatus.DRAFT)
        self.assertEqual(created_theme.name, "Harbor")
        stored_theme: Theme = create_session.add.call_args.args[0]
        self.assertEqual(stored_theme.status, ThemeStatus.DRAFT)
        self.assertNotIn("status", ThemeCreateRequest.model_fields)

    def test_patch_without_status_leaves_the_row_unchanged(self) -> None:
        """An empty partial body does not clear draft."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        bold_theme: Theme = _theme_row(
            name="Spotmu Bold v1",
            slug="spotmu-bold-v1",
            template_key="spotmu_bold_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = bold_theme

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            patched_theme: ThemeReadResponse = patch_theme_by_id(
                bold_theme.id,
                ThemePatchRequest(),
                fake_session,
                None,
            )

        self.assertEqual(patched_theme.status, ThemeStatus.DRAFT)
        self.assertEqual(bold_theme.status, ThemeStatus.DRAFT)

    def test_null_status_is_rejected(self) -> None:
        """An explicit null status is HTTP 400 and does not write."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        theme_patch_request: ThemePatchRequest = ThemePatchRequest.model_validate(
            {"status": None},
        )

        with self.assertRaises(HTTPException) as raised_http:
            patch_theme_by_id(
                paper_theme.id,
                theme_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, THEME_STATUS_REQUIRED_DETAIL)
        self.assertEqual(paper_theme.status, ThemeStatus.DRAFT)
        fake_session.commit.assert_not_called()

    def test_unknown_status_fails_schema_validation(self) -> None:
        """A status outside draft/live never reaches the handler."""

        with self.assertRaises(ValidationError):
            ThemePatchRequest.model_validate({"status": "published"})

    def test_missing_theme_patch_returns_404(self) -> None:
        """PATCH by id raises HTTP 404 when the row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_theme_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            patch_theme_by_id(
                missing_theme_id,
                ThemePatchRequest(status=ThemeStatus.LIVE),
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 404)


class ThemeSpacingPatchTests(unittest.TestCase):
    """PATCH spacing round-trips; create stores 96 / 0 / 0; negatives are 400."""

    def test_round_trip_rejects_negative_and_create_reads_defaults(self) -> None:
        """A non-default triple survives GET; -1 is 400; name-only create is 96 / 0 / 0."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        current_ops_operator: MagicMock = MagicMock()
        spacing_patch: ThemePatchRequest = ThemePatchRequest(
            page_margin=120,
            element_gap=16,
            element_margin=8,
        )

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            patched_theme: ThemeReadResponse = patch_theme_by_id(
                paper_theme.id,
                spacing_patch,
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(patched_theme.page_margin, 120)
        self.assertEqual(patched_theme.element_gap, 16)
        self.assertEqual(patched_theme.element_margin, 8)
        loaded_theme: ThemeReadResponse = get_theme_by_id(paper_theme.id, fake_session)
        self.assertEqual(loaded_theme.page_margin, 120)
        self.assertEqual(loaded_theme.element_gap, 16)
        self.assertEqual(loaded_theme.element_margin, 8)
        self.assertEqual(loaded_theme.status, ThemeStatus.DRAFT)

        self._assert_negative_spacing_is_rejected(
            paper_theme,
            fake_session,
            ThemePatchRequest(page_margin=-1),
            "page_margin",
        )
        self._assert_negative_spacing_is_rejected(
            paper_theme,
            fake_session,
            ThemePatchRequest(element_gap=-1),
            "element_gap",
        )
        self._assert_negative_spacing_is_rejected(
            paper_theme,
            fake_session,
            ThemePatchRequest(element_margin=-1),
            "element_margin",
        )
        self.assertEqual(paper_theme.page_margin, 120)
        self.assertEqual(paper_theme.element_gap, 16)
        self.assertEqual(paper_theme.element_margin, 8)

        create_session: MagicMock = MagicMock()
        create_session.scalars.return_value.all.return_value = []
        create_session.refresh.side_effect = _assign_persisted_timestamps
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(name="Harbor")

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            created_theme: ThemeReadResponse = create_theme(
                theme_create_request,
                create_session,
                None,
            )

        self.assertEqual(created_theme.name, "Harbor")
        self.assertEqual(created_theme.page_margin, 96)
        self.assertEqual(created_theme.element_gap, 0)
        self.assertEqual(created_theme.element_margin, 0)
        self.assertEqual(created_theme.page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(created_theme.element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(created_theme.element_margin, DEFAULT_ELEMENT_MARGIN)

        ignored_spacing_request: ThemeCreateRequest = ThemeCreateRequest.model_validate(
            {
                "name": "Night Shift",
                "page_margin": -1,
                "element_gap": 4,
                "element_margin": 4,
            },
        )
        ignored_session: MagicMock = MagicMock()
        ignored_session.scalars.return_value.all.return_value = ["harbor"]
        ignored_session.refresh.side_effect = _assign_persisted_timestamps

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            ignored_spacing_theme: ThemeReadResponse = create_theme(
                ignored_spacing_request,
                ignored_session,
                None,
            )

        self.assertEqual(ignored_spacing_theme.page_margin, 96)
        self.assertEqual(ignored_spacing_theme.element_gap, 0)
        self.assertEqual(ignored_spacing_theme.element_margin, 0)
        self.assertNotIn("page_margin", ThemeCreateRequest.model_fields)

    def test_partial_spacing_patch_leaves_the_other_edges_alone(self) -> None:
        """Sending only element_gap does not reset page margin or element margin."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        bold_theme: Theme = _theme_row(
            name="Spotmu Bold v1",
            slug="spotmu-bold-v1",
            template_key="spotmu_bold_v1",
            created_at=created_at,
        )
        bold_theme.page_margin = 120
        bold_theme.element_gap = 16
        bold_theme.element_margin = 8
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = bold_theme

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            patched_theme: ThemeReadResponse = patch_theme_by_id(
                bold_theme.id,
                ThemePatchRequest(element_gap=4),
                fake_session,
                None,
            )

        self.assertEqual(patched_theme.page_margin, 120)
        self.assertEqual(patched_theme.element_gap, 4)
        self.assertEqual(patched_theme.element_margin, 8)

    def test_null_spacing_is_rejected(self) -> None:
        """An explicit null page margin is HTTP 400 and does not write."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        theme_patch_request: ThemePatchRequest = ThemePatchRequest.model_validate(
            {"page_margin": None},
        )

        with self.assertRaises(HTTPException) as raised_http:
            patch_theme_by_id(
                paper_theme.id,
                theme_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            theme_spacing_required_detail("page_margin"),
        )
        self.assertEqual(paper_theme.page_margin, DEFAULT_PAGE_MARGIN)
        fake_session.commit.assert_not_called()

    def _assert_negative_spacing_is_rejected(
        self,
        theme: Theme,
        fake_session: MagicMock,
        theme_patch_request: ThemePatchRequest,
        field_name: str,
    ) -> None:
        """PATCH of -1 on one spacing field is HTTP 400 and does not commit."""

        with self.assertRaises(HTTPException) as raised_http:
            patch_theme_by_id(
                theme.id,
                theme_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            theme_spacing_negative_detail(field_name),
        )
        fake_session.commit.assert_not_called()


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
        status=ThemeStatus.DRAFT,
        page_margin=DEFAULT_PAGE_MARGIN,
        element_gap=DEFAULT_ELEMENT_GAP,
        element_margin=DEFAULT_ELEMENT_MARGIN,
        created_by=None,
        created_at=created_at,
        updated_at=created_at,
    )

    return theme
