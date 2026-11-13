"""Validate a collection JSON object and draft one from the providers.

No network and no API key. The OpenAI call is replaced with a fake response.
"""

import unittest
import uuid
from unittest.mock import MagicMock, patch

import httpx

from app.carousels.collection_generation import (
    COLLECTION_RESPONSE_SHAPE,
    DraftedSlideCollection,
    parse_slide_collection,
    openai_collection_request_body,
)
from app.carousels.collection_prompt import (
    CollectionAlbumImage,
    CollectionExclusion,
    CollectionResearch,
)
from app.carousels.instructions import instruction_prompt_text
from app.carousels.text_generation import (
    MAX_DRAFTED_NAME_LENGTH,
    OPENAI_CHAT_COMPLETIONS_URL,
    TEXT_GENERATION_FAILED_DETAIL,
    DraftedSlideText,
    FakeTextGenerationProvider,
    OpenAITextGenerationProvider,
    TextElementPrompt,
    TextGenerationError,
)


IMAGE_ONE: uuid.UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
IMAGE_TWO: uuid.UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
IMAGE_UNKNOWN: uuid.UUID = uuid.UUID("99999999-9999-4999-8999-999999999999")
SLIDE_LEFT: uuid.UUID = uuid.UUID("33333333-3333-4333-8333-333333333333")
SLIDE_RIGHT: uuid.UUID = uuid.UUID("44444444-4444-4444-8444-444444444444")
ELEMENT_TITLE: uuid.UUID = uuid.UUID("55555555-5555-4555-8555-555555555555")
ELEMENT_CAPTION: uuid.UUID = uuid.UUID("66666666-6666-4666-8666-666666666666")
ELEMENT_UNKNOWN: uuid.UUID = uuid.UUID("77777777-7777-4777-8777-777777777777")


def _elements() -> list[TextElementPrompt]:
    """The two text elements a valid slide must fill."""

    elements: list[TextElementPrompt] = [
        TextElementPrompt(skeleton_element_id=ELEMENT_TITLE, label="Title"),
        TextElementPrompt(skeleton_element_id=ELEMENT_CAPTION, label="Caption"),
    ]

    return elements


def _slide(
    name: object,
    title: object,
    caption: object,
    album_image_id: object,
    extra_element_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """One slide object. Callers replace a field to make it invalid."""

    texts: list[dict[str, object]] = [
        {"skeleton_element_id": str(ELEMENT_TITLE), "value": title},
        {"skeleton_element_id": str(ELEMENT_CAPTION), "value": caption},
    ]

    if extra_element_id is not None:
        texts.append(
            {"skeleton_element_id": str(extra_element_id), "value": "Extra"},
        )

    slide: dict[str, object] = {
        "name": name,
        "texts": texts,
        "album_image_id": album_image_id,
    }

    return slide


def _payload(*slides: dict[str, object]) -> dict[str, object]:
    """A collection object with the given slides, in order."""

    payload: dict[str, object] = {"slides": list(slides)}

    return payload


class SlideCollectionParseTests(unittest.TestCase):
    """A usable object becomes a draft. A bad object raises."""

    def test_two_slides_round_trip_and_keep_an_empty_value(self) -> None:
        """Names collapse, texts stay in element order, and one image may repeat."""

        long_name: str = "Dune " + ("light " * 80)
        payload: dict[str, object] = _payload(
            _slide("  Cove   light  ", "Still water", "", str(IMAGE_ONE)),
            _slide(long_name, "Sand", "Dry wind", str(IMAGE_ONE)),
        )
        drafted: DraftedSlideCollection = parse_slide_collection(
            payload,
            2,
            _elements(),
            [IMAGE_ONE],
            True,
        )
        expected_long_name: str = " ".join(long_name.split())[:MAX_DRAFTED_NAME_LENGTH]

        self.assertEqual(len(drafted.slides), 2)
        self.assertEqual(drafted.slides[0].name, "Cove light")
        self.assertEqual(
            drafted.slides[0].values_by_element_id[ELEMENT_TITLE],
            "Still water",
        )
        self.assertEqual(drafted.slides[0].values_by_element_id[ELEMENT_CAPTION], "")
        self.assertEqual(drafted.slides[0].album_image_id, IMAGE_ONE)
        self.assertEqual(drafted.slides[1].name, expected_long_name)
        self.assertEqual(len(drafted.slides[1].name), MAX_DRAFTED_NAME_LENGTH)
        self.assertEqual(drafted.slides[1].values_by_element_id[ELEMENT_TITLE], "Sand")
        self.assertEqual(
            drafted.slides[1].values_by_element_id[ELEMENT_CAPTION],
            "Dry wind",
        )
        self.assertEqual(drafted.slides[1].album_image_id, IMAGE_ONE)

    def test_rejected_objects_raise(self) -> None:
        """A bad count, name, element, or image rejects the whole object."""

        valid_first: dict[str, object] = _slide("Cove", "Still water", "", str(IMAGE_ONE))
        valid_second: dict[str, object] = _slide("Dune", "Sand", "Dry wind", str(IMAGE_ONE))
        rejected: list[tuple[object, bool]] = [
            (_payload(valid_first), True),
            (_payload(_slide("   ", "Still water", "", str(IMAGE_ONE)), valid_second), True),
            (_payload(_slide(12, "Still water", "", str(IMAGE_ONE)), valid_second), True),
            (
                _payload(
                    _slide(
                        "Cove",
                        "Still water",
                        "",
                        str(IMAGE_ONE),
                        extra_element_id=ELEMENT_UNKNOWN,
                    ),
                    valid_second,
                ),
                True,
            ),
            (
                _payload(
                    _slide("Cove", "Still water", "", str(IMAGE_UNKNOWN)),
                    valid_second,
                ),
                True,
            ),
            (_payload(valid_first, valid_second), False),
            (
                _payload(
                    _slide("Cove", "Still water", "", None),
                    _slide("Dune", "Sand", "Dry wind", None),
                ),
                True,
            ),
            (
                _payload(
                    _slide("Cove", "Still water", 4, str(IMAGE_ONE)),
                    valid_second,
                ),
                True,
            ),
            (
                _payload(
                    {
                        "name": "Cove",
                        "texts": [
                            {
                                "skeleton_element_id": str(ELEMENT_TITLE),
                                "value": "Still water",
                            },
                        ],
                        "album_image_id": str(IMAGE_ONE),
                    },
                    valid_second,
                ),
                True,
            ),
            (_payload(valid_first, valid_second, valid_first), True),
        ]

        for payload, image_required in rejected:

            with self.subTest(payload=payload, image_required=image_required):

                with self.assertRaises(TextGenerationError) as caught:
                    parse_slide_collection(
                        payload,
                        2,
                        _elements(),
                        [IMAGE_ONE],
                        image_required,
                    )

                self.assertEqual(str(caught.exception), TEXT_GENERATION_FAILED_DETAIL)

    def test_request_body_is_json_only_and_contains_the_instruction(self) -> None:
        """The body asks for a JSON object and carries the instruction text."""

        body: dict[str, object] = openai_collection_request_body(
            "gpt-4o-mini",
            ["Harbor fog"],
            [CollectionResearch(title="Tide notes", body="The water is still.")],
            [],
            [],
            _elements(),
            6,
            True,
        )
        messages: object = body["messages"]

        self.assertEqual(set(body), {"model", "response_format", "messages"})
        self.assertEqual(body["model"], "gpt-4o-mini")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], dict)
        self.assertIsInstance(messages[1], dict)
        system_message: object = messages[0]["content"]
        user_message: object = messages[1]["content"]
        self.assertIsInstance(system_message, str)
        self.assertIsInstance(user_message, str)
        self.assertIn("Reply with JSON only.", system_message)
        self.assertIn("Harbor fog", user_message)
        self.assertIn("Tide notes", user_message)
        self.assertIn(COLLECTION_RESPONSE_SHAPE, user_message)
        self.assertNotIn("api_key", str(body))
        self.assertNotIn("Authorization", str(body))


class SlideCollectionDraftTests(unittest.TestCase):
    """The fake provider drafts locally. OpenAI is only called through a stand-in."""

    def test_fake_provider_drafts_five_slides_and_round_robins_images(self) -> None:
        """Five names, the instruction text, and two image ids in turn."""

        provider: FakeTextGenerationProvider = FakeTextGenerationProvider()
        bodies: list[str] = ["Harbor fog", "   "]
        instruction_text: str = instruction_prompt_text(bodies)
        album_images: list[CollectionAlbumImage] = [
            CollectionAlbumImage(
                image_id=IMAGE_ONE,
                position=0,
                alt_text="Night quay",
                source="Commons",
                license_note="CC0",
            ),
            CollectionAlbumImage(
                image_id=IMAGE_TWO,
                position=1,
                alt_text="Dunes",
                source="Survey",
                license_note="Owned",
            ),
        ]
        drafted: DraftedSlideCollection = provider.draft_slide_collection(
            bodies,
            [CollectionResearch(title="Tide notes", body="The water is still.")],
            album_images,
            [
                CollectionExclusion(
                    left_name="Cove",
                    left_id=SLIDE_LEFT,
                    right_name="Dune",
                    right_id=SLIDE_RIGHT,
                ),
            ],
            _elements(),
            5,
            True,
        )
        expected_images: list[uuid.UUID] = [
            IMAGE_ONE,
            IMAGE_TWO,
            IMAGE_ONE,
            IMAGE_TWO,
            IMAGE_ONE,
        ]

        self.assertEqual(len(drafted.slides), 5)
        self.assertEqual(instruction_text, "Harbor fog")

        for index, slide in enumerate(drafted.slides):
            self.assertEqual(slide.name, f"Drafted slide {index + 1}")
            self.assertNotIn("Cove", slide.name)
            self.assertNotIn("Dune", slide.name)
            self.assertEqual(slide.album_image_id, expected_images[index])
            self.assertEqual(
                slide.values_by_element_id[ELEMENT_TITLE],
                f"Title. {instruction_text}",
            )
            self.assertEqual(
                slide.values_by_element_id[ELEMENT_CAPTION],
                f"Caption. {instruction_text}",
            )
            self.assertIn(instruction_text, slide.values_by_element_id[ELEMENT_TITLE])
            self.assertNotIn("Tide notes", slide.values_by_element_id[ELEMENT_TITLE])

    def test_fake_provider_leaves_images_null_when_none_are_required(self) -> None:
        """A skeleton that needs no picture stores a null image on every slide."""

        provider: FakeTextGenerationProvider = FakeTextGenerationProvider()
        drafted: DraftedSlideCollection = provider.draft_slide_collection(
            ["Harbor fog"],
            [],
            [
                CollectionAlbumImage(
                    image_id=IMAGE_ONE,
                    position=0,
                    alt_text=None,
                    source="Commons",
                    license_note="",
                ),
            ],
            [],
            _elements(),
            5,
            False,
        )

        self.assertEqual(len(drafted.slides), 5)

        for slide in drafted.slides:
            self.assertIsNone(slide.album_image_id)

    def test_fake_draft_slide_text_still_returns_one_slide(self) -> None:
        """The single-slide fake draft is unchanged."""

        element_id: uuid.UUID = uuid.uuid4()
        provider: FakeTextGenerationProvider = FakeTextGenerationProvider()
        drafted: DraftedSlideText = provider.draft_slide_text(
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
        self.assertEqual(len(drafted.values_by_element_id), 1)

    def test_openai_body_that_fails_parse_raises(self) -> None:
        """A chat completion the collection parser rejects raises, and does not write."""

        provider: OpenAITextGenerationProvider = OpenAITextGenerationProvider(
            "test-key",
            "gpt-4o-mini",
        )
        response: MagicMock = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"slides": []}',
                    },
                },
            ],
        }

        with patch(
            "app.carousels.text_generation.httpx.post",
            return_value=response,
        ) as posted:
            with self.assertRaises(TextGenerationError) as caught:
                provider.draft_slide_collection(
                    ["Harbor fog"],
                    [],
                    [],
                    [],
                    _elements(),
                    2,
                    False,
                )

        self.assertEqual(str(caught.exception), TEXT_GENERATION_FAILED_DETAIL)
        posted.assert_called_once_with(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers={"Authorization": "Bearer test-key"},
            json=openai_collection_request_body(
                "gpt-4o-mini",
                ["Harbor fog"],
                [],
                [],
                [],
                _elements(),
                2,
                False,
            ),
            timeout=30.0,
        )
        self.assertNotIn("test-key", str(posted.call_args.kwargs["json"]))

    def test_openai_http_and_non_json_bodies_raise(self) -> None:
        """An HTTP error or a message that is not JSON raises TextGenerationError."""

        provider: OpenAITextGenerationProvider = OpenAITextGenerationProvider(
            "test-key",
            "gpt-4o-mini",
        )
        non_json: MagicMock = MagicMock()
        non_json.status_code = 200
        non_json.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "not json",
                    },
                },
            ],
        }
        refused: MagicMock = MagicMock()
        refused.status_code = 500

        with patch(
            "app.carousels.text_generation.httpx.post",
            return_value=non_json,
        ):
            with self.assertRaises(TextGenerationError):
                provider.draft_slide_collection(
                    ["Harbor fog"],
                    [],
                    [],
                    [],
                    _elements(),
                    1,
                    False,
                )

        with patch(
            "app.carousels.text_generation.httpx.post",
            return_value=refused,
        ):
            with self.assertRaises(TextGenerationError):
                provider.draft_slide_collection(
                    ["Harbor fog"],
                    [],
                    [],
                    [],
                    _elements(),
                    1,
                    False,
                )

        with patch(
            "app.carousels.text_generation.httpx.post",
            side_effect=httpx.ConnectError("down"),
        ):
            with self.assertRaises(TextGenerationError):
                provider.draft_slide_collection(
                    ["Harbor fog"],
                    [],
                    [],
                    [],
                    _elements(),
                    1,
                    False,
                )


if __name__ == "__main__":
    unittest.main()
