"""A campaign run places live units on its theme and leaves drafts out."""

import inspect
import unittest
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.v1.campaigns import (
    CAMPAIGN_RUN_REQUIRES_BINDING_DETAIL,
    SOURCE_THEME_MISMATCH_DETAIL,
    resolve_campaign_binding,
    run_campaign,
)
from app.campaigns.assemble import assemble_carousels
from app.models.content_source import Unit
from app.models.enums import UnitTextStatus
from app.sources.unit_text_review import live_units


HARBOR_ID: uuid.UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
DESERT_ID: uuid.UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
DUNES_ID: uuid.UUID = uuid.UUID("33333333-3333-4333-8333-333333333333")
SOURCE_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-8444-444444444444")


class AssembleCarouselTests(unittest.TestCase):
    """Exclusion pairs split carousels. A single unit always fits."""

    def test_units_that_exclude_each_other_are_separate_carousels(self) -> None:
        """Harbor cannot sit with Desert, so each gets its own carousel."""

        carousels: list[list[uuid.UUID]] = assemble_carousels(
            [HARBOR_ID, DESERT_ID],
            [(HARBOR_ID, DESERT_ID), (DESERT_ID, HARBOR_ID)],
        )

        self.assertEqual(carousels, [[HARBOR_ID], [DESERT_ID]])

    def test_a_third_unit_joins_the_first_carousel_that_allows_it(self) -> None:
        """Dunes can sit with Harbor, so it does not open a third carousel."""

        carousels: list[list[uuid.UUID]] = assemble_carousels(
            [HARBOR_ID, DESERT_ID, DUNES_ID],
            [(HARBOR_ID, DESERT_ID), (DESERT_ID, HARBOR_ID)],
        )

        self.assertEqual(carousels, [[HARBOR_ID, DUNES_ID], [DESERT_ID]])

    def test_units_that_do_not_exclude_each_other_share_one_carousel(self) -> None:
        """A pick with no excluded pair stays one carousel."""

        carousels: list[list[uuid.UUID]] = assemble_carousels(
            [HARBOR_ID, DUNES_ID],
            [],
        )

        self.assertEqual(carousels, [[HARBOR_ID, DUNES_ID]])

    def test_no_live_units_build_no_carousel(self) -> None:
        """An empty live list is an empty run."""

        carousels: list[list[uuid.UUID]] = assemble_carousels([], [(HARBOR_ID, DESERT_ID)])

        self.assertEqual(carousels, [])

    def test_a_draft_unit_is_not_a_live_unit(self) -> None:
        """Only accepted text is handed to the assembler."""

        harbor: Unit = _unit("Harbor", 0, HARBOR_ID, UnitTextStatus.LIVE)
        desert: Unit = _unit("Desert", 1, DESERT_ID, UnitTextStatus.DRAFT)
        live_ids: list[uuid.UUID] = [unit.id for unit in live_units([desert, harbor])]

        self.assertEqual(live_ids, [HARBOR_ID])

    def test_assemble_does_not_generate_text(self) -> None:
        """The assembler has no model client."""

        assemble_source: str = inspect.getsource(assemble_carousels)
        run_source: str = inspect.getsource(run_campaign)

        self.assertNotIn("text_generation", assemble_source)
        self.assertNotIn("openai", assemble_source.lower())
        self.assertNotIn("text_generation", run_source)
        self.assertNotIn("openai", run_source.lower())


class CampaignBindingTests(unittest.TestCase):
    """The source has to be the one bound to the picked theme."""

    def test_a_source_on_another_theme_is_rejected(self) -> None:
        """Create and run both refuse a source from a different theme."""

        theme_id: uuid.UUID = uuid.uuid4()
        source_id: uuid.UUID = uuid.uuid4()
        other_theme_id: uuid.UUID = uuid.uuid4()
        fake_session: MagicMock = MagicMock()
        theme: MagicMock = MagicMock()
        theme.id = theme_id
        source: MagicMock = MagicMock()
        source.id = source_id
        source.theme_id = other_theme_id

        def load_row(model: type[object], row_id: uuid.UUID) -> MagicMock | None:
            if row_id == theme_id:
                return theme

            if row_id == source_id:
                return source

            return None

        fake_session.get.side_effect = load_row

        with self.assertRaises(HTTPException) as raised_http:
            resolve_campaign_binding(theme_id, source_id, fake_session)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, SOURCE_THEME_MISMATCH_DETAIL)

    def test_a_campaign_without_a_theme_cannot_run(self) -> None:
        """Rows from before this phase stay stored and do not run."""

        campaign: MagicMock = MagicMock()
        campaign.theme_id = None
        campaign.source_id = None
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = campaign

        with self.assertRaises(HTTPException) as raised_http:
            run_campaign(uuid.uuid4(), fake_session, None)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(
            raised_http.exception.detail,
            CAMPAIGN_RUN_REQUIRES_BINDING_DETAIL,
        )
        fake_session.commit.assert_not_called()


def _unit(
    name: str,
    position: int,
    unit_id: uuid.UUID,
    text_status: UnitTextStatus,
) -> Unit:
    """Build an unbound unit for the live filter."""

    unit: Unit = Unit(
        id=unit_id,
        source_id=SOURCE_ID,
        position=position,
        name=name,
        text_status=text_status,
    )
    unit.exclusions = []

    return unit
