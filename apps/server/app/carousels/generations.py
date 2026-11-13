"""Snapshot of the carousel's current generation.

The header stores the generation number and the album id. Replacing
the snapshot copies the working instructions, research, album image
ids, and slides onto that header. Other generations stay as they are.
Final assembly hangs its row on the header.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_carousel_by_id_or_raise
from app.carousels.editing import new_row_id
from app.models.album import AlbumImage
from app.models.carousel import (
    Carousel,
    CarouselGeneration,
    CarouselGenerationImage,
    CarouselGenerationInstruction,
    CarouselGenerationResearch,
    CarouselGenerationSlide,
    CarouselGenerationSlideExclusion,
    CarouselGenerationSlideText,
    CarouselInstruction,
    CarouselResearchItem,
    Slide,
    SlideExclusion,
)


def ensure_current_generation(
    carousel: Carousel,
    our_database_session: Session,
) -> CarouselGeneration:
    """Return the snapshot header for this carousel's current generation.

    A header that is already stored is returned unchanged, including
    its album id. A missing header is inserted with the carousel's
    generation number and album id, and with no child rows.

    Args:
        carousel: The working carousel. ``generation_number`` is the
            generation the header belongs to.
        our_database_session: Session that will hold a new header.

    Returns:
        The header for ``carousel.generation_number``.
    """

    for generation in list(carousel.generations):

        if generation.generation_number == carousel.generation_number:

            return generation

    created_generation: CarouselGeneration = CarouselGeneration(
        id=new_row_id(),
        carousel_id=carousel.id,
        generation_number=carousel.generation_number,
        album_id=carousel.album_id,
    )
    carousel.generations.append(created_generation)
    our_database_session.add(created_generation)

    return created_generation


def replace_current_generation_snapshot(
    carousel_id: uuid.UUID,
    our_database_session: Session,
) -> CarouselGeneration:
    """Rewrite the current generation's snapshot from the working rows.

    The header's album id is set from the carousel. Its instruction,
    research, image, slide, text, and exclusion rows are deleted and
    inserted again. A blank instruction body is kept. A null album
    stores no image rows. Another generation number is not changed.
    Working slides, instructions, research links, and album images stay.
    Assemblies, draft batches, campaign rows, and artifacts are not
    written. ``generation_number`` stays. The caller commits.

    Args:
        carousel_id: The carousel whose current generation is copied.
        our_database_session: Open session. This function flushes and
            does not commit.

    Returns:
        The current generation, with its children replaced.

    Raises:
        HTTPException: No carousel has this id.
    """

    carousel: Carousel = fetch_carousel_by_id_or_raise(
        carousel_id,
        our_database_session,
    )
    our_database_session.flush()
    _expire_working_rows(carousel, our_database_session)
    generation: CarouselGeneration = ensure_current_generation(
        carousel,
        our_database_session,
    )
    generation.album_id = carousel.album_id
    _delete_snapshot_children(generation, our_database_session)
    _copy_instructions(generation, carousel, our_database_session)
    _copy_research(generation, carousel, our_database_session)
    _copy_images(generation, carousel, our_database_session)
    copied_slides: dict[uuid.UUID, CarouselGenerationSlide] = _copy_slides(
        generation,
        carousel,
        our_database_session,
    )
    our_database_session.flush()
    _copy_exclusions(carousel, copied_slides, our_database_session)

    return generation


def refresh_generation_snapshots_for_skeleton(
    skeleton_id: uuid.UUID,
    our_database_session: Session,
) -> None:
    """Refresh the current snapshot of every carousel on this skeleton.

    Pending slide writes are flushed first. Each carousel is refreshed
    on its own current generation number. A skeleton with no carousels
    changes nothing.

    Args:
        skeleton_id: The skeleton whose bound carousels are copied.
        our_database_session: Open session. This function flushes and
            does not commit.
    """

    our_database_session.flush()
    carousel_id_rows: list[tuple[uuid.UUID]] = list(
        our_database_session.execute(
            select(Carousel.id).where(Carousel.skeleton_id == skeleton_id),
        ).all(),
    )

    for carousel_id_row in carousel_id_rows:
        replace_current_generation_snapshot(carousel_id_row[0], our_database_session)


def _expire_working_rows(carousel: Carousel, our_database_session: Session) -> None:
    """Drop cached working rows so the copy reads the flushed write."""

    our_database_session.expire(
        carousel,
        ["slides", "instructions", "research_links", "album"],
    )

    for slide in list(carousel.slides):
        our_database_session.expire(slide, ["element_texts", "exclusions"])

    if carousel.album is not None:
        our_database_session.expire(carousel.album, ["images"])


def _delete_snapshot_children(
    generation: CarouselGeneration,
    our_database_session: Session,
) -> None:
    """Drop this generation's copied rows. The header stays.

    Slide text and exclusions go with the slide. The collections are
    expired so the copies that follow are the only rows in memory.
    """

    for slide in list(generation.slides):
        our_database_session.delete(slide)

    for instruction in list(generation.instructions):
        our_database_session.delete(instruction)

    for research in list(generation.research_items):
        our_database_session.delete(research)

    for image in list(generation.images):
        our_database_session.delete(image)

    our_database_session.flush()
    our_database_session.expire(
        generation,
        ["slides", "instructions", "research_items", "images"],
    )


def _copy_instructions(
    generation: CarouselGeneration,
    carousel: Carousel,
    our_database_session: Session,
) -> None:
    """Copy every instruction body, including an empty string."""

    documents: list[CarouselInstruction] = sorted(
        list(carousel.instructions),
        key=_instruction_position,
    )

    for document in documents:
        copied_instruction: CarouselGenerationInstruction = CarouselGenerationInstruction(
            id=new_row_id(),
            generation_id=generation.id,
            position=document.position,
            body=document.body,
        )
        generation.instructions.append(copied_instruction)
        our_database_session.add(copied_instruction)


def _copy_research(
    generation: CarouselGeneration,
    carousel: Carousel,
    our_database_session: Session,
) -> None:
    """Copy each attached research item's id, title, and body."""

    links: list[CarouselResearchItem] = sorted(
        list(carousel.research_links),
        key=_research_position,
    )

    for link in links:
        copied_research: CarouselGenerationResearch = CarouselGenerationResearch(
            id=new_row_id(),
            generation_id=generation.id,
            position=link.position,
            research_item_id=link.research_item_id,
            title=link.research_item.title,
            body=link.research_item.body,
        )
        generation.research_items.append(copied_research)
        our_database_session.add(copied_research)


def _copy_images(
    generation: CarouselGeneration,
    carousel: Carousel,
    our_database_session: Session,
) -> None:
    """Copy the album's image ids in position order. A null album copies none."""

    if carousel.album_id is None or carousel.album is None:

        return

    images: list[AlbumImage] = sorted(list(carousel.album.images), key=_image_position)

    for image in images:
        copied_image: CarouselGenerationImage = CarouselGenerationImage(
            id=new_row_id(),
            generation_id=generation.id,
            position=image.position,
            album_image_id=image.id,
        )
        generation.images.append(copied_image)
        our_database_session.add(copied_image)


def _copy_slides(
    generation: CarouselGeneration,
    carousel: Carousel,
    our_database_session: Session,
) -> dict[uuid.UUID, CarouselGenerationSlide]:
    """Copy slide name, status, image, and element text. Return them by source id."""

    working_slides: list[Slide] = sorted(list(carousel.slides), key=_slide_position)
    copied_by_source: dict[uuid.UUID, CarouselGenerationSlide] = {}

    for slide in working_slides:
        copied_slide: CarouselGenerationSlide = CarouselGenerationSlide(
            id=new_row_id(),
            generation_id=generation.id,
            position=slide.position,
            name=slide.name,
            text_status=slide.text_status,
            album_image_id=slide.album_image_id,
            source_slide_id=slide.id,
        )

        for element_text in list(slide.element_texts):
            copied_text: CarouselGenerationSlideText = CarouselGenerationSlideText(
                id=new_row_id(),
                generation_slide_id=copied_slide.id,
                skeleton_element_id=element_text.skeleton_element_id,
                value=element_text.value,
                draft_value=element_text.draft_value,
            )
            copied_slide.texts.append(copied_text)

        generation.slides.append(copied_slide)
        our_database_session.add(copied_slide)
        copied_by_source[slide.id] = copied_slide

    return copied_by_source


def _copy_exclusions(
    carousel: Carousel,
    copied_by_source: dict[uuid.UUID, CarouselGenerationSlide],
    our_database_session: Session,
) -> None:
    """Copy both directions of each exclusion onto the snapshot slides."""

    working_slides: list[Slide] = sorted(list(carousel.slides), key=_slide_position)

    for slide in working_slides:

        for exclusion in list(slide.exclusions):
            copied_pair: CarouselGenerationSlideExclusion | None = _copied_exclusion(
                exclusion,
                copied_by_source,
            )

            if copied_pair is None:

                continue

            our_database_session.add(copied_pair)


def _copied_exclusion(
    exclusion: SlideExclusion,
    copied_by_source: dict[uuid.UUID, CarouselGenerationSlide],
) -> CarouselGenerationSlideExclusion | None:
    """Return one copied pair, or null when either slide was not copied."""

    source_slide: CarouselGenerationSlide | None = copied_by_source.get(exclusion.slide_id)
    excluded_slide: CarouselGenerationSlide | None = copied_by_source.get(
        exclusion.excluded_slide_id,
    )

    if source_slide is None or excluded_slide is None:

        return None

    copied_pair: CarouselGenerationSlideExclusion = CarouselGenerationSlideExclusion(
        id=new_row_id(),
        generation_slide_id=source_slide.id,
        excluded_generation_slide_id=excluded_slide.id,
    )
    source_slide.exclusions.append(copied_pair)

    return copied_pair


def _instruction_position(document: CarouselInstruction) -> int:
    """Return the stored instruction position."""

    position: int = document.position

    return position


def _research_position(link: CarouselResearchItem) -> int:
    """Return the stored research-link position."""

    position: int = link.position

    return position


def _image_position(image: AlbumImage) -> int:
    """Return the stored album-image position."""

    position: int = image.position

    return position


def _slide_position(slide: Slide) -> tuple[int, str]:
    """Return position, then id, matching the backfill order."""

    order: tuple[int, str] = (slide.position, str(slide.id))

    return order
