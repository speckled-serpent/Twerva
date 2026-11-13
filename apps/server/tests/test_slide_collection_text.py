"""Validate a collection JSON object. No network and no API key."""

import unittest
import uuid

from app.carousels.collection_generation import (
    COLLECTION_RESPONSE_SHAPE,
    DraftedSlideCollection,
    parse_slide_collection,
    openai_collection_request_body,
)
from app.carousels.collection_prompt import CollectionResearch
from app.carousels.text_generation import (
    MAX_DRAFTED_NAME_LENGTH,
    TEXT_GENERATION_FAILED_DETAIL,
    TextElementPrompt,
    TextGenerationError,
)


IMAGE_ONE: uuid.UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
IMAGE_UNKNOWN: uuid.UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
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


if __name__ == "__main__":
    unittest.main()
