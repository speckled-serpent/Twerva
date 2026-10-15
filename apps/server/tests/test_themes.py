"""Theme create validation and list serialization without Postgres."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import ValidationError

from app.api.v1.theme_elements import (
    THEME_ELEMENT_NOT_FOUND_DETAIL,
    create_theme_element,
    delete_theme_element,
    patch_theme_element,
)
import app.models
from app.api.v1.themes import (
    THEME_DELETE_REFERENCED_DETAIL,
    THEME_NAME_REQUIRED_DETAIL,
    THEME_STATUS_REQUIRED_DETAIL,
    create_theme,
    delete_theme_by_id,
    duplicate_theme_by_id,
    get_theme_by_id,
    list_themes,
    patch_theme_by_id,
    theme_delete_reference_blockers,
    unexpected_theme_reference_tables,
    theme_spacing_negative_detail,
    theme_spacing_required_detail,
)
from app.api.v1.schemas import (
    ThemeCreateRequest,
    THEME_ELEMENT_NAME_REQUIRED_DETAIL,
    ThemeElementCreateRequest,
    ThemeElementPatchRequest,
    ThemeElementReadResponse,
    ThemePatchRequest,
    ThemeReadResponse,
)
from app.models.enums import (
    AdvertisementType,
    BackgroundKind,
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
    ThemeStatus,
)
from app.models.campaign import Campaign
from app.models.content_source import ContentSource
from app.models.theme_element import ThemeElement
from app.themes.elements import (
    THEME_ELEMENT_IMAGE_REF_DETAIL,
    THEME_ELEMENT_TEXT_SOURCE_FORBIDDEN_DETAIL,
)
from app.models.theme import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
    Theme,
)
from app.themes.background import (
    BACKGROUND_ASSET_REF_DETAIL,
    BACKGROUND_COLOR_DETAIL,
    GRADIENT_ANGLE_DETAIL,
    GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
    GRADIENT_OFFSET_DETAIL,
    LIVE_ASSET_PAYLOAD_DETAIL,
    LIVE_COLOR_PAYLOAD_DETAIL,
    clamp_stop_offset,
    expand_hex_color,
    gradient_stop_color_detail,
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
        self.assertEqual(listed_themes[0].background_kind, BackgroundKind.COLOR)
        self.assertEqual(listed_themes[0].background_color, DEFAULT_BACKGROUND_COLOR)
        self.assertIsNone(listed_themes[0].background_gradient)
        self.assertIsNone(listed_themes[0].background_asset_ref)
        self.assertEqual(len(listed_themes), 2)


class ThemeStatusPatchTests(unittest.TestCase):
    """PATCH status round-trips; create ignores a status body."""

    def test_patch_live_then_draft_and_create_by_name_stays_draft(self) -> None:
        """One theme goes live and back to draft; GET returns each value.

        A name-only create stores draft. A create body that asks for live
        stores live when the default paper color is a valid payload.
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

        self.assertEqual(created_theme.status, ThemeStatus.LIVE)
        self.assertEqual(created_theme.name, "Harbor")
        self.assertEqual(created_theme.background_color, DEFAULT_BACKGROUND_COLOR)
        stored_theme: Theme = create_session.add.call_args.args[0]
        self.assertEqual(stored_theme.status, ThemeStatus.LIVE)

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

        negative_spacing_request: ThemeCreateRequest = ThemeCreateRequest(
            name="Night Shift",
            page_margin=-1,
            element_gap=4,
            element_margin=4,
        )
        negative_session: MagicMock = MagicMock()
        negative_session.scalars.return_value.all.return_value = ["harbor"]

        with patch(
            "app.api.v1.themes.commit_database_session_or_raise_conflict",
        ) as blocked_commit:
            with self.assertRaises(HTTPException) as negative_error:
                create_theme(negative_spacing_request, negative_session, None)

        self.assertEqual(negative_error.exception.status_code, 400)
        self.assertEqual(
            negative_error.exception.detail,
            theme_spacing_negative_detail("page_margin"),
        )
        blocked_commit.assert_not_called()

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


class ThemeBackgroundPatchTests(unittest.TestCase):
    """Each background kind round-trips. Live color needs a hex. Draft picture may be empty."""

    def test_each_kind_round_trips(self) -> None:
        """Color, gradient, and picture survive PATCH and GET."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        gradient_payload: dict[str, object] = {
            "angle_deg": 180,
            "stops": [
                {"offset": 0, "color": "#112233"},
                {"offset": 1, "color": "#F6F1E8"},
            ],
        }

        self._patch(
            paper_theme,
            fake_session,
            ThemePatchRequest(background_color="#AABBCC"),
        )
        color_theme: ThemeReadResponse = get_theme_by_id(paper_theme.id, fake_session)
        self.assertEqual(color_theme.background_kind, BackgroundKind.COLOR)
        self.assertEqual(color_theme.background_color, "#AABBCC")

        self._patch(
            paper_theme,
            fake_session,
            ThemePatchRequest(
                background_kind=BackgroundKind.GRADIENT,
                background_gradient=gradient_payload,
            ),
        )
        gradient_theme: ThemeReadResponse = get_theme_by_id(
            paper_theme.id,
            fake_session,
        )
        self.assertEqual(gradient_theme.background_kind, BackgroundKind.GRADIENT)
        self.assertIsNotNone(gradient_theme.background_gradient)

        if gradient_theme.background_gradient is None:
            self.fail("gradient payload is missing")

        self.assertEqual(gradient_theme.background_gradient.angle_deg, 180)
        self.assertEqual(len(gradient_theme.background_gradient.stops), 2)
        self.assertEqual(gradient_theme.background_gradient.stops[0].color, "#112233")
        self.assertEqual(gradient_theme.background_gradient.stops[1].color, "#F6F1E8")

        self._patch(
            paper_theme,
            fake_session,
            ThemePatchRequest(
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref="backgrounds/harbor.png",
            ),
        )
        picture_theme: ThemeReadResponse = get_theme_by_id(
            paper_theme.id,
            fake_session,
        )
        self.assertEqual(picture_theme.background_kind, BackgroundKind.PICTURE)
        self.assertEqual(picture_theme.background_asset_ref, "backgrounds/harbor.png")

    def test_texture_kind_is_rejected_on_write(self) -> None:
        """Create and patch refuse background kind texture."""

        with self.assertRaises(ValidationError):
            ThemePatchRequest.model_validate({"background_kind": "texture"})

        with self.assertRaises(ValidationError):
            ThemeCreateRequest.model_validate(
                {
                    "name": "Grain",
                    "background_kind": "texture",
                    "background_asset_ref": "textures/grain.jpeg",
                },
            )

    def test_live_color_with_blank_color_is_rejected(self) -> None:
        """A Live color theme cannot clear its color, including by becoming Live."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        live_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        live_theme.status = ThemeStatus.LIVE
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = live_theme

        self._assert_background_rejected(
            live_theme,
            fake_session,
            ThemePatchRequest(background_color="   "),
            LIVE_COLOR_PAYLOAD_DETAIL,
        )
        self.assertEqual(live_theme.background_color, DEFAULT_BACKGROUND_COLOR)
        self._assert_background_rejected(
            live_theme,
            fake_session,
            ThemePatchRequest.model_validate({"background_color": None}),
            LIVE_COLOR_PAYLOAD_DETAIL,
        )
        self.assertEqual(live_theme.status, ThemeStatus.LIVE)

        draft_theme: Theme = _theme_row(
            name="Harbor",
            slug="harbor",
            template_key=None,
            created_at=created_at,
        )
        draft_theme.background_color = None
        fake_session.get.return_value = draft_theme
        self._assert_background_rejected(
            draft_theme,
            fake_session,
            ThemePatchRequest(status=ThemeStatus.LIVE),
            LIVE_COLOR_PAYLOAD_DETAIL,
        )
        self.assertEqual(draft_theme.status, ThemeStatus.DRAFT)
        self.assertIsNone(draft_theme.background_color)

    def test_draft_picture_with_null_ref_saves(self) -> None:
        """A Draft picture may keep a null asset ref."""

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
            {"background_kind": "picture", "background_asset_ref": None},
        )

        patched_theme: ThemeReadResponse = self._patch(
            paper_theme,
            fake_session,
            theme_patch_request,
        )
        loaded_theme: ThemeReadResponse = get_theme_by_id(paper_theme.id, fake_session)

        self.assertEqual(patched_theme.background_kind, BackgroundKind.PICTURE)
        self.assertIsNone(patched_theme.background_asset_ref)
        self.assertEqual(patched_theme.status, ThemeStatus.DRAFT)
        self.assertEqual(loaded_theme.background_kind, BackgroundKind.PICTURE)
        self.assertIsNone(loaded_theme.background_asset_ref)

    def test_name_only_create_stores_paper_background(self) -> None:
        """Create stores color, paper #F6F1E8, and null gradient and asset ref."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        fake_session.refresh.side_effect = _assign_persisted_timestamps
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(name="Harbor")

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            created_theme: ThemeReadResponse = create_theme(
                theme_create_request,
                fake_session,
                None,
            )

        self.assertEqual(created_theme.background_kind, BackgroundKind.COLOR)
        self.assertEqual(created_theme.background_color, "#F6F1E8")
        self.assertEqual(created_theme.background_color, DEFAULT_BACKGROUND_COLOR)
        self.assertIsNone(created_theme.background_gradient)
        self.assertIsNone(created_theme.background_asset_ref)

    def test_invalid_background_payloads_are_rejected(self) -> None:
        """Bad hex, gradient, and asset paths are 400. Draft may omit a gradient."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        not_hex: ThemePatchRequest = ThemePatchRequest(background_color="zzzzzz")
        parent_path: ThemePatchRequest = ThemePatchRequest(
            background_asset_ref="../secret.png",
        )
        remote_path: ThemePatchRequest = ThemePatchRequest(
            background_asset_ref="https://example.com/a.png",
        )
        one_stop: ThemePatchRequest = ThemePatchRequest(
            background_kind=BackgroundKind.GRADIENT,
            background_gradient={
                "angle_deg": 90,
                "stops": [{"offset": 0, "color": "#112233"}],
            },
        )

        self._assert_background_rejected(
            paper_theme,
            fake_session,
            not_hex,
            BACKGROUND_COLOR_DETAIL,
        )
        self._assert_background_rejected(
            paper_theme,
            fake_session,
            parent_path,
            BACKGROUND_ASSET_REF_DETAIL,
        )
        self._assert_background_rejected(
            paper_theme,
            fake_session,
            remote_path,
            BACKGROUND_ASSET_REF_DETAIL,
        )
        self._assert_background_rejected(
            paper_theme,
            fake_session,
            one_stop,
            GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
        )
        self.assertEqual(paper_theme.background_kind, BackgroundKind.COLOR)
        self.assertEqual(paper_theme.background_color, DEFAULT_BACKGROUND_COLOR)

        paper_theme.status = ThemeStatus.LIVE
        self._assert_background_rejected(
            paper_theme,
            fake_session,
            ThemePatchRequest(background_kind=BackgroundKind.PICTURE),
            LIVE_ASSET_PAYLOAD_DETAIL,
        )
        self.assertEqual(paper_theme.background_kind, BackgroundKind.COLOR)

        paper_theme.status = ThemeStatus.DRAFT
        empty_gradient: ThemeReadResponse = self._patch(
            paper_theme,
            fake_session,
            ThemePatchRequest.model_validate(
                {"background_kind": "gradient", "background_gradient": None},
            ),
        )
        self.assertEqual(empty_gradient.background_kind, BackgroundKind.GRADIENT)
        self.assertIsNone(empty_gradient.background_gradient)
        self.assertEqual(empty_gradient.status, ThemeStatus.DRAFT)

    def test_hex_without_hash_expands_to_rrggbb(self) -> None:
        """3- and 6-digit hex, with or without #, store as uppercase #RRGGBB."""

        self.assertIsNone(expand_hex_color(""))
        self.assertIsNone(expand_hex_color("   "))
        self.assertIsNone(expand_hex_color(None))
        self.assertIsNone(expand_hex_color("zzzzzz"))
        self.assertEqual(expand_hex_color("4a4a4a"), "#4A4A4A")
        self.assertEqual(expand_hex_color("#4a4a4a"), "#4A4A4A")
        self.assertEqual(expand_hex_color("abc"), "#AABBCC")
        self.assertEqual(expand_hex_color("#abc"), "#AABBCC")
        self.assertEqual(expand_hex_color("ABC"), "#AABBCC")

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        patched_theme: ThemeReadResponse = self._patch(
            paper_theme,
            fake_session,
            ThemePatchRequest(background_color="4a4a4a"),
        )

        self.assertEqual(patched_theme.background_color, "#4A4A4A")

    def test_gradient_patch_names_the_problem(self) -> None:
        """A bad angle, offset, or stop color is a 400 that says how to fix it."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        bad_angle: ThemePatchRequest = ThemePatchRequest(
            background_gradient={
                "angle_deg": 400,
                "stops": [
                    {"offset": 0, "color": "#112233"},
                    {"offset": 1, "color": "#AABBCC"},
                ],
            },
        )
        bad_offset: ThemePatchRequest = ThemePatchRequest(
            background_gradient={
                "angle_deg": 180,
                "stops": [
                    {"offset": 0, "color": "#112233"},
                    {"offset": 1.5, "color": "#AABBCC"},
                ],
            },
        )
        bad_color: ThemePatchRequest = ThemePatchRequest(
            background_gradient={
                "angle_deg": 180,
                "stops": [
                    {"offset": 0, "color": "#112233"},
                    {"offset": 1, "color": "not-a-color"},
                ],
            },
        )

        self._assert_background_rejected(
            paper_theme,
            fake_session,
            bad_angle,
            GRADIENT_ANGLE_DETAIL,
        )
        self._assert_background_rejected(
            paper_theme,
            fake_session,
            bad_offset,
            GRADIENT_OFFSET_DETAIL,
        )
        self._assert_background_rejected(
            paper_theme,
            fake_session,
            bad_color,
            gradient_stop_color_detail(2),
        )

    def test_stop_offsets_clamp_instead_of_crossing(self) -> None:
        """A stop dragged past its neighbor stops at that neighbor."""

        self.assertEqual(clamp_stop_offset([0, 1], 0, 0.8), 0.8)
        self.assertEqual(clamp_stop_offset([0, 0.4], 0, 0.9), 0.4)
        self.assertEqual(clamp_stop_offset([0.2, 1], 1, 0), 0.2)
        self.assertEqual(clamp_stop_offset([0, 0.5, 1], 1, 0.9), 0.9)
        self.assertEqual(clamp_stop_offset([0, 0.5, 1], 1, 0.1), 0.1)

    def _patch(
        self,
        theme: Theme,
        fake_session: MagicMock,
        theme_patch_request: ThemePatchRequest,
    ) -> ThemeReadResponse:
        """Apply a patch with the commit helper stubbed."""

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            patched_theme: ThemeReadResponse = patch_theme_by_id(
                theme.id,
                theme_patch_request,
                fake_session,
                None,
            )

        return patched_theme

    def _assert_background_rejected(
        self,
        theme: Theme,
        fake_session: MagicMock,
        theme_patch_request: ThemePatchRequest,
        expected_detail: str,
    ) -> None:
        """PATCH is HTTP 400 and does not commit."""

        with self.assertRaises(HTTPException) as raised_http:
            patch_theme_by_id(
                theme.id,
                theme_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, expected_detail)
        fake_session.commit.assert_not_called()


class ThemeElementApiTests(unittest.TestCase):
    """Element create, order, band move, and source rejection."""

    def test_create_clear_text_and_image_then_move_band(self) -> None:
        """A clear text element and an image reload in order, then one moves."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_theme)
        text_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
            name="Title",
            band=ThemeElementBand.TOP,
            content_kind=ThemeElementContentKind.TEXT,
            text_source=ThemeElementTextSource.TITLE,
            font_family="DejaVu Sans",
            font_size=32,
            font_color="#112233",
            alignment="left",
        )
        image_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
            name="Image",
            band=ThemeElementBand.TOP,
            content_kind=ThemeElementContentKind.IMAGE,
            image_asset_ref="logos/mark.png",
        )

        with patch(
            "app.api.v1.theme_elements.commit_database_session_or_raise_conflict",
        ):
            text_element: ThemeElementReadResponse = create_theme_element(
                paper_theme.id,
                text_request,
                element_session,
                None,
            )
            image_element: ThemeElementReadResponse = create_theme_element(
                paper_theme.id,
                image_request,
                element_session,
                None,
            )

        self.assertIsNone(text_element.rectangle_color)
        self.assertEqual(text_element.name, "Title")
        self.assertEqual(text_element.text_source, ThemeElementTextSource.TITLE)
        self.assertFalse(text_element.bold)
        self.assertEqual(text_element.sort_order, 0)
        self.assertEqual(image_element.image_asset_ref, "logos/mark.png")
        self.assertEqual(image_element.name, "Image")
        self.assertIsNone(image_element.text_source)
        self.assertEqual(image_element.sort_order, 1)
        loaded_theme: ThemeReadResponse = get_theme_by_id(
            paper_theme.id,
            element_session,
        )
        loaded_pairs: list[tuple[str, str, int]] = [
            (element.band.value, element.content_kind.value, element.sort_order)
            for element in loaded_theme.elements
        ]

        self.assertEqual(
            loaded_pairs,
            [("top", "text", 0), ("top", "image", 1)],
        )

        with patch(
            "app.api.v1.theme_elements.commit_database_session_or_raise_conflict",
        ):
            moved_element: ThemeElementReadResponse = patch_theme_element(
                paper_theme.id,
                image_element.id,
                ThemeElementPatchRequest(band=ThemeElementBand.MIDDLE),
                element_session,
                None,
            )

        self.assertEqual(moved_element.band, ThemeElementBand.MIDDLE)
        self.assertEqual(moved_element.sort_order, 0)
        self.assertEqual(moved_element.name, "Image")
        reloaded_theme: ThemeReadResponse = get_theme_by_id(
            paper_theme.id,
            element_session,
        )
        reloaded_pairs: list[tuple[str, str, int]] = [
            (element.band.value, element.content_kind.value, element.sort_order)
            for element in reloaded_theme.elements
        ]

        self.assertEqual(
            reloaded_pairs,
            [("top", "text", 0), ("middle", "image", 0)],
        )

    def test_blank_name_is_rejected_and_a_trimmed_name_is_stored(self) -> None:
        """Create and patch refuse a blank name. Surrounding spaces are dropped."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_theme)
        name_application: FastAPI = FastAPI()

        @name_application.post("/elements")
        def create_named_element(
            theme_element_create_request: ThemeElementCreateRequest,
        ) -> dict[str, str]:

            stored_name: dict[str, str] = {"name": theme_element_create_request.name}

            return stored_name

        @name_application.patch("/elements")
        def patch_named_element(
            theme_element_patch_request: ThemeElementPatchRequest,
        ) -> dict[str, str | None]:

            stored_name: dict[str, str | None] = {"name": theme_element_patch_request.name}

            return stored_name

        name_client: TestClient = TestClient(name_application)
        missing_response: Response = name_client.post(
            "/elements",
            json={
                "band": "top",
                "content_kind": "text",
                "text_source": "title",
                "font_family": "DejaVu Sans",
                "font_size": 32,
                "font_color": "#112233",
                "alignment": "left",
            },
        )
        blank_response: Response = name_client.post(
            "/elements",
            json={
                "name": "   ",
                "band": "top",
                "content_kind": "image",
                "image_asset_ref": "logos/mark.png",
            },
        )
        trimmed_response: Response = name_client.post(
            "/elements",
            json={
                "name": "  Subject  ",
                "band": "top",
                "content_kind": "image",
                "image_asset_ref": "logos/mark.png",
            },
        )
        cleared_response: Response = name_client.patch("/elements", json={"name": " "})
        null_response: Response = name_client.patch("/elements", json={"name": None})
        omitted_response: Response = name_client.patch("/elements", json={"font_size": 40})

        self.assertEqual(missing_response.status_code, 422)
        self.assertEqual(blank_response.status_code, 422)
        self.assertIn(THEME_ELEMENT_NAME_REQUIRED_DETAIL, blank_response.text)
        self.assertEqual(trimmed_response.status_code, 200)
        self.assertEqual(trimmed_response.json()["name"], "Subject")
        self.assertEqual(cleared_response.status_code, 422)
        self.assertIn(THEME_ELEMENT_NAME_REQUIRED_DETAIL, cleared_response.text)
        self.assertEqual(null_response.status_code, 422)
        self.assertIn(THEME_ELEMENT_NAME_REQUIRED_DETAIL, null_response.text)
        self.assertEqual(omitted_response.status_code, 200)
        self.assertIsNone(omitted_response.json()["name"])

        with patch(
            "app.api.v1.theme_elements.commit_database_session_or_raise_conflict",
        ):
            created_element: ThemeElementReadResponse = create_theme_element(
                paper_theme.id,
                ThemeElementCreateRequest(
                    name="  Body  ",
                    band=ThemeElementBand.TOP,
                    content_kind=ThemeElementContentKind.TEXT,
                    text_source=ThemeElementTextSource.TITLE,
                    font_family="DejaVu Sans",
                    font_size=32,
                    font_color="#112233",
                    alignment="left",
                ),
                element_session,
                None,
            )
            renamed_element: ThemeElementReadResponse = patch_theme_element(
                paper_theme.id,
                created_element.id,
                ThemeElementPatchRequest(name="  Caption  "),
                element_session,
                None,
            )

        self.assertEqual(created_element.name, "Body")
        self.assertEqual(renamed_element.name, "Caption")

    def test_unknown_text_source_and_coordinates_are_rejected(self) -> None:
        """Sources outside the four Spotmu keys, and x/y/width, never persist."""

        with self.assertRaises(ValidationError):
            ThemeElementCreateRequest.model_validate(
                {
                    "name": "Title",
                    "band": "top",
                    "content_kind": "text",
                    "text_source": "caption",
                    "font_family": "DejaVu Sans",
                    "font_size": 32,
                    "font_color": "#112233",
                    "alignment": "left",
                },
            )

        with self.assertRaises(ValidationError):
            ThemeElementCreateRequest.model_validate(
                {
                    "name": "Title",
                    "band": "top",
                    "content_kind": "text",
                    "text_source": "title",
                    "font_family": "DejaVu Sans",
                    "font_size": 32,
                    "font_color": "#112233",
                    "alignment": "left",
                    "x": 10,
                    "y": 20,
                    "width": 400,
                },
            )

    def test_image_ref_must_be_svg_png_or_jpeg(self) -> None:
        """A non-image suffix and a parent path are HTTP 400."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_theme)
        gif_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
            name="Image",
            band=ThemeElementBand.BOTTOM,
            content_kind=ThemeElementContentKind.IMAGE,
            image_asset_ref="logos/mark.gif",
        )

        with self.assertRaises(HTTPException) as raised_gif:
            create_theme_element(paper_theme.id, gif_request, element_session, None)

        self.assertEqual(raised_gif.exception.status_code, 400)
        self.assertEqual(raised_gif.exception.detail, THEME_ELEMENT_IMAGE_REF_DETAIL)
        self.assertEqual(paper_theme.elements, [])
        parent_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
            name="Image",
            band=ThemeElementBand.BOTTOM,
            content_kind=ThemeElementContentKind.IMAGE,
            image_asset_ref="../secret.png",
        )

        with self.assertRaises(HTTPException) as raised_parent:
            create_theme_element(
                paper_theme.id,
                parent_request,
                element_session,
                None,
            )

        self.assertEqual(raised_parent.exception.status_code, 400)
        self.assertEqual(paper_theme.elements, [])

    def test_image_element_rejects_a_text_source(self) -> None:
        """An image row cannot keep one of the Spotmu text sources."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_theme)
        image_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
            name="Image",
            band=ThemeElementBand.TOP,
            content_kind=ThemeElementContentKind.IMAGE,
            text_source=ThemeElementTextSource.TITLE,
            image_asset_ref="logos/mark.jpg",
        )

        with self.assertRaises(HTTPException) as raised_http:
            create_theme_element(
                paper_theme.id,
                image_request,
                element_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            THEME_ELEMENT_TEXT_SOURCE_FORBIDDEN_DETAIL,
        )
        self.assertEqual(paper_theme.elements, [])

    def test_delete_compacts_the_band(self) -> None:
        """Deleting the first element renumbers the remaining one to 0."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_theme)
        first_request: ThemeElementCreateRequest = _text_element_request(
            ThemeElementTextSource.TITLE,
        )
        second_request: ThemeElementCreateRequest = _text_element_request(
            ThemeElementTextSource.CANONICAL_URL,
        )

        with patch(
            "app.api.v1.theme_elements.commit_database_session_or_raise_conflict",
        ):
            first_element: ThemeElementReadResponse = create_theme_element(
                paper_theme.id,
                first_request,
                element_session,
                None,
            )
            second_element: ThemeElementReadResponse = create_theme_element(
                paper_theme.id,
                second_request,
                element_session,
                None,
            )
            delete_theme_element(
                paper_theme.id,
                first_element.id,
                element_session,
                None,
            )

        loaded_theme: ThemeReadResponse = get_theme_by_id(
            paper_theme.id,
            element_session,
        )

        self.assertEqual(len(loaded_theme.elements), 1)
        self.assertEqual(loaded_theme.elements[0].id, second_element.id)
        self.assertEqual(loaded_theme.elements[0].sort_order, 0)
        self.assertEqual(
            loaded_theme.elements[0].text_source,
            ThemeElementTextSource.CANONICAL_URL,
        )

    def test_missing_element_returns_404(self) -> None:
        """PATCH for an id that is not on the theme is HTTP 404."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_theme)
        missing_element_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            patch_theme_element(
                paper_theme.id,
                missing_element_id,
                ThemeElementPatchRequest(band=ThemeElementBand.BOTTOM),
                element_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 404)
        self.assertIn(THEME_ELEMENT_NOT_FOUND_DETAIL, str(raised_http.exception.detail))


class ThemeDuplicateTests(unittest.TestCase):
    """Duplicate copies a Live theme into a new Draft and leaves the source."""

    def test_duplicate_live_theme_with_gradient_and_two_elements(self) -> None:
        """The copy is Draft, template_key is null, and element ids differ."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        source_updated_at: datetime = datetime(2026, 10, 4, 18, 30, tzinfo=timezone.utc)
        source_gradient: dict[str, object] = {
            "angle_deg": 180,
            "stops": [
                {"offset": 0, "color": "#112233"},
                {"offset": 1, "color": "#F6F1E8"},
            ],
        }
        source_theme: Theme = _theme_row(
            name="Harbor Night",
            slug="harbor-night",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        source_theme.status = ThemeStatus.LIVE
        source_theme.page_margin = 120
        source_theme.element_gap = 16
        source_theme.element_margin = 8
        source_theme.background_kind = BackgroundKind.GRADIENT
        source_theme.background_color = None
        source_theme.background_gradient = source_gradient
        source_theme.background_asset_ref = None
        source_theme.updated_at = source_updated_at
        text_element: ThemeElement = ThemeElement(
            id=uuid.uuid4(),
            theme_id=source_theme.id,
            band=ThemeElementBand.TOP,
            sort_order=0,
            content_kind=ThemeElementContentKind.TEXT,
            name="Title",
            rectangle_color=None,
            text_source=ThemeElementTextSource.TITLE,
            font_family="DejaVu Sans",
            font_size=32,
            font_color="#112233",
            bold=True,
            italic=False,
            underline=False,
            strikethrough=False,
            font_weight=700,
            alignment=ThemeElementAlignment.LEFT,
            image_asset_ref=None,
            created_at=created_at,
            updated_at=created_at,
        )
        image_element: ThemeElement = ThemeElement(
            id=uuid.uuid4(),
            theme_id=source_theme.id,
            band=ThemeElementBand.BOTTOM,
            sort_order=0,
            content_kind=ThemeElementContentKind.IMAGE,
            name="Image",
            rectangle_color="#AABBCC",
            text_source=None,
            font_family=None,
            font_size=None,
            font_color=None,
            bold=False,
            italic=False,
            underline=False,
            strikethrough=False,
            font_weight=None,
            alignment=None,
            image_asset_ref="logos/mark.png",
            created_at=created_at,
            updated_at=created_at,
        )
        source_theme.elements.append(text_element)
        source_theme.elements.append(image_element)
        source_element_ids: list[uuid.UUID] = [text_element.id, image_element.id]
        duplicate_session: _DuplicateMemorySession = _DuplicateMemorySession(
            source_theme,
            ["harbor-night"],
        )
        operator_id: uuid.UUID = uuid.uuid4()
        current_ops_operator: MagicMock = MagicMock()
        current_ops_operator.id = operator_id

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            copied_theme: ThemeReadResponse = duplicate_theme_by_id(
                source_theme.id,
                duplicate_session,
                current_ops_operator,
            )

        self.assertEqual(source_theme.status, ThemeStatus.LIVE)
        self.assertEqual(source_theme.updated_at, source_updated_at)
        self.assertEqual(source_theme.template_key, "spotmu_paper_v1")
        self.assertEqual(
            [element.id for element in source_theme.elements],
            source_element_ids,
        )
        self.assertNotEqual(copied_theme.id, source_theme.id)
        self.assertEqual(copied_theme.status, ThemeStatus.DRAFT)
        self.assertIsNone(copied_theme.template_key)
        self.assertEqual(copied_theme.name, "Copy of Harbor Night")
        self.assertEqual(copied_theme.slug, "copy-of-harbor-night")
        self.assertEqual(copied_theme.page_margin, 120)
        self.assertEqual(copied_theme.element_gap, 16)
        self.assertEqual(copied_theme.element_margin, 8)
        self.assertEqual(copied_theme.background_kind, BackgroundKind.GRADIENT)
        self.assertIsNotNone(copied_theme.background_gradient)
        self.assertEqual(copied_theme.background_gradient.angle_deg, 180)
        self.assertEqual(copied_theme.background_gradient.stops[0].color, "#112233")
        self.assertEqual(copied_theme.background_gradient.stops[1].color, "#F6F1E8")
        stored_copies: list[Theme] = [
            added_row
            for added_row in duplicate_session.added
            if isinstance(added_row, Theme)
        ]
        self.assertEqual(len(stored_copies), 1)
        self.assertEqual(stored_copies[0].background_gradient, source_gradient)
        self.assertIsNot(stored_copies[0].background_gradient, source_gradient)
        self.assertEqual(copied_theme.created_by, operator_id)
        self.assertEqual(len(copied_theme.elements), 2)
        copied_element_ids: list[uuid.UUID] = [
            element.id for element in copied_theme.elements
        ]
        self.assertEqual(len(set(copied_element_ids)), 2)
        self.assertTrue(set(copied_element_ids).isdisjoint(source_element_ids))
        self.assertEqual(copied_theme.elements[0].name, "Title")
        self.assertEqual(copied_theme.elements[0].band, ThemeElementBand.TOP)
        self.assertEqual(copied_theme.elements[0].sort_order, 0)
        self.assertEqual(
            copied_theme.elements[0].text_source,
            ThemeElementTextSource.TITLE,
        )
        self.assertEqual(copied_theme.elements[0].font_weight, 700)
        self.assertIsNone(copied_theme.elements[0].rectangle_color)
        self.assertEqual(copied_theme.elements[1].name, "Image")
        self.assertEqual(copied_theme.elements[1].band, ThemeElementBand.BOTTOM)
        self.assertEqual(copied_theme.elements[1].sort_order, 0)
        self.assertEqual(copied_theme.elements[1].image_asset_ref, "logos/mark.png")
        self.assertEqual(copied_theme.elements[1].rectangle_color, "#AABBCC")
        self.assertIsNone(copied_theme.elements[1].text_source)
        reloaded_copy: ThemeReadResponse = get_theme_by_id(
            copied_theme.id,
            duplicate_session,
        )
        self.assertEqual(reloaded_copy.status, ThemeStatus.DRAFT)
        self.assertEqual(
            [element.id for element in reloaded_copy.elements],
            copied_element_ids,
        )

    def test_missing_theme_duplicate_returns_404(self) -> None:
        """POST duplicate raises HTTP 404 when the source row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_theme_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            duplicate_theme_by_id(missing_theme_id, fake_session, None)

        self.assertEqual(raised_http.exception.status_code, 404)
        fake_session.add.assert_not_called()


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


class _DuplicateMemorySession:
    """In-memory source theme plus the Draft created by duplicate."""

    def __init__(self, theme: Theme, taken_slugs: list[str]) -> None:

        self.theme: Theme = theme
        self.taken_slugs: list[str] = taken_slugs
        self.added: list[Theme | ThemeElement] = []

    def get(self, model: type[object], key: uuid.UUID) -> Theme | None:
        """Return the source theme or a theme this session has added."""

        if model is not Theme:

            return None

        if key == self.theme.id:

            return self.theme

        for added_row in self.added:

            if isinstance(added_row, Theme) and added_row.id == key:

                return added_row

        return None

    def scalars(self, statement: object = None) -> MagicMock:
        """Return the slugs already stored, for the unique-slug helper."""

        _ = statement
        slug_result: MagicMock = MagicMock()
        slug_result.all.return_value = list(self.taken_slugs)

        return slug_result

    def add(self, row: Theme | ThemeElement) -> None:
        """Remember a pending theme or element."""

        self.added.append(row)

    def flush(self) -> None:
        """Assign ids the database would assign before elements are copied."""

        for added_row in self.added:
            _assign_new_row_identity(added_row)

    def refresh(self, row: Theme | ThemeElement) -> None:
        """Fill ids and timestamps, including elements on a refreshed theme."""

        _assign_new_row_identity(row)

        if isinstance(row, Theme):

            for element in row.elements:
                _assign_new_row_identity(element)


def _assign_new_row_identity(row: Theme | ThemeElement) -> None:
    """Fill a new row's id and timestamps once. Leave existing values."""

    persisted_at: datetime = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)

    if row.id is None:
        row.id = uuid.uuid4()

    if row.created_at is None:
        row.created_at = persisted_at
        row.updated_at = persisted_at


class _EmptyQueryResult:
    """Stand-in for ``session.execute(...).all()`` when the test has no units."""

    def all(self) -> list[object]:
        """Return no rows."""

        return []


class _ElementMemorySession:
    """In-memory theme lookup for element handlers. Not a database."""

    def __init__(self, theme: Theme) -> None:

        self.theme: Theme = theme

    def get(self, model: type[object], key: uuid.UUID) -> Theme | ThemeElement | None:
        """Return the theme or one of its elements."""

        if model is Theme:

            if key == self.theme.id:

                return self.theme

            return None

        if model is ThemeElement:

            for element in self.theme.elements:

                if element.id == key:

                    return element

            return None

        return None

    def add(self, row: object) -> None:
        """Accept the pending insert. The handler also appends the relationship."""

        return None

    def delete(self, row: object) -> None:
        """Accept the pending delete. The handler already detached the row."""

        return None

    def flush(self) -> None:
        """The unique-key dance does not need a database in this test."""

        return None

    def execute(self, statement: object) -> _EmptyQueryResult:
        """Text sync finds no units. These tests do not store sources."""

        _ = statement

        return _EmptyQueryResult()

    def refresh(self, row: Theme | ThemeElement) -> None:
        """Fill id and timestamps the way a Postgres refresh would."""

        persisted_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)

        if row.id is None:
            row.id = uuid.uuid4()

        if row.created_at is None:
            row.created_at = persisted_at
            row.updated_at = persisted_at


def _text_element_request(
    text_source: ThemeElementTextSource,
) -> ThemeElementCreateRequest:
    """Build a clear text element on the top band."""

    text_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
        name=text_source.value,
        band=ThemeElementBand.TOP,
        content_kind=ThemeElementContentKind.TEXT,
        text_source=text_source,
        font_family="DejaVu Sans",
        font_size=28,
        font_color="#112233",
        alignment="center",
    )

    return text_request


class ThemeCreatePresetTests(unittest.TestCase):
    """Create stores the frame and elements together, or stores nothing."""

    def test_create_stores_frame_and_elements(self) -> None:
        """Live spacing, a text element, and an image element come back together."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        fake_session.refresh.side_effect = _assign_persisted_timestamps
        fake_session.flush.side_effect = _assign_theme_id_on_flush(fake_session)
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(
            name="Harbor",
            status=ThemeStatus.LIVE,
            page_margin=40,
            element_gap=8,
            element_margin=4,
            background_kind=BackgroundKind.COLOR,
            background_color="#112233",
            elements=[
                ThemeElementCreateRequest(
                    name="Title",
                    band=ThemeElementBand.TOP,
                    content_kind=ThemeElementContentKind.TEXT,
                    text_source=ThemeElementTextSource.TITLE,
                    font_family="DejaVu Sans",
                    font_size=32,
                    font_color="#112233",
                    alignment=ThemeElementAlignment.CENTER,
                ),
                ThemeElementCreateRequest(
                    name="Image",
                    band=ThemeElementBand.BOTTOM,
                    content_kind=ThemeElementContentKind.IMAGE,
                    image_asset_ref="logos/mark.png",
                ),
            ],
        )

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            created_theme: ThemeReadResponse = create_theme(
                theme_create_request,
                fake_session,
                None,
            )

        self.assertEqual(created_theme.status, ThemeStatus.LIVE)
        self.assertEqual(created_theme.page_margin, 40)
        self.assertEqual(created_theme.element_gap, 8)
        self.assertEqual(created_theme.element_margin, 4)
        self.assertEqual(created_theme.background_color, "#112233")
        self.assertEqual(len(created_theme.elements), 2)
        self.assertEqual(created_theme.elements[0].band, ThemeElementBand.TOP)
        self.assertEqual(created_theme.elements[0].text_source, ThemeElementTextSource.TITLE)
        self.assertEqual(created_theme.elements[1].band, ThemeElementBand.BOTTOM)
        self.assertEqual(created_theme.elements[1].image_asset_ref, "logos/mark.png")
        self.assertNotEqual(created_theme.elements[0].id, created_theme.elements[1].id)

    def test_live_create_with_blank_color_stores_nothing(self) -> None:
        """A Live color theme with a blank color is 400 and is not committed."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(
            name="Harbor",
            status=ThemeStatus.LIVE,
            background_color="",
        )

        with patch(
            "app.api.v1.themes.commit_database_session_or_raise_conflict",
        ) as blocked_commit:
            with self.assertRaises(HTTPException) as create_error:
                create_theme(theme_create_request, fake_session, None)

        self.assertEqual(create_error.exception.status_code, 400)
        self.assertEqual(create_error.exception.detail, LIVE_COLOR_PAYLOAD_DETAIL)
        blocked_commit.assert_not_called()
        fake_session.add.assert_not_called()

    def test_invalid_element_stores_nothing(self) -> None:
        """A text element without a family is 400 and is not committed."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        theme_create_request: ThemeCreateRequest = ThemeCreateRequest(
            name="Harbor",
            elements=[
                ThemeElementCreateRequest(
                    name="Title",
                    band=ThemeElementBand.MIDDLE,
                    content_kind=ThemeElementContentKind.TEXT,
                    text_source=ThemeElementTextSource.TITLE,
                    font_size=32,
                    font_color="#112233",
                    alignment=ThemeElementAlignment.LEFT,
                ),
            ],
        )

        with patch(
            "app.api.v1.themes.commit_database_session_or_raise_conflict",
        ) as blocked_commit:
            with self.assertRaises(HTTPException) as create_error:
                create_theme(theme_create_request, fake_session, None)

        self.assertEqual(create_error.exception.status_code, 400)
        blocked_commit.assert_not_called()
        fake_session.add.assert_not_called()


class ThemeDeleteTests(unittest.TestCase):
    """Delete removes a theme. Elements cascade. Other references block it."""

    def test_delete_removes_the_theme(self) -> None:
        """DELETE hands the row to the session and commits."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        fake_session.scalar.return_value = 0

        with patch("app.api.v1.themes.commit_database_session_or_raise_conflict"):
            delete_theme_by_id(paper_theme.id, fake_session, None)

        fake_session.delete.assert_called_once_with(paper_theme)

    def test_source_reference_blocks_delete(self) -> None:
        """A source that stores this theme refuses the delete."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme
        fake_session.scalar.return_value = 1

        with self.assertRaises(HTTPException) as delete_error:
            delete_theme_by_id(paper_theme.id, fake_session, None)

        self.assertEqual(delete_error.exception.status_code, 409)
        self.assertIn("still referenced", delete_error.exception.detail)
        self.assertIn("sources", delete_error.exception.detail)
        fake_session.delete.assert_not_called()

    def test_missing_theme_delete_returns_404(self) -> None:
        """DELETE raises HTTP 404 when the row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_theme_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as delete_error:
            delete_theme_by_id(missing_theme_id, fake_session, None)

        self.assertEqual(delete_error.exception.status_code, 404)
        fake_session.delete.assert_not_called()

    def test_only_elements_and_sources_reference_themes(self) -> None:
        """Elements cascade. Sources and campaigns restrict by row. No other table points at themes."""

        _ = app.models
        self.assertEqual(unexpected_theme_reference_tables(), [])
        element_actions: set[str] = {
            (foreign_key.ondelete or "").upper()
            for foreign_key in ThemeElement.__table__.foreign_keys
            if foreign_key.column.table.name == "themes"
        }
        source_actions: set[str] = {
            (foreign_key.ondelete or "").upper()
            for foreign_key in ContentSource.__table__.c.theme_id.foreign_keys
        }
        self.assertEqual(element_actions, {"CASCADE"})
        self.assertEqual(source_actions, {"RESTRICT"})
        campaign_actions: set[str] = {
            (foreign_key.ondelete or "").upper()
            for foreign_key in Campaign.__table__.c.theme_id.foreign_keys
        }
        self.assertEqual(campaign_actions, {"RESTRICT"})

    def test_other_reference_blocks_delete(self) -> None:
        """A non-cascade foreign key refuses the delete and leaves the row."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_theme: Theme = _theme_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_theme

        with patch(
            "app.api.v1.themes.theme_delete_reference_blockers",
            return_value=["campaigns"],
        ):
            with self.assertRaises(HTTPException) as delete_error:
                delete_theme_by_id(paper_theme.id, fake_session, None)

        self.assertEqual(delete_error.exception.status_code, 409)
        self.assertIn("still referenced", delete_error.exception.detail)
        self.assertIn("campaigns", delete_error.exception.detail)
        fake_session.delete.assert_not_called()


def _assign_theme_id_on_flush(fake_session: MagicMock):
    """Give the pending theme an id the way a database flush would."""

    def assign_theme_id() -> None:

        pending_theme: Theme = fake_session.add.call_args_list[0].args[0]

        if pending_theme.id is None:
            pending_theme.id = uuid.uuid4()

    return assign_theme_id


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
        background_kind=BackgroundKind.COLOR,
        background_color=DEFAULT_BACKGROUND_COLOR,
        background_gradient=None,
        background_asset_ref=None,
        created_by=None,
        created_at=created_at,
        updated_at=created_at,
    )

    return theme
