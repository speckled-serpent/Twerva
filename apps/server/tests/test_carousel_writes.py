"""Album and slide writes. No new image bytes."""

import os
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.api.v1.schemas import (
    CarouselCreateRequest,
    CarouselPatchRequest,
    CarouselReadResponse,
    SlideReadResponse,
    SlideWriteRequest,
)
from app.api.v1.carousel_writes import (
    create_carousel,
    create_slide,
    delete_carousel,
    delete_slide,
    delete_slide_image,
    get_slide_image_file,
    patch_carousel,
    patch_slide,
)
from app.api.v1.carousels import get_carousel
from app.models.album import Album, AlbumImage
from app.models.carousel import Carousel, CarouselResearchItem, Slide
from app.models.research_item import ResearchItem
from app.models.enums import (
    AdvertisementType,
    BackgroundKind,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
    SkeletonStatus,
)
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement
from app.carousels.default_carousel import DEFAULT_ALBUM_SKELETON_ID
from app.carousels.editing import collect_used_paths
from app.carousels.slide_skeleton import IMAGE_REQUIRED_DETAIL, UNKNOWN_TEXT_ELEMENT_DETAIL
from tests.test_carousels import _default_source_from_catalog


class _ScalarResult:
    """Stand-in for ``session.scalars(...).all()``."""

    def __init__(self, rows: list[object]) -> None:
        self._rows: list[object] = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _MemoryCarouselSession:
    """Enough of a session to create an album and read it back."""

    def __init__(self) -> None:
        self.carousels: list[Carousel] = []
        self.albums: list[Album] = []
        self.research_items: list[ResearchItem] = []
        self.deleted: list[object] = []
        self.commit_count: int = 0
        self.skeleton: Skeleton = Skeleton(
            id=DEFAULT_ALBUM_SKELETON_ID,
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            advertisement_type=AdvertisementType.CAROUSEL,
            status=SkeletonStatus.DRAFT,
            page_margin=96,
            element_gap=0,
            element_margin=0,
            background_kind=BackgroundKind.COLOR,
        )
        self.skeleton.elements = []

    def add(self, row: object) -> None:
        if isinstance(row, Carousel) and row not in self.carousels:
            self.carousels.append(row)

        if isinstance(row, Slide):
            self._attach_slide(row)

        if isinstance(row, Album) and row not in self.albums:
            self.albums.append(row)

        if isinstance(row, ResearchItem) and row not in self.research_items:
            self.research_items.append(row)

    def delete(self, row: object) -> None:
        self.deleted.append(row)

        if isinstance(row, ResearchItem):
            self.research_items = [
                research_item
                for research_item in self.research_items
                if research_item.id != row.id
            ]

        if isinstance(row, CarouselResearchItem):
            self._remove_research_link(row)

    def flush(self) -> None:
        return

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        return

    def refresh(self, row: object) -> None:
        persisted_at: datetime = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        if getattr(row, "created_at", None) is None:
            setattr(row, "created_at", persisted_at)

        if hasattr(row, "updated_at"):
            setattr(row, "updated_at", persisted_at)

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        if model is Skeleton and row_id == self.skeleton.id:
            return self.skeleton

        if model is Carousel:
            return self._find_source(row_id)

        if model is Slide:
            return self._find_slide(row_id)

        if model is Album:
            return self._find_album(row_id)

        if model is AlbumImage:
            return self._find_image(row_id)

        if model is ResearchItem:
            return self._find_research_item(row_id)

        return None

    def scalars(self, statement: object) -> _ScalarResult:
        sql: str = str(statement)

        if "carousel_research_items" in sql:
            return _ScalarResult(self._research_links_for_statement(statement))

        if "carousels.slug" in sql:
            return _ScalarResult([carousel.slug for carousel in self.carousels])

        if "albums.slug" in sql:
            return _ScalarResult([album.slug for album in self.albums])

        if "research_items.slug" in sql and "research_items.title" not in sql:
            return _ScalarResult([
                research_item.slug for research_item in self.research_items
            ])

        if "slides.position" in sql:
            positions: list[int] = []

            for carousel in self.carousels:
                positions.extend(slide.position for slide in list(carousel.slides))

            return _ScalarResult(positions)

        return _ScalarResult([])

    def _attach_slide(self, slide: Slide) -> None:
        carousel: Carousel | None = self._find_source(slide.carousel_id)

        if carousel is None:
            return

        if slide not in list(carousel.slides):
            carousel.slides.append(slide)

    def _find_source(self, carousel_id: uuid.UUID) -> Carousel | None:
        for carousel in self.carousels:
            if carousel.id == carousel_id:
                return carousel

        return None

    def _find_slide(self, slide_id: uuid.UUID) -> Slide | None:
        for carousel in self.carousels:
            for slide in list(carousel.slides):
                if slide.id == slide_id:
                    return slide

        return None

    def _find_album(self, album_id: uuid.UUID) -> Album | None:
        for album in self.albums:
            if album.id == album_id:
                return album

        return None

    def _find_research_item(self, research_item_id: uuid.UUID) -> ResearchItem | None:
        for research_item in self.research_items:
            if research_item.id == research_item_id:
                return research_item

        return None

    def _research_links_for_statement(self, statement: object) -> list[CarouselResearchItem]:
        links: list[CarouselResearchItem] = []

        for carousel in self.carousels:
            links.extend(list(carousel.research_links))

        research_item_id: uuid.UUID | None = _bound_research_item_id(statement)

        if research_item_id is None:
            return links

        matching_links: list[CarouselResearchItem] = [
            link for link in links if link.research_item_id == research_item_id
        ]

        return matching_links

    def _remove_research_link(self, link: CarouselResearchItem) -> None:
        carousel: Carousel | None = self._find_source(link.carousel_id)

        if carousel is None:
            return

        carousel.research_links = [
            stored
            for stored in list(carousel.research_links)
            if stored.id != link.id
        ]

    def _find_image(self, image_id: uuid.UUID) -> AlbumImage | None:
        for album in self.albums:
            for image in list(album.images):
                if image.id == image_id:
                    return image

        for carousel in self.carousels:
            for slide in list(carousel.slides):
                for image in list(slide.images):
                    if image.id == image_id:
                        return image

        return None


def _bound_research_item_id(statement: object) -> uuid.UUID | None:
    """Return the research item id bound on a link query, when there is one."""

    whereclause: object = getattr(statement, "whereclause", None)
    right: object = getattr(whereclause, "right", None)
    value: object = getattr(right, "value", None)

    if isinstance(value, uuid.UUID):

        return value

    return None


class AlbumAndSlideWriteTests(unittest.TestCase):
    """Create, rename, edit, and the empty-slide rule."""

    def test_admin_creates_album_and_text_slide_then_reads_them_back(self) -> None:
        """A slide stores the value for the skeleton's text element."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element: SkeletonElement = _title_element(session.skeleton.id)
        session.skeleton.elements.append(text_element)
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Harbor notes", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        slide: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(
                name="Fog",
                texts=[{
                    "skeleton_element_id": str(text_element.id),
                    "value": "Fog on the water",
                }],
            ),
            session,
            None,
        )
        loaded: CarouselReadResponse = get_carousel(created.id, session)
        loaded_slide: SlideReadResponse = loaded.slides[0]

        self.assertEqual(created.slug, "harbor-notes")
        self.assertEqual(created.slides, [])
        self.assertEqual(len(loaded.slides), 1)
        self.assertEqual(loaded_slide.id, slide.id)
        self.assertEqual(loaded_slide.name, "Fog")
        self.assertEqual(loaded.skeleton_id, session.skeleton.id)
        self.assertEqual(loaded_slide.images, [])
        self.assertEqual(len(loaded_slide.texts), 1)
        self.assertEqual(loaded_slide.texts[0].skeleton_element_id, text_element.id)
        self.assertEqual(loaded_slide.texts[0].value, "Fog on the water")

    def test_second_album_with_the_same_name_gets_a_suffixed_slug(self) -> None:
        """Slug stays unique. Rename does not change it."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        first: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Harbor", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        second: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Harbor", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        renamed: CarouselReadResponse = patch_carousel(
            first.id,
            CarouselPatchRequest(name="Outer harbor"),
            session,
            None,
        )

        self.assertEqual(first.slug, "harbor")
        self.assertEqual(second.slug, "harbor-2")
        self.assertEqual(renamed.name, "Outer harbor")
        self.assertEqual(renamed.slug, "harbor")

    def test_missing_skeleton_is_not_stored(self) -> None:
        """A carousel without a real skeleton is 404 and writes nothing."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()

        with self.assertRaises(HTTPException) as raised:
            create_carousel(
                CarouselCreateRequest(name="Notes", skeleton_id=uuid.uuid4()),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(session.carousels, [])
        self.assertEqual(session.commit_count, 0)

    def test_picture_skeleton_without_an_image_is_not_stored(self) -> None:
        """A skeleton that needs an image rejects a slide that has none."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Empty check", skeleton_id=session.skeleton.id),
            session,
            None,
        )

        with self.assertRaises(HTTPException) as empty_error:
            create_slide(
                created.id,
                SlideWriteRequest(name="Empty"),
                session,
                None,
            )

        self.assertEqual(empty_error.exception.status_code, 400)
        self.assertEqual(empty_error.exception.detail, IMAGE_REQUIRED_DETAIL)
        self.assertEqual(get_carousel(created.id, session).slides, [])

    def test_unknown_text_element_writes_nothing(self) -> None:
        """A text id from another skeleton is 400 and leaves the slide as it was."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        text_element: SkeletonElement = _title_element(session.skeleton.id)
        session.skeleton.elements.append(text_element)
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Keep text", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        slide: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(
                name="Stay",
                texts=[{"skeleton_element_id": str(text_element.id), "value": "Stay"}],
            ),
            session,
            None,
        )

        with self.assertRaises(HTTPException) as raised:
            patch_slide(
                created.id,
                slide.id,
                SlideWriteRequest(
                    name="Stay",
                    texts=[{"skeleton_element_id": str(uuid.uuid4()), "value": "Gone"}],
                ),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, UNKNOWN_TEXT_ELEMENT_DETAIL)
        stored: Slide | None = session.get(Slide, slide.id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.element_texts[0].value, "Stay")


class ImageFileAndDeleteTests(unittest.TestCase):
    """Packaged file stream and in-use deletes."""

    def test_packaged_default_file_streams_from_the_package(self) -> None:
        """theme-defaults/ is the packaged JPEG, not a copy on disk."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.carousels.append(_default_source_from_catalog())
        carousel: Carousel = session.carousels[0]
        slide: Slide = list(carousel.slides)[0]
        image: AlbumImage = list(slide.images)[0]

        response: FileResponse = get_slide_image_file(
            carousel.id,
            slide.id,
            image.id,
            session,
        )

        self.assertEqual(response.media_type, "image/jpeg")
        self.assertTrue(os.path.isfile(response.path))
        self.assertTrue(str(response.path).endswith(image.relative_path.split("/")[-1]))

    def test_delete_blocks_a_default_image_a_skeleton_stores(self) -> None:
        """409 comes before the empty-slide check, and the row stays."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.carousels.append(_default_source_from_catalog())
        carousel: Carousel = session.carousels[0]
        slide: Slide = list(carousel.slides)[0]
        image: AlbumImage = list(slide.images)[0]

        with patch(
            "app.api.v1.carousel_writes.stored_paths_in_use",
            return_value={image.relative_path},
        ):
            with self.assertRaises(HTTPException) as image_error:
                delete_slide_image(carousel.id, slide.id, image.id, session, None)

            with self.assertRaises(HTTPException) as slide_error:
                delete_slide(carousel.id, slide.id, session, None)

            with self.assertRaises(HTTPException) as album_error:
                delete_carousel(carousel.id, session, None)

        self.assertEqual(image_error.exception.status_code, 409)
        self.assertEqual(slide_error.exception.status_code, 409)
        self.assertEqual(album_error.exception.status_code, 409)
        self.assertIn(image.relative_path, image_error.exception.detail)
        self.assertEqual(session.deleted, [])
        self.assertIs(session.get(AlbumImage, image.id), image)
        self.assertEqual(len(get_carousel(carousel.id, session).slides), 6)

    def test_unused_image_only_slide_cannot_drop_its_only_image(self) -> None:
        """After the in-use check, an empty slide is still 400."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_kind = BackgroundKind.PICTURE
        session.carousels.append(_default_source_from_catalog())
        carousel: Carousel = session.carousels[0]
        slide: Slide = list(carousel.slides)[0]
        image: AlbumImage = list(slide.images)[0]

        with patch(
            "app.api.v1.carousel_writes.stored_paths_in_use",
            return_value=set(),
        ):
            with self.assertRaises(HTTPException) as raised:
                delete_slide_image(carousel.id, slide.id, image.id, session, None)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, IMAGE_REQUIRED_DETAIL)
        self.assertEqual(session.deleted, [])


class UsedPathCollectionTests(unittest.TestCase):
    """Skeleton backgrounds, image elements, and artifact slides count as use."""

    def test_collect_used_paths_reads_each_store(self) -> None:
        """A path is in use only when one of those stores names it."""

        background_path: str = "albums/carousel/slide/lamp.jpg"
        element_path: str = "theme-defaults/seoul-skyline.jpg"
        slide_path: str = "albums/carousel/slide/other.jpg"
        unused_path: str = "theme-defaults/hong-kong-skyline.jpg"
        candidates: set[str] = {
            background_path,
            element_path,
            slide_path,
            unused_path,
        }

        used_paths: set[str] = collect_used_paths(
            candidates,
            [background_path, None],
            [element_path],
            [
                [{"asset_ref": slide_path}, {"asset_ref": "other.jpg"}, "skip"],
                {"asset_ref": background_path},
            ],
        )

        self.assertEqual(used_paths, {background_path, element_path, slide_path})

    def test_excluding_a_slide_is_stored_on_both(self) -> None:
        """Saving an exclusion on one slide shows it on the other."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Pairs", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        harbor: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(name="Harbor"),
            session,
            None,
        )
        desert: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(name="Desert", excluded_slide_ids=[harbor.id]),
            session,
            None,
        )
        loaded: CarouselReadResponse = get_carousel(created.id, session)
        loaded_harbor: SlideReadResponse = loaded.slides[0]
        loaded_desert: SlideReadResponse = loaded.slides[1]

        self.assertEqual(loaded_harbor.excluded_slide_ids, [desert.id])
        self.assertEqual(loaded_desert.excluded_slide_ids, [harbor.id])

    def test_self_exclusion_and_an_outside_slide_write_nothing(self) -> None:
        """A slide cannot exclude itself or a slide from another carousel."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Pairs", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        other: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Other", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        harbor: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(name="Harbor"),
            session,
            None,
        )
        desert: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(name="Desert"),
            session,
            None,
        )
        outsider: SlideReadResponse = create_slide(
            other.id,
            SlideWriteRequest(name="Outsider"),
            session,
            None,
        )
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as self_error:
            patch_slide(
                created.id,
                harbor.id,
                SlideWriteRequest(name="Harbor", excluded_slide_ids=[harbor.id]),
                session,
                None,
            )

        with self.assertRaises(HTTPException) as outside_error:
            patch_slide(
                created.id,
                harbor.id,
                SlideWriteRequest(name="Harbor", excluded_slide_ids=[outsider.id]),
                session,
                None,
            )

        with self.assertRaises(HTTPException) as duplicate_error:
            patch_slide(
                created.id,
                harbor.id,
                SlideWriteRequest(
                    name="Harbor",
                    excluded_slide_ids=[desert.id, desert.id],
                ),
                session,
                None,
            )

        self.assertEqual(self_error.exception.status_code, 400)
        self.assertEqual(self_error.exception.detail, "A slide cannot exclude itself.")
        self.assertEqual(outside_error.exception.status_code, 400)
        self.assertEqual(
            outside_error.exception.detail,
            "That slide is not in this carousel.",
        )
        self.assertEqual(duplicate_error.exception.status_code, 400)
        self.assertEqual(
            duplicate_error.exception.detail,
            "Each excluded slide is stored once.",
        )
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(
            get_carousel(created.id, session).slides[0].excluded_slide_ids,
            [],
        )

    def test_deleting_a_slide_removes_its_exclusion_pairs(self) -> None:
        """The surviving slide no longer names the deleted one."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        created: CarouselReadResponse = create_carousel(
            CarouselCreateRequest(name="Pairs", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        harbor: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(name="Harbor"),
            session,
            None,
        )
        desert: SlideReadResponse = create_slide(
            created.id,
            SlideWriteRequest(name="Desert", excluded_slide_ids=[harbor.id]),
            session,
            None,
        )
        delete_slide(created.id, harbor.id, session, None)
        carousel: Carousel = session.get(Carousel, created.id)
        survivor: Slide | None = None

        assert carousel is not None

        for slide in list(carousel.slides):

            if slide.id == desert.id:
                survivor = slide

        assert survivor is not None
        self.assertEqual(list(survivor.exclusions), [])


def _title_element(skeleton_id: uuid.UUID) -> SkeletonElement:
    """One text element the slide form can fill."""

    text_element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=skeleton_id,
        band=SkeletonElementBand.TOP,
        sort_order=0,
        content_kind=SkeletonElementContentKind.TEXT,
        name="Title",
        text_source=SkeletonElementTextSource.TITLE,
        font_family="DejaVu Sans",
        font_size=32,
        font_color="#112233",
        alignment=SkeletonElementAlignment.LEFT,
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        rectangle_opacity=100,
        rectangle_radius=0,
    )

    return text_element


if __name__ == "__main__":
    unittest.main()
