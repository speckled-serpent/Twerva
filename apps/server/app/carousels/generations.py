"""Header row for the carousel's current generation.

The header stores the generation number and the album id. Copying
instructions, research, images, and slides is a later step. Final
assembly hangs its row on this header.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.carousels.editing import new_row_id
from app.models.carousel import Carousel, CarouselGeneration


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
