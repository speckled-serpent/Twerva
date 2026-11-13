"""Validate one generated set and build its chat-completion body.

Parsing reads a JSON object. It does not read the database and does
not call the network. A bad object raises ``TextGenerationError`` and
returns nothing. ``draft_slide_text`` is unchanged.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.carousels.collection_prompt import (
    CollectionAlbumImage,
    CollectionExclusion,
    CollectionResearch,
    collection_prompt_text,
)
from app.carousels.text_generation import (
    MAX_DRAFTED_NAME_LENGTH,
    TEXT_GENERATION_FAILED_DETAIL,
    TextElementPrompt,
    TextGenerationError,
)


COLLECTION_RESPONSE_SHAPE: str = (
    '{"slides": [{"name": "...", "texts": ['
    '{"skeleton_element_id": "...", "value": "..."}], '
    '"album_image_id": "..."}]}'
)


@dataclass(frozen=True)
class DraftedCollectionSlide:
    """One slide from a generated set."""

    name: str
    values_by_element_id: dict[uuid.UUID, str]
    album_image_id: uuid.UUID | None


@dataclass(frozen=True)
class DraftedSlideCollection:
    """The slides from one generated set, in order."""

    slides: tuple[DraftedCollectionSlide, ...]


def parse_slide_collection(
    payload: object,
    slide_count: int,
    text_elements: Sequence[TextElementPrompt],
    allowed_image_ids: Sequence[uuid.UUID],
    image_required: bool,
) -> DraftedSlideCollection:
    """Read one collection object into a draft of ``slide_count`` slides.

    Args:
        payload: The JSON object. ``album_image_id`` may be null.
        slide_count: How many slides the object must contain.
        text_elements: The skeleton text elements each slide must fill.
        allowed_image_ids: Album image ids the model may choose.
        image_required: True when every slide must choose an image.

    Returns:
        The slides in order. Names are collapsed and cut to
        ``MAX_DRAFTED_NAME_LENGTH``. An empty text value is kept.

    Raises:
        TextGenerationError: The object is not a usable draft.
    """

    if not isinstance(payload, dict):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    raw_slides: object = payload.get("slides")

    if not isinstance(raw_slides, list) or len(raw_slides) != slide_count:
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    allowed_ids: set[uuid.UUID] = set(allowed_image_ids)
    slides: list[DraftedCollectionSlide] = []

    for raw_slide in raw_slides:

        slide: DraftedCollectionSlide = _parse_collection_slide(
            raw_slide,
            text_elements,
            allowed_ids,
            image_required,
        )
        slides.append(slide)

    drafted: DraftedSlideCollection = DraftedSlideCollection(slides=tuple(slides))

    return drafted


def openai_collection_request_body(
    model: str,
    instruction_bodies: Sequence[str],
    research_items: Sequence[CollectionResearch],
    album_images: Sequence[CollectionAlbumImage],
    exclusion_pairs: Sequence[CollectionExclusion],
    text_elements: Sequence[TextElementPrompt],
    slide_count: int,
    image_required: bool,
) -> dict[str, object]:
    """Build the chat completion body. The key is not part of the body.

    Args:
        model: The model name. The API key is not included.
        instruction_bodies: Document bodies, already in position order.
        research_items: Title plus body, already in position order.
        album_images: Id, position, alt text, source, and license note.
        exclusion_pairs: Each unordered pair once.
        text_elements: Skeleton text elements, in frame order.
        slide_count: How many slides this set should contain.
        image_required: True when the skeleton needs a picture.

    Returns:
        A JSON-object chat completion. The user message is
        ``collection_prompt_text`` plus the collection JSON shape.
    """

    prompt_text: str = collection_prompt_text(
        instruction_bodies,
        research_items,
        album_images,
        exclusion_pairs,
        text_elements,
        slide_count,
        image_required,
    )
    user_content: str = f"{prompt_text}\n{COLLECTION_RESPONSE_SHAPE}"
    request_body: dict[str, object] = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You draft a set of carousel slides. Reply with JSON only.",
            },
            {"role": "user", "content": user_content},
        ],
    }

    return request_body


def _parse_collection_slide(
    raw_slide: object,
    text_elements: Sequence[TextElementPrompt],
    allowed_image_ids: set[uuid.UUID],
    image_required: bool,
) -> DraftedCollectionSlide:
    """Read one slide. Any bad field rejects the whole object."""

    if not isinstance(raw_slide, dict):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    name: str = _collapsed_slide_name(raw_slide.get("name"))
    values_by_element_id: dict[uuid.UUID, str] = _values_by_element_id(
        raw_slide.get("texts"),
        text_elements,
    )
    album_image_id: uuid.UUID | None = _album_image_id(
        raw_slide.get("album_image_id"),
        allowed_image_ids,
        image_required,
    )
    slide: DraftedCollectionSlide = DraftedCollectionSlide(
        name=name,
        values_by_element_id=values_by_element_id,
        album_image_id=album_image_id,
    )

    return slide


def _collapsed_slide_name(raw_name: object) -> str:
    """Collapse whitespace and cut the name the way ``_drafted_name`` does."""

    if not isinstance(raw_name, str) or raw_name.strip() == "":
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    collapsed_name: str = " ".join(raw_name.split())[:MAX_DRAFTED_NAME_LENGTH]

    return collapsed_name


def _values_by_element_id(
    raw_texts: object,
    text_elements: Sequence[TextElementPrompt],
) -> dict[uuid.UUID, str]:
    """Require exactly the requested element ids. An empty value stays."""

    if not isinstance(raw_texts, list):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    expected_ids: set[uuid.UUID] = {
        element.skeleton_element_id for element in text_elements
    }
    found: dict[uuid.UUID, str] = {}

    for item in raw_texts:

        if not isinstance(item, dict):
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

        raw_element_id: object = item.get("skeleton_element_id")
        raw_value: object = item.get("value")

        if not isinstance(raw_element_id, str) or not isinstance(raw_value, str):
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

        try:
            element_id: uuid.UUID = uuid.UUID(raw_element_id)
        except ValueError as error:
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL) from error

        if element_id not in expected_ids or element_id in found:
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

        found[element_id] = raw_value

    if set(found) != expected_ids:
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    values_by_element_id: dict[uuid.UUID, str] = {
        element.skeleton_element_id: found[element.skeleton_element_id]
        for element in text_elements
    }

    return values_by_element_id


def _album_image_id(
    raw_image_id: object,
    allowed_image_ids: set[uuid.UUID],
    image_required: bool,
) -> uuid.UUID | None:
    """Choose an allowed image, or null when the skeleton needs none."""

    if raw_image_id is None:

        if image_required:
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

        return None

    if not isinstance(raw_image_id, str) or not image_required:
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    try:
        image_id: uuid.UUID = uuid.UUID(raw_image_id)
    except ValueError as error:
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL) from error

    if image_id not in allowed_image_ids:
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    return image_id
