"""Drafted unit text stays off the live unit until a person accepts it."""

import os
import unittest
import uuid

from fastapi import HTTPException

from app.api.v1.schemas import (
    SourceCreateRequest,
    SourceGuidancePatchRequest,
    UnitAcceptTextRequest,
    UnitElementTextWrite,
    UnitWriteRequest,
)
from app.api.v1.source_text import (
    accept_unit_text,
    generate_source_unit,
    generate_unit_text,
    patch_source_guidance,
)
from app.api.v1.source_writes import create_unit
from app.models.content_source import ContentSource, Unit
from app.models.theme_element import ThemeElement
from app.models.enums import BackgroundKind, UnitTextStatus
from app.settings import clear_settings_cache
from app.sources.text_generation import (
    GENERATE_DISABLED_DETAIL,
    FakeTextGenerationProvider,
    TextElementPrompt,
    drafted_text_from_openai_response,
)
from app.sources.unit_text_review import live_units, unit_counts_as_live
from tests.test_source_writes import _MemorySourceSession, _title_element


class UnitTextDraftTests(unittest.TestCase):
    """Generate, accept, and the live-unit filter."""

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

        session: _MemorySourceSession = _MemorySourceSession()
        text_element: ThemeElement = _title_element(session.theme.id)
        session.theme.elements = [text_element]
        created = create_source(session)
        patch_source_guidance(
            created.id,
            SourceGuidancePatchRequest(
                inspiration="Harbor fog",
                rules="Keep it short",
            ),
            session,
            None,
        )
        harbor = create_unit(
            created.id,
            UnitWriteRequest(
                name="Harbor",
                texts=[
                    UnitElementTextWrite(
                        theme_element_id=text_element.id,
                        value="Fog on the water",
                    ),
                ],
            ),
            session,
            None,
        )
        drafted = generate_unit_text(created.id, harbor.id, session, None)
        source: ContentSource | None = session.get(ContentSource, created.id)

        assert source is not None

        stored_unit: Unit = source.units[0]

        self.assertEqual(drafted.text_status, UnitTextStatus.DRAFT)
        self.assertEqual(drafted.texts[0].value, "Fog on the water")
        self.assertEqual(
            drafted.draft_texts[0].value,
            "Title. Harbor fog. Keep it short",
        )
        self.assertEqual(drafted.name, "Harbor")
        self.assertEqual(live_units(list(source.units)), [])
        self.assertFalse(unit_counts_as_live(stored_unit))
        self.assertEqual(stored_unit.element_texts[0].value, "Fog on the water")

        accepted = accept_unit_text(
            created.id,
            harbor.id,
            UnitAcceptTextRequest(
                texts=[
                    UnitElementTextWrite(
                        theme_element_id=text_element.id,
                        value="Title. Harbor fog. Keep it short",
                    ),
                ],
            ),
            session,
            None,
        )

        self.assertEqual(accepted.text_status, UnitTextStatus.LIVE)
        self.assertEqual(accepted.draft_texts, [])
        self.assertEqual(accepted.texts[0].value, "Title. Harbor fog. Keep it short")
        self.assertEqual(len(live_units(list(source.units))), 1)

    def test_generating_a_unit_leaves_the_image_empty(self) -> None:
        """A new draft unit carries text only. The image is still uploaded."""

        session: _MemorySourceSession = _MemorySourceSession()
        text_element: ThemeElement = _title_element(session.theme.id)
        session.theme.elements = [text_element]
        created = create_source(session)
        patch_source_guidance(
            created.id,
            SourceGuidancePatchRequest(inspiration="Phase four harbor", rules=""),
            session,
            None,
        )
        drafted = generate_source_unit(created.id, session, None)

        self.assertEqual(drafted.name, "Phase four harbor")
        self.assertEqual(drafted.text_status, UnitTextStatus.DRAFT)
        self.assertEqual(drafted.images, [])
        self.assertEqual(drafted.texts[0].value, "")
        self.assertEqual(drafted.draft_texts[0].value, "Title. Phase four harbor")
        stored_source: ContentSource | None = session.get(ContentSource, created.id)

        assert stored_source is not None

        self.assertEqual(len(live_units(list(stored_source.units))), 0)

    def test_accept_without_a_required_image_writes_nothing(self) -> None:
        """A picture theme still needs an uploaded image before the unit is live."""

        session: _MemorySourceSession = _MemorySourceSession()
        text_element: ThemeElement = _title_element(session.theme.id)
        session.theme.elements = [text_element]
        session.theme.background_kind = BackgroundKind.PICTURE
        created = create_source(session)
        drafted = generate_source_unit(created.id, session, None)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            accept_unit_text(
                created.id,
                drafted.id,
                UnitAcceptTextRequest(
                    texts=[
                        UnitElementTextWrite(
                            theme_element_id=text_element.id,
                            value="Kept",
                        ),
                    ],
                ),
                session,
                None,
            )

        source: ContentSource | None = session.get(ContentSource, created.id)

        assert source is not None

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "This theme needs an image on the unit.")
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(source.units[0].text_status, UnitTextStatus.DRAFT)

    def test_saving_a_draft_does_not_replace_the_live_text(self) -> None:
        """Save on a draft updates the draft. Accept is what makes it live."""

        session: _MemorySourceSession = _MemorySourceSession()
        text_element: ThemeElement = _title_element(session.theme.id)
        session.theme.elements = [text_element]
        created = create_source(session)
        harbor = create_unit(
            created.id,
            UnitWriteRequest(
                name="Harbor",
                texts=[
                    UnitElementTextWrite(
                        theme_element_id=text_element.id,
                        value="Fog on the water",
                    ),
                ],
            ),
            session,
            None,
        )
        generate_unit_text(created.id, harbor.id, session, None)

        from app.api.v1.source_writes import patch_unit

        saved = patch_unit(
            created.id,
            harbor.id,
            UnitWriteRequest(
                name="Harbor",
                texts=[
                    UnitElementTextWrite(
                        theme_element_id=text_element.id,
                        value="Edited draft",
                    ),
                ],
            ),
            session,
            None,
        )
        source: ContentSource | None = session.get(ContentSource, created.id)

        assert source is not None

        self.assertEqual(saved.text_status, UnitTextStatus.DRAFT)
        self.assertEqual(saved.texts[0].value, "Fog on the water")
        self.assertEqual(saved.draft_texts[0].value, "Edited draft")
        self.assertEqual(live_units(list(source.units)), [])

    def test_generate_without_a_key_writes_nothing(self) -> None:
        """An empty OpenAI key refuses the draft and leaves the unit live."""

        os.environ["TEXT_GENERATION_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = ""
        clear_settings_cache()
        session: _MemorySourceSession = _MemorySourceSession()
        text_element: ThemeElement = _title_element(session.theme.id)
        session.theme.elements = [text_element]
        created = create_source(session)
        harbor = create_unit(
            created.id,
            UnitWriteRequest(name="Harbor"),
            session,
            None,
        )
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            generate_unit_text(created.id, harbor.id, session, None)

        source: ContentSource | None = session.get(ContentSource, created.id)

        assert source is not None

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, GENERATE_DISABLED_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertTrue(unit_counts_as_live(source.units[0]))

    def test_a_theme_without_text_elements_is_not_drafted(self) -> None:
        """Generate needs a text element. The source stays unchanged."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.theme.elements = []
        created = create_source(session)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            generate_source_unit(created.id, session, None)

        source: ContentSource | None = session.get(ContentSource, created.id)

        assert source is not None

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "This theme has no text elements to draft.")
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(list(source.units), [])

    def _restore(self, name: str, previous: str | None) -> None:
        """Put one environment variable back."""

        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


class TextGenerationProviderTests(unittest.TestCase):
    """The fake provider and the OpenAI response parser. No network."""

    def test_fake_provider_uses_inspiration_and_rules(self) -> None:
        """Each element carries its label plus the source guidance."""

        element_id: uuid.UUID = uuid.uuid4()
        provider: FakeTextGenerationProvider = FakeTextGenerationProvider()
        drafted = provider.draft_unit_text(
            "Harbor fog",
            "Keep it short",
            None,
            [TextElementPrompt(theme_element_id=element_id, label="title")],
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
                                '{"name":"Cove","texts":[{"theme_element_id":"'
                                + str(element_id)
                                + '","value":"Still water"}]}'
                            ),
                        },
                    },
                ],
            },
            [TextElementPrompt(theme_element_id=element_id, label="title")],
            "Harbor",
        )

        self.assertEqual(drafted.name, "Harbor")
        self.assertEqual(drafted.values_by_element_id[element_id], "Still water")


def create_source(session: _MemorySourceSession):
    """Create one source on the memory session."""

    from app.api.v1.schemas import SourceReadResponse
    from app.api.v1.source_writes import create_content_source

    created_source: SourceReadResponse = create_content_source(
        SourceCreateRequest(name="Pairs", theme_id=session.theme.id),
        session,
        None,
    )

    return created_source
