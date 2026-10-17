"""Drafted slide text stays off the live slide until a person accepts it."""

import os
import unittest
import uuid

from fastapi import HTTPException

from app.api.v1.schemas import (
    CarouselCreateRequest,
    CarouselGuidancePatchRequest,
    SlideAcceptTextRequest,
    SlideElementTextWrite,
    SlideWriteRequest,
)
from app.api.v1.carousel_text import (
    accept_slide_text,
    generate_source_slide,
    generate_slide_text,
    patch_source_guidance,
)
from app.api.v1.carousel_writes import create_slide
from app.models.carousel import Carousel, Slide
from app.models.skeleton_element import SkeletonElement
from app.models.enums import BackgroundKind, SlideTextStatus
from app.settings import clear_settings_cache
from app.carousels.text_generation import (
    GENERATE_DISABLED_DETAIL,
    FakeTextGenerationProvider,
    TextElementPrompt,
    drafted_text_from_openai_response,
)
from app.carousels.slide_text_review import live_slides, slide_counts_as_live
from tests.test_carousel_writes import _MemoryCarouselSession, _title_element


class SlideTextDraftTests(unittest.TestCase):
    """Generate, accept, and the live-slide filter."""

    def setUp(self) -> None:
        """Point Generate at the fake provider for this case."""

        self.previous_provider: str | None = os.environ.get("TEXT_GENERATION_PROVIDER")
        self.previous_api_key: str | None = os.environ.get("OPENAI_API_KEY")
        os.environ["TEXT_GENERATION_PROVIDER"] = "fake"
        os.environ["OPENAI_API_KEY"] = ""
        clear_settings_cache()

    def tearDown(self) -> None:
        """Restore the provider env and drop the settings cache."""

        self._restore("TEXT_GENERATION_PROVIDER", self.previous_provider)
        self._restore("OPENAI_API_KEY", self.previous_api_key)
        clear_settings_cache()

    def test_a_draft_is_not_live_until_it_is_accepted(self) -> None:
        """Generate fills the draft. The approved string stays until accept."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element: SkeletonElement = _title_element(session.skeleton.id)
        session.skeleton.elements = [text_element]
        created = create_source(session)
        patch_source_guidance(
            created.id,
            CarouselGuidancePatchRequest(
                inspiration="Harbor fog",
                rules="Keep it short",
            ),
            session,
            None,
        )
        harbor = create_slide(
            created.id,
            SlideWriteRequest(
                name="Harbor",
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=text_element.id,
                        value="Fog on the water",
                    ),
                ],
            ),
            session,
            None,
        )
        drafted = generate_slide_text(created.id, harbor.id, session, None)
        carousel: Carousel | None = session.get(Carousel, created.id)

        assert carousel is not None

        stored_slide: Slide = carousel.slides[0]

        self.assertEqual(drafted.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(drafted.texts[0].value, "Fog on the water")
        self.assertEqual(
            drafted.draft_texts[0].value,
            "Title. Harbor fog. Keep it short",
        )
        self.assertEqual(drafted.name, "Harbor")
        self.assertEqual(live_slides(list(carousel.slides)), [])
        self.assertFalse(slide_counts_as_live(stored_slide))
        self.assertEqual(stored_slide.element_texts[0].value, "Fog on the water")

        accepted = accept_slide_text(
            created.id,
            harbor.id,
            SlideAcceptTextRequest(
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=text_element.id,
                        value="Title. Harbor fog. Keep it short",
                    ),
                ],
            ),
            session,
            None,
        )

        self.assertEqual(accepted.text_status, SlideTextStatus.LIVE)
        self.assertEqual(accepted.draft_texts, [])
        self.assertEqual(accepted.texts[0].value, "Title. Harbor fog. Keep it short")
        self.assertEqual(len(live_slides(list(carousel.slides))), 1)

    def test_generating_a_slide_leaves_the_image_empty(self) -> None:
        """A new draft slide carries text only. The image is still uploaded."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element: SkeletonElement = _title_element(session.skeleton.id)
        session.skeleton.elements = [text_element]
        created = create_source(session)
        patch_source_guidance(
            created.id,
            CarouselGuidancePatchRequest(inspiration="Phase four harbor", rules=""),
            session,
            None,
        )
        drafted = generate_source_slide(created.id, session, None)

        self.assertEqual(drafted.name, "Phase four harbor")
        self.assertEqual(drafted.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(drafted.images, [])
        self.assertEqual(drafted.texts[0].value, "")
        self.assertEqual(drafted.draft_texts[0].value, "Title. Phase four harbor")
        stored_source: Carousel | None = session.get(Carousel, created.id)

        assert stored_source is not None

        self.assertEqual(len(live_slides(list(stored_source.slides))), 0)

    def test_accept_without_a_required_image_writes_nothing(self) -> None:
        """A picture skeleton still needs an uploaded image before the slide is live."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element: SkeletonElement = _title_element(session.skeleton.id)
        session.skeleton.elements = [text_element]
        session.skeleton.background_kind = BackgroundKind.PICTURE
        created = create_source(session)
        drafted = generate_source_slide(created.id, session, None)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            accept_slide_text(
                created.id,
                drafted.id,
                SlideAcceptTextRequest(
                    texts=[
                        SlideElementTextWrite(
                            skeleton_element_id=text_element.id,
                            value="Kept",
                        ),
                    ],
                ),
                session,
                None,
            )

        carousel: Carousel | None = session.get(Carousel, created.id)

        assert carousel is not None

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "This skeleton needs an image on the slide.")
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(carousel.slides[0].text_status, SlideTextStatus.DRAFT)

    def test_saving_a_draft_does_not_replace_the_live_text(self) -> None:
        """Save on a draft updates the draft. Accept is what makes it live."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element: SkeletonElement = _title_element(session.skeleton.id)
        session.skeleton.elements = [text_element]
        created = create_source(session)
        harbor = create_slide(
            created.id,
            SlideWriteRequest(
                name="Harbor",
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=text_element.id,
                        value="Fog on the water",
                    ),
                ],
            ),
            session,
            None,
        )
        generate_slide_text(created.id, harbor.id, session, None)

        from app.api.v1.carousel_writes import patch_slide

        saved = patch_slide(
            created.id,
            harbor.id,
            SlideWriteRequest(
                name="Harbor",
                texts=[
                    SlideElementTextWrite(
                        skeleton_element_id=text_element.id,
                        value="Edited draft",
                    ),
                ],
            ),
            session,
            None,
        )
        carousel: Carousel | None = session.get(Carousel, created.id)

        assert carousel is not None

        self.assertEqual(saved.text_status, SlideTextStatus.DRAFT)
        self.assertEqual(saved.texts[0].value, "Fog on the water")
        self.assertEqual(saved.draft_texts[0].value, "Edited draft")
        self.assertEqual(live_slides(list(carousel.slides)), [])

    def test_generate_without_a_key_writes_nothing(self) -> None:
        """An empty OpenAI key refuses the draft and leaves the slide live."""

        os.environ["TEXT_GENERATION_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = ""
        clear_settings_cache()
        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element: SkeletonElement = _title_element(session.skeleton.id)
        session.skeleton.elements = [text_element]
        created = create_source(session)
        harbor = create_slide(
            created.id,
            SlideWriteRequest(name="Harbor"),
            session,
            None,
        )
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            generate_slide_text(created.id, harbor.id, session, None)

        carousel: Carousel | None = session.get(Carousel, created.id)

        assert carousel is not None

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, GENERATE_DISABLED_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertTrue(slide_counts_as_live(carousel.slides[0]))

    def test_a_skeleton_without_text_elements_is_not_drafted(self) -> None:
        """Generate needs a text element. The carousel stays unchanged."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.elements = []
        created = create_source(session)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            generate_source_slide(created.id, session, None)

        carousel: Carousel | None = session.get(Carousel, created.id)

        assert carousel is not None

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "This skeleton has no text elements to draft.")
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(list(carousel.slides), [])

    def _restore(self, name: str, previous: str | None) -> None:
        """Put one environment variable back."""

        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


class TextGenerationProviderTests(unittest.TestCase):
    """The fake provider and the OpenAI response parser. No network."""

    def test_fake_provider_uses_inspiration_and_rules(self) -> None:
        """Each element carries its label plus the carousel guidance."""

        element_id: uuid.UUID = uuid.uuid4()
        provider: FakeTextGenerationProvider = FakeTextGenerationProvider()
        drafted = provider.draft_slide_text(
            "Harbor fog",
            "Keep it short",
            None,
            [TextElementPrompt(skeleton_element_id=element_id, label="title")],
        )

        self.assertEqual(drafted.name, "Harbor fog")
        self.assertEqual(
            drafted.values_by_element_id[element_id],
            "title. Harbor fog. Keep it short",
        )

    def test_openai_payload_maps_each_element(self) -> None:
        """A chat completion JSON object becomes one value per element."""

        element_id: uuid.UUID = uuid.uuid4()
        drafted = drafted_text_from_openai_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"name":"Cove","texts":[{"skeleton_element_id":"'
                                + str(element_id)
                                + '","value":"Still water"}]}'
                            ),
                        },
                    },
                ],
            },
            [TextElementPrompt(skeleton_element_id=element_id, label="title")],
            "Harbor",
        )

        self.assertEqual(drafted.name, "Harbor")
        self.assertEqual(drafted.values_by_element_id[element_id], "Still water")


def create_source(session: _MemoryCarouselSession):
    """Create one carousel on the memory session."""

    from app.api.v1.schemas import CarouselReadResponse
    from app.api.v1.carousel_writes import create_carousel

    created_source: CarouselReadResponse = create_carousel(
        CarouselCreateRequest(name="Pairs", skeleton_id=session.skeleton.id),
        session,
        None,
    )

    return created_source
