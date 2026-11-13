"""Write one generated set of draft slides.

The count comes from the global default. Instruction text is not parsed
for a number. This module does not draw frames and does not call
``draft_slide_text``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.carousel_writes import (
    _clear_exclusion_pairs,
    _next_slide_position,
    _store_draft_texts,
)
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.carousels.generations import replace_current_generation_snapshot
from app.carousels.collection_generation import (
    DraftedCollectionSlide,
    DraftedSlideCollection,
)
from app.carousels.collection_prompt import (
    CollectionAlbumImage,
    CollectionExclusion,
    CollectionResearch,
    collection_prompt_text,
)
from app.carousels.editing import new_row_id
from app.carousels.instructions import instruction_prompt_text
from app.carousels.slide_skeleton import (
    IMAGE_REQUIRED_DETAIL,
    skeleton_requires_image,
    skeleton_text_elements,
)
from app.carousels.text_generation import (
    TextElementPrompt,
    TextGenerationError,
    TextGenerationProvider,
)
from app.global_settings import slide_count_or_global_default
from app.models.album import Album, AlbumImage
from app.models.carousel import (
    Carousel,
    CarouselInstruction,
    CarouselResearchItem,
    Slide,
    SlideDraftBatch,
    SlideElementText,
)
from app.models.enums import SlideTextStatus
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement


NO_INSTRUCTION_TEXT_DETAIL: str = "Add instruction text before generating slides."
NO_ALBUM_DETAIL: str = "Attach an album on Content first."
EMPTY_ALBUM_DETAIL: str = "This album has no images yet."
PENDING_BATCH_DETAIL: str = (
    "Accept or discard the generated set before generating another."
)
PENDING_BATCH_STATUS: str = "pending"
ACCEPTED_BATCH_STATUS: str = "accepted"
DISCARDED_BATCH_STATUS: str = "discarded"
NO_TEXT_ELEMENTS_DETAIL: str = "This skeleton has no text elements to draft."
EMPTY_BATCH_DETAIL: str = "This set has no slides to accept."
BATCH_NOT_FOUND_DETAIL: str = "Slide draft batch not found."


def write_generated_slide_collection(
    our_database_session: Session,
    carousel: Carousel,
    skeleton: Skeleton,
    provider_or_http: Callable[[], TextGenerationProvider],
) -> None:
    """Draft a set and append it. A refusal writes nothing.

    Args:
        our_database_session: Open session. One commit stores the batch
            and its slides.
        carousel: The carousel being filled, with instructions, research,
            slides, and the album loaded.
        skeleton: That carousel's skeleton, with elements loaded.
        provider_or_http: Returns the provider, or raises HTTP 409 when
            Generate is off. Called only after the carousel checks pass.

    Raises:
        HTTPException: The carousel is not ready, a set is already
            pending, or the provider did not return a draft.
    """

    instruction_bodies: list[str] = _instruction_bodies(carousel)
    text_elements: list[TextElementPrompt] = _text_prompts(skeleton)
    image_required: bool = skeleton_requires_image(skeleton)
    album_images: list[AlbumImage] = _album_images(carousel, our_database_session)
    _reject_when_not_ready(
        instruction_bodies,
        text_elements,
        image_required,
        carousel.album_id,
        album_images,
        carousel,
    )
    provider: TextGenerationProvider = provider_or_http()
    slide_count: int = slide_count_or_global_default(None)

    try:
        drafted_collection: DraftedSlideCollection = provider.draft_slide_collection(
            instruction_bodies,
            _research_prompts(carousel),
            _album_prompts(album_images),
            _exclusion_prompts(carousel),
            text_elements,
            slide_count,
            image_required,
        )
    except TextGenerationError as generation_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(generation_error),
        ) from generation_error

    try:
        _append_drafted_slides(
            our_database_session,
            carousel,
            skeleton,
            drafted_collection.slides,
            slide_count,
            album_images,
        )
        replace_current_generation_snapshot(carousel.id, our_database_session)
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail="Slides could not be saved.",
        )
    except HTTPException:
        raise
    except Exception:
        our_database_session.rollback()

        raise


def accept_generated_slide_collection(
    our_database_session: Session,
    carousel: Carousel,
    skeleton: Skeleton,
    batch_id: uuid.UUID,
) -> None:
    """Make one pending set live. Other slides stay as they are.

    Args:
        our_database_session: Open session. One commit stores the accept.
        carousel: The carousel that owns the batch, with slides loaded.
        skeleton: That carousel's skeleton.
        batch_id: The pending set to accept.

    Raises:
        HTTPException: The batch is not a pending set on this carousel,
            the set has no slides, or a picture slide has no image.
    """

    batch: SlideDraftBatch = _pending_batch_or_raise(carousel, batch_id)
    batch_slides: list[Slide] = _slides_in_batch(carousel, batch.id)

    if len(batch_slides) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=EMPTY_BATCH_DETAIL,
        )

    if skeleton_requires_image(skeleton):

        for slide in batch_slides:

            if slide.album_image_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=IMAGE_REQUIRED_DETAIL,
                )

    for slide in batch_slides:
        _accept_slide_text(slide)

    batch.status = ACCEPTED_BATCH_STATUS
    replace_current_generation_snapshot(carousel.id, our_database_session)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slides could not be saved.",
    )


def discard_generated_slide_collection(
    our_database_session: Session,
    carousel: Carousel,
    batch_id: uuid.UUID,
) -> None:
    """Delete one pending set and keep the batch row as discarded.

    Args:
        our_database_session: Open session. One commit stores the discard.
        carousel: The carousel that owns the batch, with slides loaded.
        batch_id: The pending set to discard.

    Raises:
        HTTPException: The batch is not a pending set on this carousel.
    """

    batch: SlideDraftBatch = _pending_batch_or_raise(carousel, batch_id)

    for slide in _slides_in_batch(carousel, batch.id):
        _clear_exclusion_pairs(slide, carousel, our_database_session)
        our_database_session.delete(slide)

    batch.status = DISCARDED_BATCH_STATUS
    replace_current_generation_snapshot(carousel.id, our_database_session)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Slides could not be discarded.",
    )


def _pending_batch_or_raise(carousel: Carousel, batch_id: uuid.UUID) -> SlideDraftBatch:
    """Return the pending set on this carousel, or raise HTTP 404."""

    for batch in list(carousel.draft_batches):

        if (
            batch.id == batch_id
            and batch.carousel_id == carousel.id
            and batch.status == PENDING_BATCH_STATUS
        ):

            return batch

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=BATCH_NOT_FOUND_DETAIL,
    )


def _slides_in_batch(carousel: Carousel, batch_id: uuid.UUID) -> list[Slide]:
    """Return the slides stored on this generated set."""

    batch_slides: list[Slide] = [
        slide
        for slide in list(carousel.slides)
        if slide.draft_batch_id == batch_id
    ]

    return batch_slides


def _accept_slide_text(slide: Slide) -> None:
    """Copy draft copy onto the live value and mark the slide live."""

    for element_text in list(slide.element_texts):
        copied_value: str = _copied_draft_value(element_text)
        element_text.value = copied_value
        element_text.draft_value = None

    slide.text_status = SlideTextStatus.LIVE


def _copied_draft_value(element_text: SlideElementText) -> str:
    """Return the draft string, or an empty string when none was stored."""

    if element_text.draft_value is None:

        return ""

    copied_value: str = element_text.draft_value

    return copied_value


def _reject_when_not_ready(
    instruction_bodies: list[str],
    text_elements: list[TextElementPrompt],
    image_required: bool,
    album_id: uuid.UUID | None,
    album_images: list[AlbumImage],
    carousel: Carousel,
) -> None:
    """Refuse before the provider runs. Nothing is written."""

    if instruction_prompt_text(instruction_bodies) == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_INSTRUCTION_TEXT_DETAIL,
        )

    if len(text_elements) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_TEXT_ELEMENTS_DETAIL,
        )

    if image_required and album_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_ALBUM_DETAIL,
        )

    if image_required and len(album_images) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=EMPTY_ALBUM_DETAIL,
        )

    if _has_pending_batch(carousel):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=PENDING_BATCH_DETAIL,
        )


def _append_drafted_slides(
    our_database_session: Session,
    carousel: Carousel,
    skeleton: Skeleton,
    drafted_slides: tuple[DraftedCollectionSlide, ...],
    slide_count: int,
    album_images: list[AlbumImage],
) -> None:
    """Insert the pending batch and one draft slide per drafted item."""

    batch: SlideDraftBatch = SlideDraftBatch(
        id=new_row_id(),
        carousel_id=carousel.id,
        status=PENDING_BATCH_STATUS,
        slide_count=slide_count,
    )
    batch.carousel = carousel
    our_database_session.add(batch)
    images_by_id: dict[uuid.UUID, AlbumImage] = {
        image.id: image for image in album_images
    }
    next_position: int = _next_slide_position(carousel.id, our_database_session)

    for offset, drafted_slide in enumerate(drafted_slides):
        drafted: DraftedCollectionSlide = drafted_slide
        created_slide: Slide = Slide(
            id=new_row_id(),
            carousel_id=carousel.id,
            position=next_position + offset,
            name=drafted.name,
            text_status=SlideTextStatus.DRAFT,
            draft_batch_id=batch.id,
        )
        created_slide.draft_batch = batch
        created_slide.element_texts = []
        created_slide.exclusions = []
        chosen_image: AlbumImage | None = None

        if drafted.album_image_id is not None:
            chosen_image = images_by_id.get(drafted.album_image_id)

        if chosen_image is not None:
            created_slide.images = [chosen_image]
        else:
            created_slide.album_image_id = drafted.album_image_id

        our_database_session.add(created_slide)
        _store_draft_texts(
            created_slide,
            _draft_pairs(skeleton, drafted),
            our_database_session,
        )


def _draft_pairs(
    skeleton: Skeleton,
    drafted: DraftedCollectionSlide,
) -> list[tuple[uuid.UUID, str]]:
    """One draft string per text element, in frame order."""

    values_by_element_id: dict[uuid.UUID, str] = drafted.values_by_element_id
    pairs: list[tuple[uuid.UUID, str]] = [
        (element.id, values_by_element_id.get(element.id, ""))
        for element in skeleton_text_elements(skeleton)
    ]

    return pairs


def _instruction_bodies(carousel: Carousel) -> list[str]:
    """Return instruction bodies from position 0 upward."""

    ordered_documents: list[CarouselInstruction] = sorted(
        list(carousel.instructions),
        key=_instruction_position,
    )
    bodies: list[str] = [document.body for document in ordered_documents]

    return bodies


def _instruction_position(document: CarouselInstruction) -> int:
    """Return the sort key for an instruction document."""

    position: int = document.position

    return position


def _text_prompts(skeleton: Skeleton) -> list[TextElementPrompt]:
    """Label each text element by its name for the provider."""

    prompts: list[TextElementPrompt] = []

    for element in skeleton_text_elements(skeleton):
        label: str = element.name.strip()

        if label == "":
            label = "text"

        prompt: TextElementPrompt = TextElementPrompt(
            skeleton_element_id=element.id,
            label=label,
        )
        prompts.append(prompt)

    return prompts


def _album_images(
    carousel: Carousel,
    our_database_session: Session,
) -> list[AlbumImage]:
    """Return the attached album's images in position order."""

    if carousel.album_id is None:

        return []

    album: Album | None = carousel.album

    if album is None:
        found_album: Album | None = our_database_session.get(Album, carousel.album_id)
        album = found_album

    if album is None:

        return []

    images: list[AlbumImage] = sorted(list(album.images), key=_image_position)

    return images


def _image_position(image: AlbumImage) -> int:
    """Return the sort key for an album image."""

    position: int = image.position

    return position


def _album_prompts(images: list[AlbumImage]) -> list[CollectionAlbumImage]:
    """Describe each image. The bytes are not included."""

    prompts: list[CollectionAlbumImage] = [
        CollectionAlbumImage(
            image_id=image.id,
            position=image.position,
            alt_text=image.alt_text,
            source=image.source,
            license_note=image.license_note,
        )
        for image in images
    ]

    return prompts


def _research_prompts(carousel: Carousel) -> list[CollectionResearch]:
    """Return attached research in position order, including an empty body."""

    ordered_links: list[CarouselResearchItem] = sorted(
        list(carousel.research_links),
        key=_research_position,
    )
    prompts: list[CollectionResearch] = [
        CollectionResearch(
            title=link.research_item.title,
            body=link.research_item.body,
        )
        for link in ordered_links
    ]

    return prompts


def _research_position(link: CarouselResearchItem) -> int:
    """Return the sort key for an attached research item."""

    position: int = link.position

    return position


def _exclusion_prompts(carousel: Carousel) -> list[CollectionExclusion]:
    """Collapse both stored directions into one pair."""

    slides: list[Slide] = sorted(list(carousel.slides), key=_slide_position)
    slides_by_id: dict[uuid.UUID, Slide] = {slide.id: slide for slide in slides}
    seen_pairs: set[frozenset[uuid.UUID]] = set()
    prompts: list[CollectionExclusion] = []

    for slide in slides:

        for exclusion in list(slide.exclusions):
            pair_key: frozenset[uuid.UUID] = frozenset(
                {slide.id, exclusion.excluded_slide_id},
            )
            other_slide: Slide | None = slides_by_id.get(exclusion.excluded_slide_id)

            if (
                exclusion.excluded_slide_id == slide.id
                or pair_key in seen_pairs
                or other_slide is None
            ):
                continue

            seen_pairs.add(pair_key)
            prompt: CollectionExclusion = CollectionExclusion(
                left_name=slide.name,
                left_id=slide.id,
                right_name=other_slide.name,
                right_id=other_slide.id,
            )
            prompts.append(prompt)

    return prompts


def _slide_position(slide: Slide) -> int:
    """Return the sort key for a slide."""

    position: int = slide.position

    return position


def _has_pending_batch(carousel: Carousel) -> bool:
    """Return true when this carousel already has a set waiting for review."""

    for batch in list(carousel.draft_batches):

        if batch.status == PENDING_BATCH_STATUS:

            return True

    return False
