"""Skeleton create validation and list serialization without Postgres."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import ValidationError

from app.api.v1.skeleton_elements import (
    SKELETON_ELEMENT_NOT_FOUND_DETAIL,
    create_skeleton_element,
    delete_skeleton_element,
    patch_skeleton_element,
)
import app.models
from app.api.v1.skeletons import (
    SKELETON_DELETE_REFERENCED_DETAIL,
    SKELETON_NAME_REQUIRED_DETAIL,
    SKELETON_STATUS_REQUIRED_DETAIL,
    create_skeleton,
    delete_skeleton_by_id,
    duplicate_skeleton_by_id,
    get_skeleton_by_id,
    list_skeletons,
    patch_skeleton_by_id,
    skeleton_delete_reference_blockers,
    unexpected_skeleton_reference_tables,
    skeleton_spacing_negative_detail,
    skeleton_spacing_required_detail,
)
from app.api.v1.schemas import (
    SkeletonCreateRequest,
    SKELETON_ELEMENT_NAME_REQUIRED_DETAIL,
    SkeletonElementCreateRequest,
    SkeletonElementPatchRequest,
    SkeletonElementReadResponse,
    SkeletonPatchRequest,
    SkeletonReadResponse,
)
from app.models.enums import (
    AdvertisementType,
    BackgroundKind,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
    SkeletonStatus,
)
from app.models.campaign import Campaign
from app.models.carousel import Carousel
from app.models.skeleton_element import SkeletonElement
from app.skeletons.elements import (
    SKELETON_ELEMENT_IMAGE_REF_DETAIL,
    SKELETON_ELEMENT_TEXT_SOURCE_FORBIDDEN_DETAIL,
)
from app.models.skeleton import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
    Skeleton,
)
from app.skeletons.background import (
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
from app.skeletons.slug import allocate_unique_skeleton_slug, slugify_skeleton_name


class SkeletonCreateValidationTests(unittest.TestCase):
    """Create rejects a blank name and an unknown template before any write."""

    def test_empty_name_fails_schema_validation(self) -> None:
        """A zero-length name never reaches the handler."""

        with self.assertRaises(ValidationError):
            SkeletonCreateRequest(name="")

    def test_blank_skeleton_name_is_rejected(self) -> None:
        """Whitespace-only name returns HTTP 400 and does not persist."""

        fake_session: MagicMock = MagicMock()
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(name="   ")

        with self.assertRaises(HTTPException) as raised_http:
            create_skeleton(skeleton_create_request, fake_session, None)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, SKELETON_NAME_REQUIRED_DETAIL)
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()

    def test_unknown_template_key_is_rejected(self) -> None:
        """A template id outside the carousel registry returns HTTP 400."""

        fake_session: MagicMock = MagicMock()
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(
            name="Night Shift",
            template_key="not_a_template",
        )

        with self.assertRaises(HTTPException) as raised_http:
            create_skeleton(skeleton_create_request, fake_session, None)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertIn("Unknown carousel template", str(raised_http.exception.detail))
        fake_session.add.assert_not_called()

    def test_create_defaults_to_carousel_without_template(self) -> None:
        """A named skeleton persists carousel, a slug, and a null template key."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(name="  Harbor  ")
        operator_id: uuid.UUID = uuid.uuid4()
        current_ops_operator: MagicMock = MagicMock()
        current_ops_operator.id = operator_id
        fake_session.refresh.side_effect = _assign_persisted_timestamps

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            skeleton_read_response: SkeletonReadResponse = create_skeleton(
                skeleton_create_request,
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(skeleton_read_response.name, "Harbor")
        self.assertEqual(skeleton_read_response.slug, "harbor")
        self.assertEqual(
            skeleton_read_response.advertisement_type,
            AdvertisementType.CAROUSEL,
        )
        self.assertIsNone(skeleton_read_response.template_key)
        self.assertEqual(skeleton_read_response.status, SkeletonStatus.DRAFT)
        self.assertEqual(skeleton_read_response.page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(skeleton_read_response.element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(skeleton_read_response.element_margin, DEFAULT_ELEMENT_MARGIN)
        self.assertEqual(skeleton_read_response.created_by, operator_id)
        added_skeleton: Skeleton = fake_session.add.call_args.args[0]
        self.assertEqual(added_skeleton.status, SkeletonStatus.DRAFT)
        self.assertEqual(added_skeleton.page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(added_skeleton.element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(added_skeleton.element_margin, DEFAULT_ELEMENT_MARGIN)
        fake_session.add.assert_called_once()

    def test_blank_template_key_is_stored_as_null(self) -> None:
        """Whitespace template_key is treated as omitted."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(
            name="Harbor",
            template_key="   ",
        )
        fake_session.refresh.side_effect = _assign_persisted_timestamps

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            skeleton_read_response: SkeletonReadResponse = create_skeleton(
                skeleton_create_request,
                fake_session,
                None,
            )

        self.assertIsNone(skeleton_read_response.template_key)
        added_skeleton: Skeleton = fake_session.add.call_args.args[0]
        self.assertIsNone(added_skeleton.template_key)

    def test_known_template_key_is_stored(self) -> None:
        """spotmu_bold_v1 is accepted and returned on the read model."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = ["harbor"]
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(
            name="Harbor",
            template_key="spotmu_bold_v1",
        )
        fake_session.refresh.side_effect = _assign_persisted_timestamps

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            skeleton_read_response: SkeletonReadResponse = create_skeleton(
                skeleton_create_request,
                fake_session,
                None,
            )

        self.assertEqual(skeleton_read_response.slug, "harbor-2")
        self.assertEqual(skeleton_read_response.template_key, "spotmu_bold_v1")

    def test_missing_skeleton_returns_404(self) -> None:
        """GET by id raises HTTP 404 when the row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_skeleton_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            get_skeleton_by_id(missing_skeleton_id, fake_session)

        self.assertEqual(raised_http.exception.status_code, 404)


class SkeletonListTests(unittest.TestCase):
    """List returns the rows the query produced, newest-query order kept."""

    def test_list_skeletons_serializes_query_rows(self) -> None:
        """GET list maps name, advertisement type, and template key."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        bold_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Bold v1",
            slug="spotmu-bold-v1",
            template_key="spotmu_bold_v1",
            created_at=created_at,
        )
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = [bold_skeleton, paper_skeleton]

        listed_skeletons: list[SkeletonReadResponse] = list_skeletons(fake_session)

        self.assertEqual(
            [skeleton.name for skeleton in listed_skeletons],
            ["Spotmu Bold v1", "Spotmu Paper v1"],
        )
        self.assertEqual(
            listed_skeletons[0].advertisement_type,
            AdvertisementType.CAROUSEL,
        )
        self.assertEqual(listed_skeletons[0].template_key, "spotmu_bold_v1")
        self.assertEqual(listed_skeletons[1].template_key, "spotmu_paper_v1")
        self.assertEqual(listed_skeletons[0].status, SkeletonStatus.DRAFT)
        self.assertEqual(listed_skeletons[1].status, SkeletonStatus.DRAFT)
        self.assertEqual(listed_skeletons[0].page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(listed_skeletons[0].element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(listed_skeletons[0].element_margin, DEFAULT_ELEMENT_MARGIN)
        self.assertEqual(listed_skeletons[1].page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(listed_skeletons[0].background_kind, BackgroundKind.COLOR)
        self.assertEqual(listed_skeletons[0].background_color, DEFAULT_BACKGROUND_COLOR)
        self.assertIsNone(listed_skeletons[0].background_gradient)
        self.assertIsNone(listed_skeletons[0].background_asset_ref)
        self.assertEqual(len(listed_skeletons), 2)


class SkeletonStatusPatchTests(unittest.TestCase):
    """PATCH status round-trips; create ignores a status body."""

    def test_patch_live_then_draft_and_create_by_name_stays_draft(self) -> None:
        """One skeleton goes live and back to draft; GET returns each value.

        A name-only create stores draft. A create body that asks for live
        stores live when the default paper color is a valid payload.
        """

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        current_ops_operator: MagicMock = MagicMock()

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            live_response: SkeletonReadResponse = patch_skeleton_by_id(
                paper_skeleton.id,
                SkeletonPatchRequest(status=SkeletonStatus.LIVE),
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(live_response.status, SkeletonStatus.LIVE)
        self.assertEqual(paper_skeleton.status, SkeletonStatus.LIVE)
        loaded_live: SkeletonReadResponse = get_skeleton_by_id(paper_skeleton.id, fake_session)
        self.assertEqual(loaded_live.status, SkeletonStatus.LIVE)
        self.assertEqual(loaded_live.name, "Spotmu Paper v1")

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            draft_response: SkeletonReadResponse = patch_skeleton_by_id(
                paper_skeleton.id,
                SkeletonPatchRequest(status=SkeletonStatus.DRAFT),
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(draft_response.status, SkeletonStatus.DRAFT)
        loaded_draft: SkeletonReadResponse = get_skeleton_by_id(paper_skeleton.id, fake_session)
        self.assertEqual(loaded_draft.status, SkeletonStatus.DRAFT)

        create_session: MagicMock = MagicMock()
        create_session.scalars.return_value.all.return_value = []
        create_session.refresh.side_effect = _assign_persisted_timestamps
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest.model_validate(
            {"name": "Harbor", "status": "live"},
        )

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            created_skeleton: SkeletonReadResponse = create_skeleton(
                skeleton_create_request,
                create_session,
                None,
            )

        self.assertEqual(created_skeleton.status, SkeletonStatus.LIVE)
        self.assertEqual(created_skeleton.name, "Harbor")
        self.assertEqual(created_skeleton.background_color, DEFAULT_BACKGROUND_COLOR)
        stored_skeleton: Skeleton = create_session.add.call_args.args[0]
        self.assertEqual(stored_skeleton.status, SkeletonStatus.LIVE)

    def test_patch_without_status_leaves_the_row_unchanged(self) -> None:
        """An empty partial body does not clear draft."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        bold_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Bold v1",
            slug="spotmu-bold-v1",
            template_key="spotmu_bold_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = bold_skeleton

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            patched_skeleton: SkeletonReadResponse = patch_skeleton_by_id(
                bold_skeleton.id,
                SkeletonPatchRequest(),
                fake_session,
                None,
            )

        self.assertEqual(patched_skeleton.status, SkeletonStatus.DRAFT)
        self.assertEqual(bold_skeleton.status, SkeletonStatus.DRAFT)

    def test_null_status_is_rejected(self) -> None:
        """An explicit null status is HTTP 400 and does not write."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        skeleton_patch_request: SkeletonPatchRequest = SkeletonPatchRequest.model_validate(
            {"status": None},
        )

        with self.assertRaises(HTTPException) as raised_http:
            patch_skeleton_by_id(
                paper_skeleton.id,
                skeleton_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, SKELETON_STATUS_REQUIRED_DETAIL)
        self.assertEqual(paper_skeleton.status, SkeletonStatus.DRAFT)
        fake_session.commit.assert_not_called()

    def test_unknown_status_fails_schema_validation(self) -> None:
        """A status outside draft/live never reaches the handler."""

        with self.assertRaises(ValidationError):
            SkeletonPatchRequest.model_validate({"status": "published"})

    def test_missing_skeleton_patch_returns_404(self) -> None:
        """PATCH by id raises HTTP 404 when the row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_skeleton_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            patch_skeleton_by_id(
                missing_skeleton_id,
                SkeletonPatchRequest(status=SkeletonStatus.LIVE),
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 404)


class SkeletonSpacingPatchTests(unittest.TestCase):
    """PATCH spacing round-trips; create stores 96 / 0 / 0; negatives are 400."""

    def test_round_trip_rejects_negative_and_create_reads_defaults(self) -> None:
        """A non-default triple survives GET; -1 is 400; name-only create is 96 / 0 / 0."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        current_ops_operator: MagicMock = MagicMock()
        spacing_patch: SkeletonPatchRequest = SkeletonPatchRequest(
            page_margin=120,
            element_gap=16,
            element_margin=8,
        )

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            patched_skeleton: SkeletonReadResponse = patch_skeleton_by_id(
                paper_skeleton.id,
                spacing_patch,
                fake_session,
                current_ops_operator,
            )

        self.assertEqual(patched_skeleton.page_margin, 120)
        self.assertEqual(patched_skeleton.element_gap, 16)
        self.assertEqual(patched_skeleton.element_margin, 8)
        loaded_skeleton: SkeletonReadResponse = get_skeleton_by_id(paper_skeleton.id, fake_session)
        self.assertEqual(loaded_skeleton.page_margin, 120)
        self.assertEqual(loaded_skeleton.element_gap, 16)
        self.assertEqual(loaded_skeleton.element_margin, 8)
        self.assertEqual(loaded_skeleton.status, SkeletonStatus.DRAFT)

        self._assert_negative_spacing_is_rejected(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(page_margin=-1),
            "page_margin",
        )
        self._assert_negative_spacing_is_rejected(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(element_gap=-1),
            "element_gap",
        )
        self._assert_negative_spacing_is_rejected(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(element_margin=-1),
            "element_margin",
        )
        self.assertEqual(paper_skeleton.page_margin, 120)
        self.assertEqual(paper_skeleton.element_gap, 16)
        self.assertEqual(paper_skeleton.element_margin, 8)

        create_session: MagicMock = MagicMock()
        create_session.scalars.return_value.all.return_value = []
        create_session.refresh.side_effect = _assign_persisted_timestamps
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(name="Harbor")

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            created_skeleton: SkeletonReadResponse = create_skeleton(
                skeleton_create_request,
                create_session,
                None,
            )

        self.assertEqual(created_skeleton.name, "Harbor")
        self.assertEqual(created_skeleton.page_margin, 96)
        self.assertEqual(created_skeleton.element_gap, 0)
        self.assertEqual(created_skeleton.element_margin, 0)
        self.assertEqual(created_skeleton.page_margin, DEFAULT_PAGE_MARGIN)
        self.assertEqual(created_skeleton.element_gap, DEFAULT_ELEMENT_GAP)
        self.assertEqual(created_skeleton.element_margin, DEFAULT_ELEMENT_MARGIN)

        negative_spacing_request: SkeletonCreateRequest = SkeletonCreateRequest(
            name="Night Shift",
            page_margin=-1,
            element_gap=4,
            element_margin=4,
        )
        negative_session: MagicMock = MagicMock()
        negative_session.scalars.return_value.all.return_value = ["harbor"]

        with patch(
            "app.api.v1.skeletons.commit_database_session_or_raise_conflict",
        ) as blocked_commit:
            with self.assertRaises(HTTPException) as negative_error:
                create_skeleton(negative_spacing_request, negative_session, None)

        self.assertEqual(negative_error.exception.status_code, 400)
        self.assertEqual(
            negative_error.exception.detail,
            skeleton_spacing_negative_detail("page_margin"),
        )
        blocked_commit.assert_not_called()

    def test_partial_spacing_patch_leaves_the_other_edges_alone(self) -> None:
        """Sending only element_gap does not reset page margin or element margin."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        bold_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Bold v1",
            slug="spotmu-bold-v1",
            template_key="spotmu_bold_v1",
            created_at=created_at,
        )
        bold_skeleton.page_margin = 120
        bold_skeleton.element_gap = 16
        bold_skeleton.element_margin = 8
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = bold_skeleton

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            patched_skeleton: SkeletonReadResponse = patch_skeleton_by_id(
                bold_skeleton.id,
                SkeletonPatchRequest(element_gap=4),
                fake_session,
                None,
            )

        self.assertEqual(patched_skeleton.page_margin, 120)
        self.assertEqual(patched_skeleton.element_gap, 4)
        self.assertEqual(patched_skeleton.element_margin, 8)

    def test_null_spacing_is_rejected(self) -> None:
        """An explicit null page margin is HTTP 400 and does not write."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        skeleton_patch_request: SkeletonPatchRequest = SkeletonPatchRequest.model_validate(
            {"page_margin": None},
        )

        with self.assertRaises(HTTPException) as raised_http:
            patch_skeleton_by_id(
                paper_skeleton.id,
                skeleton_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            skeleton_spacing_required_detail("page_margin"),
        )
        self.assertEqual(paper_skeleton.page_margin, DEFAULT_PAGE_MARGIN)
        fake_session.commit.assert_not_called()

    def _assert_negative_spacing_is_rejected(
        self,
        skeleton: Skeleton,
        fake_session: MagicMock,
        skeleton_patch_request: SkeletonPatchRequest,
        field_name: str,
    ) -> None:
        """PATCH of -1 on one spacing field is HTTP 400 and does not commit."""

        with self.assertRaises(HTTPException) as raised_http:
            patch_skeleton_by_id(
                skeleton.id,
                skeleton_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            skeleton_spacing_negative_detail(field_name),
        )
        fake_session.commit.assert_not_called()


class SkeletonBackgroundPatchTests(unittest.TestCase):
    """Each background kind round-trips. Live color needs a hex. Draft picture may be empty."""

    def test_each_kind_round_trips(self) -> None:
        """Color, gradient, and picture survive PATCH and GET."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        gradient_payload: dict[str, object] = {
            "angle_deg": 180,
            "stops": [
                {"offset": 0, "color": "#112233"},
                {"offset": 1, "color": "#F6F1E8"},
            ],
        }

        self._patch(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(background_color="#AABBCC"),
        )
        color_skeleton: SkeletonReadResponse = get_skeleton_by_id(paper_skeleton.id, fake_session)
        self.assertEqual(color_skeleton.background_kind, BackgroundKind.COLOR)
        self.assertEqual(color_skeleton.background_color, "#AABBCC")

        self._patch(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(
                background_kind=BackgroundKind.GRADIENT,
                background_gradient=gradient_payload,
            ),
        )
        gradient_skeleton: SkeletonReadResponse = get_skeleton_by_id(
            paper_skeleton.id,
            fake_session,
        )
        self.assertEqual(gradient_skeleton.background_kind, BackgroundKind.GRADIENT)
        self.assertIsNotNone(gradient_skeleton.background_gradient)

        if gradient_skeleton.background_gradient is None:
            self.fail("gradient payload is missing")

        self.assertEqual(gradient_skeleton.background_gradient.angle_deg, 180)
        self.assertEqual(len(gradient_skeleton.background_gradient.stops), 2)
        self.assertEqual(gradient_skeleton.background_gradient.stops[0].color, "#112233")
        self.assertEqual(gradient_skeleton.background_gradient.stops[1].color, "#F6F1E8")

        self._patch(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref="backgrounds/harbor.png",
            ),
        )
        picture_skeleton: SkeletonReadResponse = get_skeleton_by_id(
            paper_skeleton.id,
            fake_session,
        )
        self.assertEqual(picture_skeleton.background_kind, BackgroundKind.PICTURE)
        self.assertEqual(picture_skeleton.background_asset_ref, "backgrounds/harbor.png")

    def test_texture_kind_is_rejected_on_write(self) -> None:
        """Create and patch refuse background kind texture."""

        with self.assertRaises(ValidationError):
            SkeletonPatchRequest.model_validate({"background_kind": "texture"})

        with self.assertRaises(ValidationError):
            SkeletonCreateRequest.model_validate(
                {
                    "name": "Grain",
                    "background_kind": "texture",
                    "background_asset_ref": "textures/grain.jpeg",
                },
            )

    def test_live_color_with_blank_color_is_rejected(self) -> None:
        """A Live color skeleton cannot clear its color, including by becoming Live."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        live_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        live_skeleton.status = SkeletonStatus.LIVE
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = live_skeleton

        self._assert_background_rejected(
            live_skeleton,
            fake_session,
            SkeletonPatchRequest(background_color="   "),
            LIVE_COLOR_PAYLOAD_DETAIL,
        )
        self.assertEqual(live_skeleton.background_color, DEFAULT_BACKGROUND_COLOR)
        self._assert_background_rejected(
            live_skeleton,
            fake_session,
            SkeletonPatchRequest.model_validate({"background_color": None}),
            LIVE_COLOR_PAYLOAD_DETAIL,
        )
        self.assertEqual(live_skeleton.status, SkeletonStatus.LIVE)

        draft_skeleton: Skeleton = _skeleton_row(
            name="Harbor",
            slug="harbor",
            template_key=None,
            created_at=created_at,
        )
        draft_skeleton.background_color = None
        fake_session.get.return_value = draft_skeleton
        self._assert_background_rejected(
            draft_skeleton,
            fake_session,
            SkeletonPatchRequest(status=SkeletonStatus.LIVE),
            LIVE_COLOR_PAYLOAD_DETAIL,
        )
        self.assertEqual(draft_skeleton.status, SkeletonStatus.DRAFT)
        self.assertIsNone(draft_skeleton.background_color)

    def test_draft_picture_with_null_ref_saves(self) -> None:
        """A Draft picture may keep a null asset ref."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        skeleton_patch_request: SkeletonPatchRequest = SkeletonPatchRequest.model_validate(
            {"background_kind": "picture", "background_asset_ref": None},
        )

        patched_skeleton: SkeletonReadResponse = self._patch(
            paper_skeleton,
            fake_session,
            skeleton_patch_request,
        )
        loaded_skeleton: SkeletonReadResponse = get_skeleton_by_id(paper_skeleton.id, fake_session)

        self.assertEqual(patched_skeleton.background_kind, BackgroundKind.PICTURE)
        self.assertIsNone(patched_skeleton.background_asset_ref)
        self.assertEqual(patched_skeleton.status, SkeletonStatus.DRAFT)
        self.assertEqual(loaded_skeleton.background_kind, BackgroundKind.PICTURE)
        self.assertIsNone(loaded_skeleton.background_asset_ref)

    def test_name_only_create_stores_paper_background(self) -> None:
        """Create stores color, paper #F6F1E8, and null gradient and asset ref."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        fake_session.refresh.side_effect = _assign_persisted_timestamps
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(name="Harbor")

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            created_skeleton: SkeletonReadResponse = create_skeleton(
                skeleton_create_request,
                fake_session,
                None,
            )

        self.assertEqual(created_skeleton.background_kind, BackgroundKind.COLOR)
        self.assertEqual(created_skeleton.background_color, "#F6F1E8")
        self.assertEqual(created_skeleton.background_color, DEFAULT_BACKGROUND_COLOR)
        self.assertIsNone(created_skeleton.background_gradient)
        self.assertIsNone(created_skeleton.background_asset_ref)

    def test_invalid_background_payloads_are_rejected(self) -> None:
        """Bad hex, gradient, and asset paths are 400. Draft may omit a gradient."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        not_hex: SkeletonPatchRequest = SkeletonPatchRequest(background_color="zzzzzz")
        parent_path: SkeletonPatchRequest = SkeletonPatchRequest(
            background_asset_ref="../secret.png",
        )
        remote_path: SkeletonPatchRequest = SkeletonPatchRequest(
            background_asset_ref="https://example.com/a.png",
        )
        one_stop: SkeletonPatchRequest = SkeletonPatchRequest(
            background_kind=BackgroundKind.GRADIENT,
            background_gradient={
                "angle_deg": 90,
                "stops": [{"offset": 0, "color": "#112233"}],
            },
        )

        self._assert_background_rejected(
            paper_skeleton,
            fake_session,
            not_hex,
            BACKGROUND_COLOR_DETAIL,
        )
        self._assert_background_rejected(
            paper_skeleton,
            fake_session,
            parent_path,
            BACKGROUND_ASSET_REF_DETAIL,
        )
        self._assert_background_rejected(
            paper_skeleton,
            fake_session,
            remote_path,
            BACKGROUND_ASSET_REF_DETAIL,
        )
        self._assert_background_rejected(
            paper_skeleton,
            fake_session,
            one_stop,
            GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
        )
        self.assertEqual(paper_skeleton.background_kind, BackgroundKind.COLOR)
        self.assertEqual(paper_skeleton.background_color, DEFAULT_BACKGROUND_COLOR)

        paper_skeleton.status = SkeletonStatus.LIVE
        self._assert_background_rejected(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(background_kind=BackgroundKind.PICTURE),
            LIVE_ASSET_PAYLOAD_DETAIL,
        )
        self.assertEqual(paper_skeleton.background_kind, BackgroundKind.COLOR)

        paper_skeleton.status = SkeletonStatus.DRAFT
        empty_gradient: SkeletonReadResponse = self._patch(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest.model_validate(
                {"background_kind": "gradient", "background_gradient": None},
            ),
        )
        self.assertEqual(empty_gradient.background_kind, BackgroundKind.GRADIENT)
        self.assertIsNone(empty_gradient.background_gradient)
        self.assertEqual(empty_gradient.status, SkeletonStatus.DRAFT)

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
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        patched_skeleton: SkeletonReadResponse = self._patch(
            paper_skeleton,
            fake_session,
            SkeletonPatchRequest(background_color="4a4a4a"),
        )

        self.assertEqual(patched_skeleton.background_color, "#4A4A4A")

    def test_gradient_patch_names_the_problem(self) -> None:
        """A bad angle, offset, or stop color is a 400 that says how to fix it."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        bad_angle: SkeletonPatchRequest = SkeletonPatchRequest(
            background_gradient={
                "angle_deg": 400,
                "stops": [
                    {"offset": 0, "color": "#112233"},
                    {"offset": 1, "color": "#AABBCC"},
                ],
            },
        )
        bad_offset: SkeletonPatchRequest = SkeletonPatchRequest(
            background_gradient={
                "angle_deg": 180,
                "stops": [
                    {"offset": 0, "color": "#112233"},
                    {"offset": 1.5, "color": "#AABBCC"},
                ],
            },
        )
        bad_color: SkeletonPatchRequest = SkeletonPatchRequest(
            background_gradient={
                "angle_deg": 180,
                "stops": [
                    {"offset": 0, "color": "#112233"},
                    {"offset": 1, "color": "not-a-color"},
                ],
            },
        )

        self._assert_background_rejected(
            paper_skeleton,
            fake_session,
            bad_angle,
            GRADIENT_ANGLE_DETAIL,
        )
        self._assert_background_rejected(
            paper_skeleton,
            fake_session,
            bad_offset,
            GRADIENT_OFFSET_DETAIL,
        )
        self._assert_background_rejected(
            paper_skeleton,
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
        skeleton: Skeleton,
        fake_session: MagicMock,
        skeleton_patch_request: SkeletonPatchRequest,
    ) -> SkeletonReadResponse:
        """Apply a patch with the commit helper stubbed."""

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            patched_skeleton: SkeletonReadResponse = patch_skeleton_by_id(
                skeleton.id,
                skeleton_patch_request,
                fake_session,
                None,
            )

        return patched_skeleton

    def _assert_background_rejected(
        self,
        skeleton: Skeleton,
        fake_session: MagicMock,
        skeleton_patch_request: SkeletonPatchRequest,
        expected_detail: str,
    ) -> None:
        """PATCH is HTTP 400 and does not commit."""

        with self.assertRaises(HTTPException) as raised_http:
            patch_skeleton_by_id(
                skeleton.id,
                skeleton_patch_request,
                fake_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, expected_detail)
        fake_session.commit.assert_not_called()


class SkeletonElementApiTests(unittest.TestCase):
    """Element create, order, band move, and carousel rejection."""

    def test_create_clear_text_and_image_then_move_band(self) -> None:
        """A clear text element and an image reload in order, then one moves."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_skeleton)
        text_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
            name="Title",
            band=SkeletonElementBand.TOP,
            content_kind=SkeletonElementContentKind.TEXT,
            text_source=SkeletonElementTextSource.TITLE,
            font_family="DejaVu Sans",
            font_size=32,
            font_color="#112233",
            alignment="left",
        )
        image_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
            name="Image",
            band=SkeletonElementBand.TOP,
            content_kind=SkeletonElementContentKind.IMAGE,
            image_asset_ref="logos/mark.png",
        )

        with patch(
            "app.api.v1.skeleton_elements.commit_database_session_or_raise_conflict",
        ):
            text_element: SkeletonElementReadResponse = create_skeleton_element(
                paper_skeleton.id,
                text_request,
                element_session,
                None,
            )
            image_element: SkeletonElementReadResponse = create_skeleton_element(
                paper_skeleton.id,
                image_request,
                element_session,
                None,
            )

        self.assertIsNone(text_element.rectangle_color)
        self.assertEqual(text_element.name, "Title")
        self.assertEqual(text_element.text_source, SkeletonElementTextSource.TITLE)
        self.assertFalse(text_element.bold)
        self.assertEqual(text_element.sort_order, 0)
        self.assertEqual(image_element.image_asset_ref, "logos/mark.png")
        self.assertEqual(image_element.name, "Image")
        self.assertIsNone(image_element.text_source)
        self.assertEqual(image_element.sort_order, 1)
        loaded_skeleton: SkeletonReadResponse = get_skeleton_by_id(
            paper_skeleton.id,
            element_session,
        )
        loaded_pairs: list[tuple[str, str, int]] = [
            (element.band.value, element.content_kind.value, element.sort_order)
            for element in loaded_skeleton.elements
        ]

        self.assertEqual(
            loaded_pairs,
            [("top", "text", 0), ("top", "image", 1)],
        )

        with patch(
            "app.api.v1.skeleton_elements.commit_database_session_or_raise_conflict",
        ):
            moved_element: SkeletonElementReadResponse = patch_skeleton_element(
                paper_skeleton.id,
                image_element.id,
                SkeletonElementPatchRequest(band=SkeletonElementBand.MIDDLE),
                element_session,
                None,
            )

        self.assertEqual(moved_element.band, SkeletonElementBand.MIDDLE)
        self.assertEqual(moved_element.sort_order, 0)
        self.assertEqual(moved_element.name, "Image")
        reloaded_skeleton: SkeletonReadResponse = get_skeleton_by_id(
            paper_skeleton.id,
            element_session,
        )
        reloaded_pairs: list[tuple[str, str, int]] = [
            (element.band.value, element.content_kind.value, element.sort_order)
            for element in reloaded_skeleton.elements
        ]

        self.assertEqual(
            reloaded_pairs,
            [("top", "text", 0), ("middle", "image", 0)],
        )

    def test_blank_name_is_rejected_and_a_trimmed_name_is_stored(self) -> None:
        """Create and patch refuse a blank name. Surrounding spaces are dropped."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_skeleton)
        name_application: FastAPI = FastAPI()

        @name_application.post("/elements")
        def create_named_element(
            skeleton_element_create_request: SkeletonElementCreateRequest,
        ) -> dict[str, str]:

            stored_name: dict[str, str] = {"name": skeleton_element_create_request.name}

            return stored_name

        @name_application.patch("/elements")
        def patch_named_element(
            skeleton_element_patch_request: SkeletonElementPatchRequest,
        ) -> dict[str, str | None]:

            stored_name: dict[str, str | None] = {"name": skeleton_element_patch_request.name}

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
        self.assertIn(SKELETON_ELEMENT_NAME_REQUIRED_DETAIL, blank_response.text)
        self.assertEqual(trimmed_response.status_code, 200)
        self.assertEqual(trimmed_response.json()["name"], "Subject")
        self.assertEqual(cleared_response.status_code, 422)
        self.assertIn(SKELETON_ELEMENT_NAME_REQUIRED_DETAIL, cleared_response.text)
        self.assertEqual(null_response.status_code, 422)
        self.assertIn(SKELETON_ELEMENT_NAME_REQUIRED_DETAIL, null_response.text)
        self.assertEqual(omitted_response.status_code, 200)
        self.assertIsNone(omitted_response.json()["name"])

        with patch(
            "app.api.v1.skeleton_elements.commit_database_session_or_raise_conflict",
        ):
            created_element: SkeletonElementReadResponse = create_skeleton_element(
                paper_skeleton.id,
                SkeletonElementCreateRequest(
                    name="  Body  ",
                    band=SkeletonElementBand.TOP,
                    content_kind=SkeletonElementContentKind.TEXT,
                    text_source=SkeletonElementTextSource.TITLE,
                    font_family="DejaVu Sans",
                    font_size=32,
                    font_color="#112233",
                    alignment="left",
                ),
                element_session,
                None,
            )
            renamed_element: SkeletonElementReadResponse = patch_skeleton_element(
                paper_skeleton.id,
                created_element.id,
                SkeletonElementPatchRequest(name="  Caption  "),
                element_session,
                None,
            )

        self.assertEqual(created_element.name, "Body")
        self.assertEqual(renamed_element.name, "Caption")

    def test_unknown_text_source_and_coordinates_are_rejected(self) -> None:
        """Carousels outside the four Spotmu keys, and x/y/width, never persist."""

        with self.assertRaises(ValidationError):
            SkeletonElementCreateRequest.model_validate(
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
            SkeletonElementCreateRequest.model_validate(
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
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_skeleton)
        gif_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
            name="Image",
            band=SkeletonElementBand.BOTTOM,
            content_kind=SkeletonElementContentKind.IMAGE,
            image_asset_ref="logos/mark.gif",
        )

        with self.assertRaises(HTTPException) as raised_gif:
            create_skeleton_element(paper_skeleton.id, gif_request, element_session, None)

        self.assertEqual(raised_gif.exception.status_code, 400)
        self.assertEqual(raised_gif.exception.detail, SKELETON_ELEMENT_IMAGE_REF_DETAIL)
        self.assertEqual(paper_skeleton.elements, [])
        parent_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
            name="Image",
            band=SkeletonElementBand.BOTTOM,
            content_kind=SkeletonElementContentKind.IMAGE,
            image_asset_ref="../secret.png",
        )

        with self.assertRaises(HTTPException) as raised_parent:
            create_skeleton_element(
                paper_skeleton.id,
                parent_request,
                element_session,
                None,
            )

        self.assertEqual(raised_parent.exception.status_code, 400)
        self.assertEqual(paper_skeleton.elements, [])

    def test_image_element_rejects_a_text_source(self) -> None:
        """An image row cannot keep one of the Spotmu text sources."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_skeleton)
        image_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
            name="Image",
            band=SkeletonElementBand.TOP,
            content_kind=SkeletonElementContentKind.IMAGE,
            text_source=SkeletonElementTextSource.TITLE,
            image_asset_ref="logos/mark.jpg",
        )

        with self.assertRaises(HTTPException) as raised_http:
            create_skeleton_element(
                paper_skeleton.id,
                image_request,
                element_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            SKELETON_ELEMENT_TEXT_SOURCE_FORBIDDEN_DETAIL,
        )
        self.assertEqual(paper_skeleton.elements, [])

    def test_text_element_may_omit_text_source(self) -> None:
        """A text row can be stored with a null text source."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_skeleton)
        text_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
            name="Headline",
            band=SkeletonElementBand.TOP,
            content_kind=SkeletonElementContentKind.TEXT,
            font_family="DejaVu Sans",
            font_size=32,
            font_color="#112233",
            alignment=SkeletonElementAlignment.LEFT,
        )

        with patch(
            "app.api.v1.skeleton_elements.commit_database_session_or_raise_conflict",
        ):
            created_element: SkeletonElementReadResponse = create_skeleton_element(
                paper_skeleton.id,
                text_request,
                element_session,
                None,
            )

        self.assertEqual(created_element.name, "Headline")
        self.assertIsNone(created_element.text_source)
        self.assertEqual(created_element.content_kind, SkeletonElementContentKind.TEXT)
        self.assertEqual(len(paper_skeleton.elements), 1)

    def test_delete_compacts_the_band(self) -> None:
        """Deleting the first element renumbers the remaining one to 0."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_skeleton)
        first_request: SkeletonElementCreateRequest = _text_element_request(
            SkeletonElementTextSource.TITLE,
        )
        second_request: SkeletonElementCreateRequest = _text_element_request(
            SkeletonElementTextSource.CANONICAL_URL,
        )

        with patch(
            "app.api.v1.skeleton_elements.commit_database_session_or_raise_conflict",
        ):
            first_element: SkeletonElementReadResponse = create_skeleton_element(
                paper_skeleton.id,
                first_request,
                element_session,
                None,
            )
            second_element: SkeletonElementReadResponse = create_skeleton_element(
                paper_skeleton.id,
                second_request,
                element_session,
                None,
            )
            delete_skeleton_element(
                paper_skeleton.id,
                first_element.id,
                element_session,
                None,
            )

        loaded_skeleton: SkeletonReadResponse = get_skeleton_by_id(
            paper_skeleton.id,
            element_session,
        )

        self.assertEqual(len(loaded_skeleton.elements), 1)
        self.assertEqual(loaded_skeleton.elements[0].id, second_element.id)
        self.assertEqual(loaded_skeleton.elements[0].sort_order, 0)
        self.assertEqual(
            loaded_skeleton.elements[0].text_source,
            SkeletonElementTextSource.CANONICAL_URL,
        )

    def test_missing_element_returns_404(self) -> None:
        """PATCH for an id that is not on the skeleton is HTTP 404."""

        created_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        element_session: _ElementMemorySession = _ElementMemorySession(paper_skeleton)
        missing_element_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            patch_skeleton_element(
                paper_skeleton.id,
                missing_element_id,
                SkeletonElementPatchRequest(band=SkeletonElementBand.BOTTOM),
                element_session,
                None,
            )

        self.assertEqual(raised_http.exception.status_code, 404)
        self.assertIn(SKELETON_ELEMENT_NOT_FOUND_DETAIL, str(raised_http.exception.detail))


class SkeletonDuplicateTests(unittest.TestCase):
    """Duplicate copies a Live skeleton into a new Draft and leaves the carousel."""

    def test_duplicate_live_skeleton_with_gradient_and_two_elements(self) -> None:
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
        source_skeleton: Skeleton = _skeleton_row(
            name="Harbor Night",
            slug="harbor-night",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        source_skeleton.status = SkeletonStatus.LIVE
        source_skeleton.page_margin = 120
        source_skeleton.element_gap = 16
        source_skeleton.element_margin = 8
        source_skeleton.background_kind = BackgroundKind.GRADIENT
        source_skeleton.background_color = None
        source_skeleton.background_gradient = source_gradient
        source_skeleton.background_asset_ref = None
        source_skeleton.updated_at = source_updated_at
        text_element: SkeletonElement = SkeletonElement(
            id=uuid.uuid4(),
            skeleton_id=source_skeleton.id,
            band=SkeletonElementBand.TOP,
            sort_order=0,
            content_kind=SkeletonElementContentKind.TEXT,
            name="Title",
            rectangle_color=None,
            text_source=SkeletonElementTextSource.TITLE,
            font_family="DejaVu Sans",
            font_size=32,
            font_color="#112233",
            bold=True,
            italic=False,
            underline=False,
            strikethrough=False,
            font_weight=700,
            alignment=SkeletonElementAlignment.LEFT,
            image_asset_ref=None,
            created_at=created_at,
            updated_at=created_at,
        )
        image_element: SkeletonElement = SkeletonElement(
            id=uuid.uuid4(),
            skeleton_id=source_skeleton.id,
            band=SkeletonElementBand.BOTTOM,
            sort_order=0,
            content_kind=SkeletonElementContentKind.IMAGE,
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
        source_skeleton.elements.append(text_element)
        source_skeleton.elements.append(image_element)
        source_element_ids: list[uuid.UUID] = [text_element.id, image_element.id]
        duplicate_session: _DuplicateMemorySession = _DuplicateMemorySession(
            source_skeleton,
            ["harbor-night"],
        )
        operator_id: uuid.UUID = uuid.uuid4()
        current_ops_operator: MagicMock = MagicMock()
        current_ops_operator.id = operator_id

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            copied_skeleton: SkeletonReadResponse = duplicate_skeleton_by_id(
                source_skeleton.id,
                duplicate_session,
                current_ops_operator,
            )

        self.assertEqual(source_skeleton.status, SkeletonStatus.LIVE)
        self.assertEqual(source_skeleton.updated_at, source_updated_at)
        self.assertEqual(source_skeleton.template_key, "spotmu_paper_v1")
        self.assertEqual(
            [element.id for element in source_skeleton.elements],
            source_element_ids,
        )
        self.assertNotEqual(copied_skeleton.id, source_skeleton.id)
        self.assertEqual(copied_skeleton.status, SkeletonStatus.DRAFT)
        self.assertIsNone(copied_skeleton.template_key)
        self.assertEqual(copied_skeleton.name, "Copy of Harbor Night")
        self.assertEqual(copied_skeleton.slug, "copy-of-harbor-night")
        self.assertEqual(copied_skeleton.page_margin, 120)
        self.assertEqual(copied_skeleton.element_gap, 16)
        self.assertEqual(copied_skeleton.element_margin, 8)
        self.assertEqual(copied_skeleton.background_kind, BackgroundKind.GRADIENT)
        self.assertIsNotNone(copied_skeleton.background_gradient)
        self.assertEqual(copied_skeleton.background_gradient.angle_deg, 180)
        self.assertEqual(copied_skeleton.background_gradient.stops[0].color, "#112233")
        self.assertEqual(copied_skeleton.background_gradient.stops[1].color, "#F6F1E8")
        stored_copies: list[Skeleton] = [
            added_row
            for added_row in duplicate_session.added
            if isinstance(added_row, Skeleton)
        ]
        self.assertEqual(len(stored_copies), 1)
        self.assertEqual(stored_copies[0].background_gradient, source_gradient)
        self.assertIsNot(stored_copies[0].background_gradient, source_gradient)
        self.assertEqual(copied_skeleton.created_by, operator_id)
        self.assertEqual(len(copied_skeleton.elements), 2)
        copied_element_ids: list[uuid.UUID] = [
            element.id for element in copied_skeleton.elements
        ]
        self.assertEqual(len(set(copied_element_ids)), 2)
        self.assertTrue(set(copied_element_ids).isdisjoint(source_element_ids))
        self.assertEqual(copied_skeleton.elements[0].name, "Title")
        self.assertEqual(copied_skeleton.elements[0].band, SkeletonElementBand.TOP)
        self.assertEqual(copied_skeleton.elements[0].sort_order, 0)
        self.assertEqual(
            copied_skeleton.elements[0].text_source,
            SkeletonElementTextSource.TITLE,
        )
        self.assertEqual(copied_skeleton.elements[0].font_weight, 700)
        self.assertIsNone(copied_skeleton.elements[0].rectangle_color)
        self.assertEqual(copied_skeleton.elements[1].name, "Image")
        self.assertEqual(copied_skeleton.elements[1].band, SkeletonElementBand.BOTTOM)
        self.assertEqual(copied_skeleton.elements[1].sort_order, 0)
        self.assertEqual(copied_skeleton.elements[1].image_asset_ref, "logos/mark.png")
        self.assertEqual(copied_skeleton.elements[1].rectangle_color, "#AABBCC")
        self.assertIsNone(copied_skeleton.elements[1].text_source)
        reloaded_copy: SkeletonReadResponse = get_skeleton_by_id(
            copied_skeleton.id,
            duplicate_session,
        )
        self.assertEqual(reloaded_copy.status, SkeletonStatus.DRAFT)
        self.assertEqual(
            [element.id for element in reloaded_copy.elements],
            copied_element_ids,
        )

    def test_missing_skeleton_duplicate_returns_404(self) -> None:
        """POST duplicate raises HTTP 404 when the carousel row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_skeleton_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            duplicate_skeleton_by_id(missing_skeleton_id, fake_session, None)

        self.assertEqual(raised_http.exception.status_code, 404)
        fake_session.add.assert_not_called()


class SkeletonSlugTests(unittest.TestCase):
    """Slug derivation matches the campaign hyphen rules with a skeleton fallback."""

    def test_slugify_skeleton_name(self) -> None:
        """Spaces and punctuation become a single hyphenated slug."""

        skeleton_slug: str = slugify_skeleton_name("  Spotmu Paper v1! ")

        self.assertEqual(skeleton_slug, "spotmu-paper-v1")

    def test_slugify_falls_back_when_name_has_no_letters(self) -> None:
        """Punctuation-only names use the skeleton fallback slug."""

        skeleton_slug: str = slugify_skeleton_name("!!!")

        self.assertEqual(skeleton_slug, "skeleton")

    def test_allocate_unique_skeleton_slug_appends_suffix(self) -> None:
        """A taken slug gets -2."""

        allocated_slug: str = allocate_unique_skeleton_slug(
            "harbor",
            {"harbor"},
        )

        self.assertEqual(allocated_slug, "harbor-2")


class _DuplicateMemorySession:
    """In-memory carousel skeleton plus the Draft created by duplicate."""

    def __init__(self, skeleton: Skeleton, taken_slugs: list[str]) -> None:

        self.skeleton: Skeleton = skeleton
        self.taken_slugs: list[str] = taken_slugs
        self.added: list[Skeleton | SkeletonElement] = []

    def get(self, model: type[object], key: uuid.UUID) -> Skeleton | None:
        """Return the carousel skeleton or a skeleton this session has added."""

        if model is not Skeleton:

            return None

        if key == self.skeleton.id:

            return self.skeleton

        for added_row in self.added:

            if isinstance(added_row, Skeleton) and added_row.id == key:

                return added_row

        return None

    def scalars(self, statement: object = None) -> MagicMock:
        """Return the slugs already stored, for the unique-slug helper."""

        _ = statement
        slug_result: MagicMock = MagicMock()
        slug_result.all.return_value = list(self.taken_slugs)

        return slug_result

    def add(self, row: Skeleton | SkeletonElement) -> None:
        """Remember a pending skeleton or element."""

        self.added.append(row)

    def flush(self) -> None:
        """Assign ids the database would assign before elements are copied."""

        for added_row in self.added:
            _assign_new_row_identity(added_row)

    def refresh(self, row: Skeleton | SkeletonElement) -> None:
        """Fill ids and timestamps, including elements on a refreshed skeleton."""

        _assign_new_row_identity(row)

        if isinstance(row, Skeleton):

            for element in row.elements:
                _assign_new_row_identity(element)


def _assign_new_row_identity(row: Skeleton | SkeletonElement) -> None:
    """Fill a new row's id and timestamps once. Leave existing values."""

    persisted_at: datetime = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)

    if row.id is None:
        row.id = uuid.uuid4()

    if row.created_at is None:
        row.created_at = persisted_at
        row.updated_at = persisted_at


class _EmptyQueryResult:
    """Stand-in for ``session.execute(...).all()`` when the test has no slides."""

    def all(self) -> list[object]:
        """Return no rows."""

        return []


class _ElementMemorySession:
    """In-memory skeleton lookup for element handlers. Not a database."""

    def __init__(self, skeleton: Skeleton) -> None:

        self.skeleton: Skeleton = skeleton

    def get(self, model: type[object], key: uuid.UUID) -> Skeleton | SkeletonElement | None:
        """Return the skeleton or one of its elements."""

        if model is Skeleton:

            if key == self.skeleton.id:

                return self.skeleton

            return None

        if model is SkeletonElement:

            for element in self.skeleton.elements:

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
        """Text sync finds no slides. These tests do not store carousels."""

        _ = statement

        return _EmptyQueryResult()

    def refresh(self, row: Skeleton | SkeletonElement) -> None:
        """Fill id and timestamps the way a Postgres refresh would."""

        persisted_at: datetime = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)

        if row.id is None:
            row.id = uuid.uuid4()

        if row.created_at is None:
            row.created_at = persisted_at
            row.updated_at = persisted_at


def _text_element_request(
    text_source: SkeletonElementTextSource,
) -> SkeletonElementCreateRequest:
    """Build a clear text element on the top band."""

    text_request: SkeletonElementCreateRequest = SkeletonElementCreateRequest(
        name=text_source.value,
        band=SkeletonElementBand.TOP,
        content_kind=SkeletonElementContentKind.TEXT,
        text_source=text_source,
        font_family="DejaVu Sans",
        font_size=28,
        font_color="#112233",
        alignment="center",
    )

    return text_request


class SkeletonCreatePresetTests(unittest.TestCase):
    """Create stores the frame and elements together, or stores nothing."""

    def test_create_stores_frame_and_elements(self) -> None:
        """Live spacing, a text element, and an image element come back together."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        fake_session.refresh.side_effect = _assign_persisted_timestamps
        fake_session.flush.side_effect = _assign_skeleton_id_on_flush(fake_session)
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(
            name="Harbor",
            status=SkeletonStatus.LIVE,
            page_margin=40,
            element_gap=8,
            element_margin=4,
            background_kind=BackgroundKind.COLOR,
            background_color="#112233",
            elements=[
                SkeletonElementCreateRequest(
                    name="Title",
                    band=SkeletonElementBand.TOP,
                    content_kind=SkeletonElementContentKind.TEXT,
                    text_source=SkeletonElementTextSource.TITLE,
                    font_family="DejaVu Sans",
                    font_size=32,
                    font_color="#112233",
                    alignment=SkeletonElementAlignment.CENTER,
                ),
                SkeletonElementCreateRequest(
                    name="Image",
                    band=SkeletonElementBand.BOTTOM,
                    content_kind=SkeletonElementContentKind.IMAGE,
                    image_asset_ref="logos/mark.png",
                ),
            ],
        )

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            created_skeleton: SkeletonReadResponse = create_skeleton(
                skeleton_create_request,
                fake_session,
                None,
            )

        self.assertEqual(created_skeleton.status, SkeletonStatus.LIVE)
        self.assertEqual(created_skeleton.page_margin, 40)
        self.assertEqual(created_skeleton.element_gap, 8)
        self.assertEqual(created_skeleton.element_margin, 4)
        self.assertEqual(created_skeleton.background_color, "#112233")
        self.assertEqual(len(created_skeleton.elements), 2)
        self.assertEqual(created_skeleton.elements[0].band, SkeletonElementBand.TOP)
        self.assertEqual(created_skeleton.elements[0].text_source, SkeletonElementTextSource.TITLE)
        self.assertEqual(created_skeleton.elements[1].band, SkeletonElementBand.BOTTOM)
        self.assertEqual(created_skeleton.elements[1].image_asset_ref, "logos/mark.png")
        self.assertNotEqual(created_skeleton.elements[0].id, created_skeleton.elements[1].id)

    def test_live_create_with_blank_color_stores_nothing(self) -> None:
        """A Live color skeleton with a blank color is 400 and is not committed."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(
            name="Harbor",
            status=SkeletonStatus.LIVE,
            background_color="",
        )

        with patch(
            "app.api.v1.skeletons.commit_database_session_or_raise_conflict",
        ) as blocked_commit:
            with self.assertRaises(HTTPException) as create_error:
                create_skeleton(skeleton_create_request, fake_session, None)

        self.assertEqual(create_error.exception.status_code, 400)
        self.assertEqual(create_error.exception.detail, LIVE_COLOR_PAYLOAD_DETAIL)
        blocked_commit.assert_not_called()
        fake_session.add.assert_not_called()

    def test_invalid_element_stores_nothing(self) -> None:
        """A text element without a family is 400 and is not committed."""

        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = []
        skeleton_create_request: SkeletonCreateRequest = SkeletonCreateRequest(
            name="Harbor",
            elements=[
                SkeletonElementCreateRequest(
                    name="Title",
                    band=SkeletonElementBand.MIDDLE,
                    content_kind=SkeletonElementContentKind.TEXT,
                    text_source=SkeletonElementTextSource.TITLE,
                    font_size=32,
                    font_color="#112233",
                    alignment=SkeletonElementAlignment.LEFT,
                ),
            ],
        )

        with patch(
            "app.api.v1.skeletons.commit_database_session_or_raise_conflict",
        ) as blocked_commit:
            with self.assertRaises(HTTPException) as create_error:
                create_skeleton(skeleton_create_request, fake_session, None)

        self.assertEqual(create_error.exception.status_code, 400)
        blocked_commit.assert_not_called()
        fake_session.add.assert_not_called()


class SkeletonDeleteTests(unittest.TestCase):
    """Delete removes a skeleton. Elements cascade. Other references block it."""

    def test_delete_removes_the_skeleton(self) -> None:
        """DELETE hands the row to the session and commits."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        fake_session.scalar.return_value = 0

        with patch("app.api.v1.skeletons.commit_database_session_or_raise_conflict"):
            delete_skeleton_by_id(paper_skeleton.id, fake_session, None)

        fake_session.delete.assert_called_once_with(paper_skeleton)

    def test_source_reference_blocks_delete(self) -> None:
        """A carousel that stores this skeleton refuses the delete."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton
        fake_session.scalar.return_value = 1

        with self.assertRaises(HTTPException) as delete_error:
            delete_skeleton_by_id(paper_skeleton.id, fake_session, None)

        self.assertEqual(delete_error.exception.status_code, 409)
        self.assertIn("still referenced", delete_error.exception.detail)
        self.assertIn("carousels", delete_error.exception.detail)
        fake_session.delete.assert_not_called()

    def test_missing_skeleton_delete_returns_404(self) -> None:
        """DELETE raises HTTP 404 when the row is absent."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_skeleton_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as delete_error:
            delete_skeleton_by_id(missing_skeleton_id, fake_session, None)

        self.assertEqual(delete_error.exception.status_code, 404)
        fake_session.delete.assert_not_called()

    def test_only_elements_and_carousels_reference_skeletons(self) -> None:
        """Elements cascade. Carousels and campaigns restrict by row. No other table points at skeletons."""

        _ = app.models
        self.assertEqual(unexpected_skeleton_reference_tables(), [])
        element_actions: set[str] = {
            (foreign_key.ondelete or "").upper()
            for foreign_key in SkeletonElement.__table__.foreign_keys
            if foreign_key.column.table.name == "skeletons"
        }
        source_actions: set[str] = {
            (foreign_key.ondelete or "").upper()
            for foreign_key in Carousel.__table__.c.skeleton_id.foreign_keys
        }
        self.assertEqual(element_actions, {"CASCADE"})
        self.assertEqual(source_actions, {"RESTRICT"})
        campaign_actions: set[str] = {
            (foreign_key.ondelete or "").upper()
            for foreign_key in Campaign.__table__.c.skeleton_id.foreign_keys
        }
        self.assertEqual(campaign_actions, {"RESTRICT"})

    def test_other_reference_blocks_delete(self) -> None:
        """A non-cascade foreign key refuses the delete and leaves the row."""

        created_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        paper_skeleton: Skeleton = _skeleton_row(
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            template_key="spotmu_paper_v1",
            created_at=created_at,
        )
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = paper_skeleton

        with patch(
            "app.api.v1.skeletons.skeleton_delete_reference_blockers",
            return_value=["campaigns"],
        ):
            with self.assertRaises(HTTPException) as delete_error:
                delete_skeleton_by_id(paper_skeleton.id, fake_session, None)

        self.assertEqual(delete_error.exception.status_code, 409)
        self.assertIn("still referenced", delete_error.exception.detail)
        self.assertIn("campaigns", delete_error.exception.detail)
        fake_session.delete.assert_not_called()


def _assign_skeleton_id_on_flush(fake_session: MagicMock):
    """Give the pending skeleton an id the way a database flush would."""

    def assign_skeleton_id() -> None:

        pending_skeleton: Skeleton = fake_session.add.call_args_list[0].args[0]

        if pending_skeleton.id is None:
            pending_skeleton.id = uuid.uuid4()

    return assign_skeleton_id


def _assign_persisted_timestamps(skeleton: Skeleton) -> None:
    """Fill server-default columns the handler reads after refresh."""

    persisted_at: datetime = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    skeleton.id = uuid.uuid4()
    skeleton.created_at = persisted_at
    skeleton.updated_at = persisted_at


def _skeleton_row(
    name: str,
    slug: str,
    template_key: str | None,
    created_at: datetime,
) -> Skeleton:
    """Build an in-memory Skeleton for list serialization."""

    skeleton: Skeleton = Skeleton(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        advertisement_type=AdvertisementType.CAROUSEL,
        template_key=template_key,
        status=SkeletonStatus.DRAFT,
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

    return skeleton
