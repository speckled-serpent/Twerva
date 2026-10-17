"""Attach, create, and clear the one album on a carousel."""

import inspect
import os
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from pydantic import ValidationError

from app.albums.linking import SLIDES_STILL_POINT_AT_ALBUM_DETAIL
from app.api.v1.albums import create_album
from app.api.v1.carousel_intake import add_images_from_payloads, create_slide_with_images
from app.api.v1.carousel_writes import (
    delete_carousel_album,
    post_carousel_album,
    put_carousel_album,
)
from app.api.v1.carousels import get_carousel
from app.api.v1.schemas import (
    AlbumCreateRequest,
    AlbumReadResponse,
    CarouselAlbumAttachRequest,
    CarouselAlbumCreateRequest,
    CarouselReadResponse,
)
from app.carousels.default_carousel import default_library_album_id
from app.carousels.editing import BLANK_NAME_DETAIL
from app.carousels.slide_skeleton import CarouselStepState
from app.models.album import Album, AlbumImage
from app.models.carousel import Carousel, Slide
from app.models.enums import BackgroundKind
from tests.test_carousel_editor_step import _create
from tests.test_carousel_writes import _MemoryCarouselSession
from tests.test_carousels import _default_source_from_catalog


class CarouselAlbumLinkTests(unittest.TestCase):
    """One album pointer. Slides that still use it block replace and clear."""

    def test_second_carousel_attaches_the_default_album_without_copying_files(self) -> None:
        """Two carousels can point at Default. The six photos stay one set."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        default_carousel, default_album = _seed_default(session)
        image_ids: list[uuid.UUID] = [image.id for image in list(default_album.images)]
        image_paths: list[str] = [image.relative_path for image in list(default_album.images)]
        slide_image_ids: list[uuid.UUID | None] = [
            slide.album_image_id for slide in list(default_carousel.slides)
        ]
        second: CarouselReadResponse = _create(session, "Harbor")

        attached: CarouselReadResponse = _attach(session, second.id, default_album.id)
        loaded: CarouselReadResponse = get_carousel(second.id, session)
        stored_default: Carousel | None = session.get(Carousel, default_carousel.id)

        self.assertEqual(attached.album_id, default_library_album_id())
        self.assertEqual(loaded.album_id, default_library_album_id())
        self.assertEqual(len(session.albums), 1)
        self.assertEqual([image.id for image in list(default_album.images)], image_ids)
        self.assertEqual(
            [image.relative_path for image in list(default_album.images)],
            image_paths,
        )
        self.assertIsNotNone(stored_default)
        assert stored_default is not None
        self.assertEqual(stored_default.album_id, default_library_album_id())
        self.assertEqual(
            [slide.album_image_id for slide in list(stored_default.slides)],
            slide_image_ids,
        )
        self.assertEqual(len(image_ids), 6)

    def test_clearing_or_replacing_default_is_refused_and_the_album_stays(self) -> None:
        """Default's slides still point at its photos, so the pointer stays."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        default_carousel, default_album = _seed_default(session)
        image_paths: list[str] = [image.relative_path for image in list(default_album.images)]
        empty: CarouselReadResponse = _create(session, "Spare")
        spare: CarouselReadResponse = _create_named(session, empty.id, "Spare photos")
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as cleared:
            _clear(session, default_carousel.id)

        with self.assertRaises(HTTPException) as replaced:
            _attach(session, default_carousel.id, spare.album_id)

        with self.assertRaises(HTTPException) as created:
            _create_named(session, default_carousel.id, "Another album")

        loaded: CarouselReadResponse = get_carousel(default_carousel.id, session)
        spare_album: Album | None = session.get(Album, spare.album_id)

        self.assertEqual(cleared.exception.status_code, 409)
        self.assertEqual(cleared.exception.detail, SLIDES_STILL_POINT_AT_ALBUM_DETAIL)
        self.assertEqual(replaced.exception.status_code, 409)
        self.assertEqual(replaced.exception.detail, SLIDES_STILL_POINT_AT_ALBUM_DETAIL)
        self.assertEqual(created.exception.status_code, 409)
        self.assertEqual(created.exception.detail, SLIDES_STILL_POINT_AT_ALBUM_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(loaded.album_id, default_library_album_id())
        self.assertEqual(loaded.steps.content, CarouselStepState.DONE)
        self.assertEqual(loaded.steps.slides, CarouselStepState.DONE)
        self.assertEqual(loaded.editor_step, 3)
        self.assertEqual(
            [image.relative_path for image in list(default_album.images)],
            image_paths,
        )
        self.assertIsNotNone(spare_album)
        self.assertIsNone(_album_id_named(session, "Another album"))
        self.assertEqual(get_carousel(empty.id, session).album_id, spare.album_id)
        self.assertNotEqual(spare.album_id, default_library_album_id())

    def test_putting_the_same_album_is_allowed_while_slides_point_at_it(self) -> None:
        """Staying on the album is not leaving it."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        default_carousel, default_album = _seed_default(session)

        attached: CarouselReadResponse = _attach(session, default_carousel.id, default_album.id)

        self.assertEqual(attached.album_id, default_library_album_id())
        self.assertEqual(len(list(default_album.images)), 6)

    def test_a_carousel_with_no_slide_images_can_clear_and_attach_another(self) -> None:
        """Clear drops the pointer and leaves the album. Another album can attach."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.COLOR
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Notes")
        first: CarouselReadResponse = _create_named(session, created.id, "First")
        first_album_id: uuid.UUID | None = first.album_id
        assert first_album_id is not None
        _add_imageless_slide(session, created.id, "One")
        _add_imageless_slide(session, created.id, "Two")

        cleared: CarouselReadResponse = _clear(session, created.id)
        kept_album: Album | None = session.get(Album, first_album_id)
        other: Album = _empty_album(session, "Harbor", "harbor")
        attached: CarouselReadResponse = _attach(session, created.id, other.id)
        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertIsNone(cleared.album_id)
        self.assertEqual(cleared.steps.content, CarouselStepState.DONE)
        self.assertEqual(cleared.steps.slides, CarouselStepState.DONE)
        self.assertIsNotNone(kept_album)
        assert kept_album is not None
        self.assertEqual(list(kept_album.images), [])
        self.assertEqual(kept_album.slug, "first")
        self.assertEqual(attached.album_id, other.id)
        self.assertEqual(loaded.album_id, other.id)
        self.assertEqual(loaded.editor_step, 0)
        self.assertEqual(loaded.steps.content, CarouselStepState.DONE)
        self.assertEqual(loaded.steps.slides, CarouselStepState.DONE)

    def test_picture_skeleton_steps_follow_the_album_pointer(self) -> None:
        """Attaching satisfies the album rule. Clearing locks Slides again."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.skeleton.elements = []
        created: CarouselReadResponse = _create(session, "Plates")

        self.assertEqual(created.steps.content, CarouselStepState.AVAILABLE)
        self.assertEqual(created.steps.slides, CarouselStepState.LOCKED)
        self.assertIsNone(created.album_id)

        attached: CarouselReadResponse = _create_named(session, created.id, "Plate photos")
        _add_imageless_slide(session, created.id, "One")
        _add_imageless_slide(session, created.id, "Two")
        with_slides: CarouselReadResponse = get_carousel(created.id, session)
        cleared: CarouselReadResponse = _clear(session, created.id)

        self.assertEqual(attached.steps.basic, CarouselStepState.DONE)
        self.assertEqual(attached.steps.instructions, CarouselStepState.LOCKED)
        self.assertEqual(attached.steps.content, CarouselStepState.DONE)
        self.assertEqual(attached.steps.slides, CarouselStepState.AVAILABLE)
        self.assertEqual(attached.steps.final, CarouselStepState.LOCKED)
        self.assertIsNotNone(attached.album_id)
        self.assertEqual(with_slides.steps.content, CarouselStepState.DONE)
        self.assertEqual(with_slides.steps.slides, CarouselStepState.DONE)
        self.assertIsNone(cleared.album_id)
        self.assertEqual(cleared.steps.content, CarouselStepState.AVAILABLE)
        self.assertEqual(cleared.steps.slides, CarouselStepState.LOCKED)
        self.assertEqual(cleared.editor_step, 0)
        self.assertEqual(len(session.albums), 1)

    def test_replacing_an_unused_album_leaves_that_album_row(self) -> None:
        """A carousel with no slide images can switch albums. The old row stays."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Notes")
        first: CarouselReadResponse = _create_named(session, created.id, "First")
        first_album_id: uuid.UUID | None = first.album_id
        assert first_album_id is not None

        second: CarouselReadResponse = _create_named(session, created.id, "Second")
        first_album: Album | None = session.get(Album, first_album_id)

        self.assertNotEqual(second.album_id, first_album_id)
        self.assertIsNotNone(first_album)
        assert first_album is not None
        self.assertEqual(first_album.name, "First")
        self.assertEqual(list(first_album.images), [])
        self.assertEqual(second.steps.content, CarouselStepState.DONE)

    def test_a_shared_album_can_be_cleared_when_this_carousel_has_no_slide_images(
        self,
    ) -> None:
        """Slides on the other carousel do not block this clear."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        default_carousel, default_album = _seed_default(session)
        second: CarouselReadResponse = _create(session, "Harbor")
        _attach(session, second.id, default_album.id)

        cleared: CarouselReadResponse = _clear(session, second.id)
        loaded_default: CarouselReadResponse = get_carousel(default_carousel.id, session)

        self.assertIsNone(cleared.album_id)
        self.assertEqual(loaded_default.album_id, default_library_album_id())
        self.assertEqual(len(list(default_album.images)), 6)

        _attach(session, second.id, default_album.id)
        _point_slide_at_image(session, second.id, list(default_album.images)[0])
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            _clear(session, second.id)

        still_attached: CarouselReadResponse = get_carousel(second.id, session)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, SLIDES_STILL_POINT_AT_ALBUM_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(still_attached.album_id, default_library_album_id())

    def test_a_slide_pointing_at_another_album_does_not_block_the_clear(self) -> None:
        """Only images in the album being left count."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        _default_carousel, default_album = _seed_default(session)
        created: CarouselReadResponse = _create(session, "Notes")
        attached: CarouselReadResponse = _create_named(session, created.id, "Empty")
        _point_slide_at_image(session, created.id, list(default_album.images)[0])

        cleared: CarouselReadResponse = _clear(session, created.id)

        self.assertIsNone(cleared.album_id)
        self.assertNotEqual(attached.album_id, default_album.id)
        self.assertEqual(len(list(default_album.images)), 6)

    def test_blank_name_is_400_and_unknown_album_is_404(self) -> None:
        """A blank name creates nothing. A missing album does not change the pointer."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Notes")
        commits_before: int = session.commit_count
        missing_album_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as blank:
            _create_named(session, created.id, "   ")

        with self.assertRaises(HTTPException) as missing:
            _attach(session, created.id, missing_album_id)

        loaded: CarouselReadResponse = get_carousel(created.id, session)

        self.assertEqual(blank.exception.status_code, 400)
        self.assertEqual(blank.exception.detail, BLANK_NAME_DETAIL)
        self.assertEqual(missing.exception.status_code, 404)
        self.assertIn(str(missing_album_id), str(missing.exception.detail))
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(session.albums, [])
        self.assertIsNone(loaded.album_id)
        self.assertEqual(loaded.steps.slides, CarouselStepState.AVAILABLE)

    def test_created_album_uses_the_album_name_and_slug_rules(self) -> None:
        """The carousel route and POST /albums agree on the slug."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Notes")
        library: AlbumCreateRequest = AlbumCreateRequest(name="Harbor")
        listed: AlbumReadResponse = create_album(library, session, None)
        attached: CarouselReadResponse = _create_named(session, created.id, "  Harbor  ")
        created_album: Album | None = session.get(Album, attached.album_id)

        self.assertEqual(listed.slug, "harbor")
        self.assertIsNotNone(created_album)
        assert created_album is not None
        self.assertEqual(created_album.name, "Harbor")
        self.assertEqual(created_album.slug, "harbor-2")
        self.assertEqual(list(created_album.images), [])
        self.assertEqual(attached.album_id, created_album.id)

    def test_missing_carousel_is_not_found(self) -> None:
        """An unknown carousel is 404 and does not create an album."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        missing_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised:
            _create_named(session, missing_id, "Harbor")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(session.albums, [])
        self.assertEqual(session.commit_count, 0)

    def test_bodies_reject_extra_fields(self) -> None:
        """Attach takes an album id. Create takes a name."""

        with self.assertRaises(ValidationError):
            CarouselAlbumAttachRequest.model_validate({
                "album_id": str(uuid.uuid4()),
                "name": "Harbor",
            })

        with self.assertRaises(ValidationError):
            CarouselAlbumCreateRequest.model_validate({
                "name": "Harbor",
                "album_id": str(uuid.uuid4()),
            })

    def test_clearing_when_no_album_is_attached_leaves_the_row(self) -> None:
        """Delete on an empty pointer does not write."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = _create(session, "Notes")
        commits_before: int = session.commit_count

        cleared: CarouselReadResponse = _clear(session, created.id)

        self.assertIsNone(cleared.album_id)
        self.assertEqual(cleared.steps.content, CarouselStepState.DONE)
        self.assertEqual(cleared.steps.slides, CarouselStepState.AVAILABLE)
        self.assertEqual(session.commit_count, commits_before)

    def test_slide_upload_still_creates_an_album_when_the_carousel_has_none(self) -> None:
        """This task leaves ensure_carousel_album on the slide upload path."""

        create_source: str = inspect.getsource(create_slide_with_images)
        add_source: str = inspect.getsource(add_images_from_payloads)

        self.assertIn("ensure_carousel_album(", create_source)
        self.assertIn("ensure_carousel_album(", add_source)


def _attach(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    album_id: uuid.UUID | None,
) -> CarouselReadResponse:
    """PUT an existing album on the carousel."""

    assert album_id is not None
    attached: CarouselReadResponse = put_carousel_album(
        carousel_id,
        CarouselAlbumAttachRequest(album_id=album_id),
        session,
        None,
    )

    return attached


def _create_named(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    name: str,
) -> CarouselReadResponse:
    """POST a new album by name and point the carousel at it."""

    created: CarouselReadResponse = post_carousel_album(
        carousel_id,
        CarouselAlbumCreateRequest(name=name),
        session,
        None,
    )

    return created


def _clear(session: _MemoryCarouselSession, carousel_id: uuid.UUID) -> CarouselReadResponse:
    """DELETE the carousel's album pointer."""

    cleared: CarouselReadResponse = delete_carousel_album(carousel_id, session, None)

    return cleared


def _seed_default(session: _MemoryCarouselSession) -> tuple[Carousel, Album]:
    """Put the seeded Default carousel and its one album in the session."""

    carousel: Carousel = _default_source_from_catalog()
    images: list[AlbumImage] = []

    for slide in list(carousel.slides):
        image: AlbumImage | None = slide.album_image
        assert image is not None
        slide.album_image_id = image.id
        images.append(image)

    album: Album = Album(
        id=default_library_album_id(),
        name="Default",
        slug="default",
    )
    album.images = images
    session.add(carousel)
    session.add(album)

    return carousel, album


def _empty_album(session: _MemoryCarouselSession, name: str, slug: str) -> Album:
    """Add an album with no images. The caller attaches it."""

    album: Album = Album(id=uuid.uuid4(), name=name, slug=slug)
    album.images = []
    session.add(album)

    return album


def _add_imageless_slide(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    name: str,
) -> None:
    """Add a slide with no image. Picture skeletons reject this on the write route."""

    carousel: Carousel | None = session.get(Carousel, carousel_id)
    assert carousel is not None
    slide: Slide = Slide(
        id=uuid.uuid4(),
        carousel_id=carousel_id,
        position=len(list(carousel.slides)),
        name=name,
    )
    slide.element_texts = []
    slide.exclusions = []
    slide.album_image = None
    slide.album_image_id = None
    session.add(slide)


def _point_slide_at_image(
    session: _MemoryCarouselSession,
    carousel_id: uuid.UUID,
    image: AlbumImage,
) -> None:
    """Point one new slide at an image that already lives on an album."""

    carousel: Carousel | None = session.get(Carousel, carousel_id)
    assert carousel is not None
    slide: Slide = Slide(
        id=uuid.uuid4(),
        carousel_id=carousel_id,
        position=len(list(carousel.slides)),
        name="Shared photo",
    )
    slide.element_texts = []
    slide.exclusions = []
    slide.album_image = image
    slide.album_image_id = image.id
    session.add(slide)


def _album_id_named(session: _MemoryCarouselSession, name: str) -> uuid.UUID | None:
    """Return the id of an album with this name, or null."""

    for album in session.albums:

        if album.name == name:

            return album.id

    return None


if __name__ == "__main__":
    unittest.main()
