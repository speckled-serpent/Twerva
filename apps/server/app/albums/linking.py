"""Point a carousel at an album when its slides gain an image."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.carousels.editing import (
    allocate_unique_source_slug,
    new_row_id,
    slugify_carousel_name,
)
from app.models.album import Album, AlbumImage
from app.models.carousel import Carousel


def ensure_carousel_album(carousel: Carousel, our_database_session: Session) -> Album:
    """Return the carousel's album, creating one named after the carousel.

    A carousel with no images has no album until the first image is stored.
    The Content step is what later lets an operator pick a different album.

    Args:
        carousel: Carousel that is about to own an image.
        our_database_session: Open session.

    Returns:
        The album the new image should join.
    """

    if carousel.album_id is not None:
        found_album: Album | None = our_database_session.get(Album, carousel.album_id)

        if found_album is not None:

            return found_album

    album_name: str = carousel.name.strip()
    taken_slugs: set[str] = set(our_database_session.scalars(select(Album.slug)).all())
    album_slug: str = allocate_unique_source_slug(
        slugify_carousel_name(album_name),
        taken_slugs,
    )
    created_album: Album = Album(
        id=new_row_id(),
        name=album_name,
        slug=album_slug,
    )
    created_album.images = []
    our_database_session.add(created_album)
    carousel.album = created_album

    return created_album


def next_album_image_position(album: Album) -> int:
    """Return the next position at the end of an album.

    Args:
        album: Album whose images are already loaded.

    Returns:
        Zero when the album is empty, otherwise one past the last position.
    """

    positions: list[int] = [image.position for image in list(album.images)]

    if len(positions) == 0:

        return 0

    next_position: int = max(positions) + 1

    return next_position


def slide_image_rows(slide: object) -> list[AlbumImage]:
    """Return the album image a slide points at, as a list of zero or one.

    Args:
        slide: A slide, or any object with ``album_image``.

    Returns:
        The pointed-at image, or an empty list.
    """

    album_image: AlbumImage | None = getattr(slide, "album_image", None)

    if album_image is None:

        return []

    return [album_image]
