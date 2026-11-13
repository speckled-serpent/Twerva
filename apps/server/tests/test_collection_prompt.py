"""The collection prompt is one user text. It does not call a provider."""

import unittest
import uuid

from app.carousels.collection_prompt import (
    CollectionAlbumImage,
    CollectionExclusion,
    CollectionResearch,
    collection_prompt_text,
)
from app.carousels.instructions import instruction_prompt_text
from app.carousels.text_generation import TextElementPrompt


IMAGE_ONE: uuid.UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
IMAGE_TWO: uuid.UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
SLIDE_LEFT: uuid.UUID = uuid.UUID("33333333-3333-4333-8333-333333333333")
SLIDE_RIGHT: uuid.UUID = uuid.UUID("44444444-4444-4444-8444-444444444444")
ELEMENT_TITLE: uuid.UUID = uuid.UUID("55555555-5555-4555-8555-555555555555")
ELEMENT_CAPTION: uuid.UUID = uuid.UUID("66666666-6666-4666-8666-666666666666")
FIRST_INSTRUCTION: str = "Harbor fog"
SECOND_INSTRUCTION: str = "Keep it short"
BLANK_INSTRUCTION: str = "   "


class CollectionPromptTests(unittest.TestCase):
    """Section order, the instruction join, and empty sections."""

    def test_prompt_joins_the_parts_in_section_order(self) -> None:
        """Bodies, research, images, and one exclusion stay in the given order."""

        prompt: str = collection_prompt_text(
            [FIRST_INSTRUCTION, BLANK_INSTRUCTION, SECOND_INSTRUCTION],
            [
                CollectionResearch(title="Harbor notes", body="The tide is out."),
                CollectionResearch(title="Quay facts", body=""),
            ],
            [
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
            ],
            [
                CollectionExclusion(
                    left_name="Cove",
                    left_id=SLIDE_LEFT,
                    right_name="Dune",
                    right_id=SLIDE_RIGHT,
                ),
            ],
            [
                TextElementPrompt(skeleton_element_id=ELEMENT_TITLE, label="Title"),
                TextElementPrompt(skeleton_element_id=ELEMENT_CAPTION, label="Caption"),
            ],
            6,
            True,
        )
        joined_instructions: str = instruction_prompt_text(
            [FIRST_INSTRUCTION, BLANK_INSTRUCTION, SECOND_INSTRUCTION],
        )
        exclusion_line: str = (
            f"Cove ({SLIDE_LEFT}) cannot be shown with Dune ({SLIDE_RIGHT})"
        )
        expected: str = (
            "Instructions:\n"
            f"{joined_instructions}\n"
            "\n"
            "Research:\n"
            "Harbor notes\n"
            "The tide is out.\n"
            "\n"
            "Quay facts\n"
            "\n"
            "Album images:\n"
            f"{IMAGE_ONE} position 0 alt: Night quay source: Commons note: CC0\n"
            f"{IMAGE_TWO} position 1 alt: Dunes source: Survey note: Owned\n"
            "\n"
            "Slides that cannot be shown together:\n"
            f"{exclusion_line}\n"
            "\n"
            "Text elements:\n"
            f"{ELEMENT_TITLE} (Title)\n"
            f"{ELEMENT_CAPTION} (Caption)\n"
            "\n"
            "Slide count: 6. Image: required"
        )

        self.assertEqual(joined_instructions, "Harbor fog\n\nKeep it short")
        self.assertNotIn(BLANK_INSTRUCTION, joined_instructions)
        self.assertEqual(prompt, expected)
        self.assertEqual(prompt.count(exclusion_line), 1)
        self.assertLess(prompt.index("Harbor notes"), prompt.index("Quay facts"))
        self.assertLess(prompt.index(str(IMAGE_ONE)), prompt.index(str(IMAGE_TWO)))
        self.assertIn("alt: Night quay", prompt)
        self.assertIn("source: Commons", prompt)
        self.assertIn("note: CC0", prompt)
        self.assertIn("alt: Dunes", prompt)
        self.assertIn("source: Survey", prompt)
        self.assertIn("note: Owned", prompt)
        self.assertIn("Slide count: 6. Image: required", prompt)
        self.assertLess(prompt.index("Instructions:"), prompt.index("Research:"))
        self.assertLess(prompt.index("Research:"), prompt.index("Album images:"))
        self.assertLess(
            prompt.index("Album images:"),
            prompt.index("Slides that cannot be shown together:"),
        )
        self.assertLess(
            prompt.index("Slides that cannot be shown together:"),
            prompt.index("Text elements:"),
        )
        self.assertLess(prompt.index("Text elements:"), prompt.index("Slide count:"))

    def test_empty_research_and_album_sections_say_none(self) -> None:
        """No research and no images are each None. A missing picture says so."""

        prompt: str = collection_prompt_text(
            ["Only this"],
            [],
            [],
            [],
            [],
            5,
            False,
        )

        self.assertIn("Instructions:\nOnly this", prompt)
        self.assertIn("Research:\nNone.", prompt)
        self.assertIn("Album images:\nNone.", prompt)
        self.assertIn("Slides that cannot be shown together:\nNone.", prompt)
        self.assertIn("Text elements:\nNone.", prompt)
        self.assertIn("Slide count: 5. Image: none", prompt)
        self.assertNotIn("Image: required", prompt)


if __name__ == "__main__":
    unittest.main()
