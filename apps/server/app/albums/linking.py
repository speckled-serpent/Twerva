"""Decide whether a carousel may leave an album, and whether an image is on it.

Replacing or clearing the album is refused while a slide on the carousel
still points at an image in the album being left. Storing a slide image
does not create an album.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.album import Album, AlbumImage
from app.models.carousel import Carousel, Slide


SLIDES_STILL_POINT_AT_ALBUM_DETAIL: str = (
    "Slides still point at that album's images, so clear those slide images first."
)
ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL: str = "That image is not on this carousel's album."


def slides_point_at_album(
    carousel: Carousel,
    album_id: uuid.UUID,
    our_database_session: Session,
) -> bool:
    """Return true when a slide on this carousel points at that album.

    The check is ``album_image_id`` on this carousel's slides. A slide
    on another carousel can keep pointing at the same images. This does
    not write, and it does not treat the Default album as a special case.

    Args:
        carousel: The carousel that would leave the album. Slides loaded.
        album_id: The album being replaced or cleared.
        our_database_session: Open session, used to load the image row.

    Returns:
        True when at least one slide still points at an image in that album.
    """

    for slide in list(carousel.slides):
        image_album_id: uuid.UUID | None = _image_album_id(slide, our_database_session)

        if image_album_id == album_id:

            return True

    return False


def album_image_on_carousel(
    carousel: Carousel,
    album_image_id: uuid.UUID,
    our_database_session: Session,
) -> AlbumImage:
    """Return the image when it belongs to the carousel's attached album.

    Args:
        carousel: The carousel being saved. ``album_id`` is the attach.
        album_image_id: The image the slide should point at.
        our_database_session: Open session.

    Returns:
        The album image row. This does not copy the file.

    Raises:
        ValueError: The carousel has no album, the id is unknown, or the
            image belongs to a different album. The message is
            ``ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL``.
    """

    attached_album_id: uuid.UUID | None = carousel.album_id

    if attached_album_id is None:
        raise ValueError(ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL)

    found_image: AlbumImage | None = our_database_session.get(AlbumImage, album_image_id)

    if found_image is None or found_image.album_id != attached_album_id:
        raise ValueError(ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL)

    return found_image


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


def _image_album_id(slide: Slide, our_database_session: Session) -> uuid.UUID | None:
    """Return the album that owns the image this slide points at.

    Args:
        slide: A slide on the carousel being changed.
        our_database_session: Open session, used when the image row is
            not already on the slide.

    Returns:
        The image's ``album_id``, or null when the slide has no image.
    """

    image_id: uuid.UUID | None = slide.album_image_id
    pointed_image: AlbumImage | None = slide.album_image

    if image_id is None and pointed_image is not None:
        image_id = pointed_image.id

    if image_id is None:

        return None

    found_image: AlbumImage | None = our_database_session.get(AlbumImage, image_id)

    if found_image is not None:

        return found_image.album_id

    if pointed_image is not None and pointed_image.id == image_id:

        return pointed_image.album_id

    return None


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
