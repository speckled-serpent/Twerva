"""A slide can point at an image that already belongs to the carousel's album."""

import os
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException

from app.albums.linking import (
    ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL,
    SLIDES_STILL_POINT_AT_ALBUM_DETAIL,
)
from app.api.v1.carousel_writes import (
    create_slide,
    delete_carousel_album,
    patch_slide,
    post_carousel_album,
)
from app.api.v1.carousels import get_carousel
from app.api.v1.schemas import (
    CarouselAlbumCreateRequest,
    CarouselReadResponse,
    SlideReadResponse,
    SlideWriteRequest,
)
from app.carousels.default_carousel import (
    DefaultSlideSeed,
    default_library_album_id,
    default_slide_seeds,
)
from app.carousels.slide_skeleton import IMAGE_NOT_USED_DETAIL, IMAGE_REQUIRED_DETAIL
from app.models.album import Album, AlbumImage
from app.models.carousel import Carousel, Slide
from app.models.enums import (
    BackgroundKind,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
)
from app.models.skeleton_element import SkeletonElement
from tests.test_carousel_album_link import _seed_default
from tests.test_carousel_editor_step import _create
from tests.test_carousel_writes import _MemoryCarouselSession


DEFAULT_ALBUM_ID: uuid.UUID = uuid.UUID("fb72c0d7-0519-50a1-acd9-a7cc9bf33e8a")
_OMITTED: object = object()


class SlideAlbumImageWriteTests(unittest.TestCase):
    """Store, replace, and clear a slide's album image without a new file."""

    def test_create_points_at_an_image_already_on_the_attached_album(self) -> None:
        """A new slide uses an album image that already exists. No file is added."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, album, image = _picture_carousel(session, "Plates")
        image_count: int = len(list(album.images))
        stored_path: str = image.relative_path

        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Harbor", image.id),
            session,
            None,
        )
        loaded: CarouselReadResponse = get_carousel(carousel.id, session)
        stored: Slide | None = session.get(Slide, created.id)

        self.assertEqual(created.images[0].id, image.id)
        self.assertEqual(created.images[0].relative_path, stored_path)
        self.assertEqual(len(created.images), 1)
        self.assertEqual(loaded.slides[0].images[0].id, image.id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.album_image_id, image.id)
        self.assertEqual(len(list(album.images)), image_count)
        self.assertEqual(album.images[0].relative_path, stored_path)

    def test_patch_switches_to_another_image_on_the_same_album(self) -> None:
        """Replacing the pointer does not add or remove an album file."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, album, first = _picture_carousel(session, "Plates")
        second: AlbumImage = _photo(album, 1, "albums/plates/two.jpg")
        album.images.append(second)
        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Harbor", first.id),
            session,
            None,
        )

        updated: SlideReadResponse = patch_slide(
            carousel.id,
            created.id,
            _write("Harbor", second.id),
            session,
            None,
        )
        stored: Slide | None = session.get(Slide, created.id)

        self.assertEqual(updated.images[0].id, second.id)
        self.assertEqual(updated.images[0].relative_path, second.relative_path)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.album_image_id, second.id)
        self.assertEqual(
            [image.relative_path for image in list(album.images)],
            [first.relative_path, second.relative_path],
        )

    def test_two_slides_can_point_at_the_same_album_image(self) -> None:
        """The album keeps one file when two slides use it."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, album, image = _picture_carousel(session, "Plates")

        first: SlideReadResponse = create_slide(
            carousel.id,
            _write("One", image.id),
            session,
            None,
        )
        second: SlideReadResponse = create_slide(
            carousel.id,
            _write("Two", image.id),
            session,
            None,
        )

        self.assertEqual(first.images[0].id, image.id)
        self.assertEqual(second.images[0].id, image.id)
        self.assertEqual(len(list(album.images)), 1)

    def test_an_id_from_another_album_is_rejected_and_the_pointer_stays(self) -> None:
        """A foreign image is 400. The slide keeps the image it already had."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, album, image = _picture_carousel(session, "Plates")
        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Harbor", image.id),
            session,
            None,
        )
        other: Album = _loose_album(session, "Other", "other")
        foreign: AlbumImage = _photo(other, 0, "albums/other/one.jpg")
        other.images.append(foreign)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            patch_slide(
                carousel.id,
                created.id,
                _write("Harbor", foreign.id),
                session,
                None,
            )

        stored: Slide | None = session.get(Slide, created.id)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.album_image_id, image.id)
        self.assertEqual(stored.name, "Harbor")
        self.assertEqual(len(list(album.images)), 1)
        self.assertEqual(len(list(other.images)), 1)

    def test_an_unknown_id_is_rejected_and_the_pointer_stays(self) -> None:
        """An id that is not an album image is 400 and writes nothing."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, _album, image = _picture_carousel(session, "Plates")
        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Harbor", image.id),
            session,
            None,
        )
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            patch_slide(
                carousel.id,
                created.id,
                _write("Renamed", uuid.uuid4()),
                session,
                None,
            )

        stored: Slide | None = session.get(Slide, created.id)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.album_image_id, image.id)
        self.assertEqual(stored.name, "Harbor")

    def test_a_set_id_with_no_attached_album_is_rejected(self) -> None:
        """An image cannot be stored while the carousel has no album."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = []
        carousel: CarouselReadResponse = _create(session, "Plates")
        loose: Album = _loose_album(session, "Loose", "loose")
        image: AlbumImage = _photo(loose, 0, "albums/loose/one.jpg")
        loose.images.append(image)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            create_slide(carousel.id, _write("Harbor", image.id), session, None)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, ALBUM_IMAGE_NOT_ON_CAROUSEL_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(get_carousel(carousel.id, session).slides, [])
        self.assertIsNone(get_carousel(carousel.id, session).album_id)

    def test_a_skeleton_that_needs_no_picture_rejects_a_set_id(self) -> None:
        """A color skeleton refuses an image id, even one on its album."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = []
        carousel: CarouselReadResponse = _create(session, "Notes")
        album: Album = _attach_named(session, carousel.id, "Notes photos")
        image: AlbumImage = _photo(album, 0, "albums/notes/one.jpg")
        album.images.append(image)
        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Stay"),
            session,
            None,
        )
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as patched:
            patch_slide(carousel.id, created.id, _write("Stay", image.id), session, None)

        with self.assertRaises(HTTPException) as created_with_image:
            create_slide(carousel.id, _write("Other", image.id), session, None)

        stored: Slide | None = session.get(Slide, created.id)

        self.assertEqual(patched.exception.status_code, 400)
        self.assertEqual(patched.exception.detail, IMAGE_NOT_USED_DETAIL)
        self.assertEqual(created_with_image.exception.status_code, 400)
        self.assertEqual(created_with_image.exception.detail, IMAGE_NOT_USED_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertIsNone(stored.album_image_id)
        self.assertEqual(len(get_carousel(carousel.id, session).slides), 1)
        self.assertEqual(len(list(album.images)), 1)

    def test_an_image_element_can_store_an_album_image(self) -> None:
        """A color background with an image element still needs a slide image."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = [_image_element(session.skeleton.id)]
        carousel: CarouselReadResponse = _create(session, "Frames")
        album: Album = _attach_named(session, carousel.id, "Frame photos")
        image: AlbumImage = _photo(album, 0, "albums/frames/one.jpg")
        album.images.append(image)

        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Harbor", image.id),
            session,
            None,
        )

        self.assertEqual(created.images[0].id, image.id)
        self.assertEqual(len(list(album.images)), 1)

    def test_null_on_a_picture_skeleton_is_rejected_and_the_pointer_stays(self) -> None:
        """Clearing the only image on a picture slide is a save with no image."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, _album, image = _picture_carousel(session, "Plates")
        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Harbor", image.id),
            session,
            None,
        )
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            patch_slide(carousel.id, created.id, _write("Harbor", None), session, None)

        stored: Slide | None = session.get(Slide, created.id)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, IMAGE_REQUIRED_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.album_image_id, image.id)

    def test_omitted_album_image_id_leaves_the_pointer(self) -> None:
        """A name save that does not send the field keeps the existing image."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, _album, image = _picture_carousel(session, "Plates")
        created: SlideReadResponse = create_slide(
            carousel.id,
            _write("Harbor", image.id),
            session,
            None,
        )

        updated: SlideReadResponse = patch_slide(
            carousel.id,
            created.id,
            _write("Renamed"),
            session,
            None,
        )
        stored: Slide | None = session.get(Slide, created.id)

        self.assertEqual(updated.name, "Renamed")
        self.assertEqual(updated.images[0].id, image.id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.album_image_id, image.id)

    def test_null_clears_the_pointer_when_the_skeleton_needs_no_picture(self) -> None:
        """Null drops the pointer and leaves the album image row."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        _default_carousel, default_album = _seed_default(session)
        first: Slide = list(_default_carousel.slides)[0]
        image_id: uuid.UUID | None = first.album_image_id
        paths_before: list[str] = [image.relative_path for image in list(default_album.images)]
        assert image_id is not None

        cleared: SlideReadResponse = patch_slide(
            _default_carousel.id,
            first.id,
            _write(first.name, None),
            session,
            None,
        )
        stored: Slide | None = session.get(Slide, first.id)

        self.assertEqual(cleared.images, [])
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertIsNone(stored.album_image_id)
        self.assertEqual(
            [image.relative_path for image in list(default_album.images)],
            paths_before,
        )
        self.assertEqual(len(paths_before), 6)
        self.assertEqual(len(get_carousel(_default_carousel.id, session).slides), 6)

    def test_pointing_at_an_album_image_blocks_clearing_the_album(self) -> None:
        """The stored pointer is the one album replace and clear already refuse."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        carousel, _album, image = _picture_carousel(session, "Plates")
        create_slide(carousel.id, _write("Harbor", image.id), session, None)
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            delete_carousel_album(carousel.id, session, None)

        loaded: CarouselReadResponse = get_carousel(carousel.id, session)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, SLIDES_STILL_POINT_AT_ALBUM_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(loaded.album_id, carousel.album_id)
        self.assertEqual(loaded.slides[0].images[0].id, image.id)

    def test_default_slides_still_return_their_six_photos(self) -> None:
        """Default stays on its album, and a name save does not drop a photo."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        default_carousel, default_album = _seed_default(session)
        seeds: tuple[DefaultSlideSeed, ...] = default_slide_seeds()
        first: Slide = list(default_carousel.slides)[0]

        loaded: CarouselReadResponse = get_carousel(default_carousel.id, session)
        renamed: SlideReadResponse = patch_slide(
            default_carousel.id,
            first.id,
            _write("Still the skyline"),
            session,
            None,
        )
        reread: CarouselReadResponse = get_carousel(default_carousel.id, session)

        self.assertEqual(default_library_album_id(), DEFAULT_ALBUM_ID)
        self.assertEqual(loaded.album_id, DEFAULT_ALBUM_ID)
        self.assertEqual(len(loaded.slides), 6)
        self.assertEqual(len(list(default_album.images)), 6)

        for slide, seed in zip(loaded.slides, seeds, strict=True):
            self.assertEqual(len(slide.images), 1)
            self.assertEqual(slide.images[0].id, seed.image_id)
            self.assertEqual(slide.images[0].relative_path, seed.relative_path)

        self.assertEqual(renamed.name, "Still the skyline")
        self.assertEqual(renamed.images[0].id, seeds[0].image_id)
        self.assertEqual(len(reread.slides), 6)
        self.assertEqual(
            [slide.images[0].id for slide in reread.slides],
            [seed.image_id for seed in seeds],
        )


def _write(
    name: str,
    album_image_id: uuid.UUID | None | object = _OMITTED,
) -> SlideWriteRequest:
    """Build a slide save. Omit the image field unless it was passed."""

    payload: dict[str, object] = {"name": name}

    if album_image_id is not _OMITTED:
        image_value: str | None = None if album_image_id is None else str(album_image_id)
        payload["album_image_id"] = image_value

    request: SlideWriteRequest = SlideWriteRequest.model_validate(payload)

    return request


def _picture_carousel(
    session: _MemoryCarouselSession,
    name: str,
) -> tuple[CarouselReadResponse, Album, AlbumImage]:
    """A picture carousel with one album and one image already on it."""

    session.skeleton.background_kind = BackgroundKind.PICTURE
    session.skeleton.elements = []
    created: CarouselReadResponse = _create(session, name)
    album: Album = _attach_named(session, created.id, f"{name} photos")
    image: AlbumImage = _photo(album, 0, f"albums/{album.slug}/one.jpg")
    album.images.append(image)
    loaded: CarouselReadResponse = get_carousel(created.id, session)

    return loaded, album, image


def _attach_named(session: _MemoryCarouselSession, carousel_id: uuid.UUID, name: str) -> Album:
    """Create an album by name, attach it, and return the row."""

    attached: CarouselReadResponse = post_carousel_album(
        carousel_id,
        CarouselAlbumCreateRequest(name=name),
        session,
        None,
    )
    album_id: uuid.UUID | None = attached.album_id
    assert album_id is not None
    album: Album | None = session.get(Album, album_id)
    assert album is not None

    return album


def _loose_album(session: _MemoryCarouselSession, name: str, slug: str) -> Album:
    """An album that is not attached to the carousel under test."""

    album: Album = Album(id=uuid.uuid4(), name=name, slug=slug)
    album.images = []
    session.add(album)

    return album


def _photo(album: Album, position: int, relative_path: str) -> AlbumImage:
    """An image row already on an album. No bytes are written."""

    image: AlbumImage = AlbumImage(
        id=uuid.uuid4(),
        album_id=album.id,
        position=position,
        relative_path=relative_path,
        media_type=SlideImageMediaType.JPEG,
        byte_size=12,
        width=8,
        height=8,
        alt_text=None,
        license=SlideImageLicense.OWNED,
        source="bench",
        license_note="",
        intake=SlideImageIntake.UPLOAD,
        thumbnail_path=None,
    )

    return image


def _image_element(skeleton_id: uuid.UUID) -> SkeletonElement:
    """One image element. Its path is not opened."""

    element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=skeleton_id,
        band=SkeletonElementBand.MIDDLE,
        sort_order=0,
        content_kind=SkeletonElementContentKind.IMAGE,
        name="Photo",
        image_asset_ref="theme-defaults/ocean-waves.jpg",
    )

    return element


if __name__ == "__main__":
    unittest.main()
