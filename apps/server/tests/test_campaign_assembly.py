"""A campaign run places live slides on its skeleton and leaves drafts out."""

import inspect
import unittest
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.v1.campaigns import (
    CAMPAIGN_RUN_REQUIRES_BINDING_DETAIL,
    CAROUSEL_SKELETON_MISMATCH_DETAIL,
    resolve_campaign_binding,
    run_campaign,
)
from app.campaigns.assemble import assemble_carousels
from app.models.carousel import Slide
from app.models.enums import SlideTextStatus
from app.carousels.slide_text_review import live_slides


HARBOR_ID: uuid.UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
DESERT_ID: uuid.UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
DUNES_ID: uuid.UUID = uuid.UUID("33333333-3333-4333-8333-333333333333")
CAROUSEL_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-8444-444444444444")


class AssembleCarouselTests(unittest.TestCase):
    """Exclusion pairs split carousels. A single slide always fits."""

    def test_slides_that_exclude_each_other_are_separate_carousels(self) -> None:
        """Harbor cannot sit with Desert, so each gets its own carousel."""

        carousels: list[list[uuid.UUID]] = assemble_carousels(
            [HARBOR_ID, DESERT_ID],
            [(HARBOR_ID, DESERT_ID), (DESERT_ID, HARBOR_ID)],
        )

        self.assertEqual(carousels, [[HARBOR_ID], [DESERT_ID]])

    def test_a_third_slide_joins_the_first_carousel_that_allows_it(self) -> None:
        """Dunes can sit with Harbor, so it does not open a third carousel."""

        carousels: list[list[uuid.UUID]] = assemble_carousels(
            [HARBOR_ID, DESERT_ID, DUNES_ID],
            [(HARBOR_ID, DESERT_ID), (DESERT_ID, HARBOR_ID)],
        )

        self.assertEqual(carousels, [[HARBOR_ID, DUNES_ID], [DESERT_ID]])

    def test_slides_that_do_not_exclude_each_other_share_one_carousel(self) -> None:
        """A pick with no excluded pair stays one carousel."""

        carousels: list[list[uuid.UUID]] = assemble_carousels(
            [HARBOR_ID, DUNES_ID],
            [],
        )

        self.assertEqual(carousels, [[HARBOR_ID, DUNES_ID]])

    def test_no_live_slides_build_no_carousel(self) -> None:
        """An empty live list is an empty run."""

        carousels: list[list[uuid.UUID]] = assemble_carousels([], [(HARBOR_ID, DESERT_ID)])

        self.assertEqual(carousels, [])

    def test_a_draft_slide_is_not_a_live_slide(self) -> None:
        """Only accepted text is handed to the assembler."""

        harbor: Slide = _slide("Harbor", 0, HARBOR_ID, SlideTextStatus.LIVE)
        desert: Slide = _slide("Desert", 1, DESERT_ID, SlideTextStatus.DRAFT)
        live_ids: list[uuid.UUID] = [slide.id for slide in live_slides([desert, harbor])]

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
    """The carousel has to be the one bound to the picked skeleton."""

    def test_a_source_on_another_skeleton_is_rejected(self) -> None:
        """Create and run both refuse a carousel from a different skeleton."""

        skeleton_id: uuid.UUID = uuid.uuid4()
        carousel_id: uuid.UUID = uuid.uuid4()
        other_skeleton_id: uuid.UUID = uuid.uuid4()
        fake_session: MagicMock = MagicMock()
        skeleton: MagicMock = MagicMock()
        skeleton.id = skeleton_id
        carousel: MagicMock = MagicMock()
        carousel.id = carousel_id
        carousel.skeleton_id = other_skeleton_id

        def load_row(model: type[object], row_id: uuid.UUID) -> MagicMock | None:
            if row_id == skeleton_id:
                return skeleton

            if row_id == carousel_id:
                return carousel

            return None

        fake_session.get.side_effect = load_row

        with self.assertRaises(HTTPException) as raised_http:
            resolve_campaign_binding(skeleton_id, carousel_id, fake_session)

        self.assertEqual(raised_http.exception.status_code, 400)
        self.assertEqual(raised_http.exception.detail, CAROUSEL_SKELETON_MISMATCH_DETAIL)

    def test_a_campaign_without_a_skeleton_cannot_run(self) -> None:
        """Rows from before this phase stay stored and do not run."""

        campaign: MagicMock = MagicMock()
        campaign.skeleton_id = None
        campaign.carousel_id = None
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


def _slide(
    name: str,
    position: int,
    slide_id: uuid.UUID,
    text_status: SlideTextStatus,
) -> Slide:
    """Build an unbound slide for the live filter."""

    slide: Slide = Slide(
        id=slide_id,
        carousel_id=CAROUSEL_ID,
        position=position,
        name=name,
        text_status=text_status,
    )
    slide.exclusions = []

    return slide
