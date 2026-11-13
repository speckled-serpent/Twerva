"""Build the user text for one generated set.

The function does not read the database and does not call a provider.
Instruction bodies go through ``instruction_prompt_text``. Blank
instruction bodies are dropped there. A research item stays even when
its body is empty. Album lines name an image id. They do not include
the bytes.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.carousels.instructions import instruction_prompt_text
from app.carousels.text_generation import TextElementPrompt


@dataclass(frozen=True)
class CollectionResearch:
    """One attached research document, already in position order."""

    title: str
    body: str


@dataclass(frozen=True)
class CollectionAlbumImage:
    """One album image the model may choose. Bytes are not included."""

    image_id: uuid.UUID
    position: int
    alt_text: str | None
    source: str
    license_note: str


@dataclass(frozen=True)
class CollectionExclusion:
    """One unordered pair. The caller passes each pair once."""

    left_name: str
    left_id: uuid.UUID
    right_name: str
    right_id: uuid.UUID


def collection_prompt_text(
    instruction_bodies: Sequence[str],
    research_items: Sequence[CollectionResearch],
    album_images: Sequence[CollectionAlbumImage],
    exclusion_pairs: Sequence[CollectionExclusion],
    text_elements: Sequence[TextElementPrompt],
    slide_count: int,
    image_required: bool,
) -> str:
    """Return the user text for one collection draft.

    Args:
        instruction_bodies: Document bodies, already in position order.
        research_items: Title plus body, already in position order.
        album_images: Id, position, alt text, source, and license note.
        exclusion_pairs: Each unordered pair once, with both names and ids.
        text_elements: Skeleton text elements, in frame order.
        slide_count: How many slides this set should contain.
        image_required: True when the skeleton needs a picture.

    Returns:
        The sections in order, then one line with the count and either
        ``Image: required`` or ``Image: none``. An empty section is
        ``None.``
    """

    instruction_body: str = instruction_prompt_text(list(instruction_bodies))
    research_body: str = "\n\n".join(_research_block(item) for item in research_items)
    album_body: str = "\n".join(_album_line(image) for image in album_images)
    exclusion_body: str = "\n".join(_exclusion_line(pair) for pair in exclusion_pairs)
    element_body: str = "\n".join(_element_line(element) for element in text_elements)
    image_label: str = "Image: none"

    if image_required:
        image_label = "Image: required"

    count_line: str = f"Slide count: {slide_count}. {image_label}"
    sections: list[str] = [
        _section("Instructions", instruction_body),
        _section("Research", research_body),
        _section("Album images", album_body),
        _section("Slides that cannot be shown together", exclusion_body),
        _section("Text elements", element_body),
        count_line,
    ]
    prompt_text: str = "\n\n".join(sections)

    return prompt_text


def _section(heading: str, body: str) -> str:
    """One headed block. An empty body is ``None.``"""

    content: str = "None." if body == "" else body
    section: str = f"{heading}:\n{content}"

    return section


def _research_block(item: CollectionResearch) -> str:
    """Title, then the body when the document has one."""

    if item.body == "":

        return item.title

    block: str = f"{item.title}\n{item.body}"

    return block


def _album_line(image: CollectionAlbumImage) -> str:
    """One album image. A missing alt is an empty alt field."""

    alt_text: str = ""

    if image.alt_text is not None:
        alt_text = image.alt_text

    line: str = (
        f"{image.image_id} position {image.position} "
        f"alt: {alt_text} source: {image.source} note: {image.license_note}"
    )

    return line


def _exclusion_line(pair: CollectionExclusion) -> str:
    """One pair, in the order the caller passed it."""

    line: str = (
        f"{pair.left_name} ({pair.left_id}) cannot be shown with "
        f"{pair.right_name} ({pair.right_id})"
    )

    return line


def _element_line(element: TextElementPrompt) -> str:
    """One skeleton text element, id then label."""

    line: str = f"{element.skeleton_element_id} ({element.label})"

    return line
