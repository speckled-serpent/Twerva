"""Album and unit writes. No new image bytes."""

import os
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api.v1.schemas import (
    SourceCreateRequest,
    SourcePatchRequest,
    SourceReadResponse,
    UnitImageMetadataPatch,
    UnitReadResponse,
    UnitWriteRequest,
)
from app.api.v1.source_writes import (
    create_content_source,
    create_unit,
    delete_content_source,
    delete_unit,
    delete_unit_image,
    get_unit_image_file,
    patch_content_source,
    patch_unit,
    patch_unit_image_metadata,
)
from app.api.v1.sources import get_content_source
from app.models.content_source import ContentSource, Unit, UnitImage
from app.models.enums import (
    AdvertisementType,
    BackgroundKind,
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
    ThemeStatus,
    UnitImageLicense,
)
from app.models.theme import Theme
from app.models.theme_element import ThemeElement
from app.sources.default_album import DEFAULT_ALBUM_THEME_ID
from app.sources.editing import (
    LICENSE_NOTE_DETAIL,
    collect_used_paths,
)
from app.sources.unit_theme import IMAGE_REQUIRED_DETAIL, UNKNOWN_TEXT_ELEMENT_DETAIL
from tests.test_sources import _default_source_from_catalog


class _ScalarResult:
    """Stand-in for ``session.scalars(...).all()``."""

    def __init__(self, rows: list[object]) -> None:
        self._rows: list[object] = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _MemorySourceSession:
    """Enough of a session to create an album and read it back."""

    def __init__(self) -> None:
        self.sources: list[ContentSource] = []
        self.deleted: list[object] = []
        self.commit_count: int = 0
        self.theme: Theme = Theme(
            id=DEFAULT_ALBUM_THEME_ID,
            name="Spotmu Paper v1",
            slug="spotmu-paper-v1",
            advertisement_type=AdvertisementType.CAROUSEL,
            status=ThemeStatus.DRAFT,
            page_margin=96,
            element_gap=0,
            element_margin=0,
            background_kind=BackgroundKind.COLOR,
        )
        self.theme.elements = []

    def add(self, row: object) -> None:
        if isinstance(row, ContentSource) and row not in self.sources:
            self.sources.append(row)

        if isinstance(row, Unit):
            self._attach_unit(row)

    def delete(self, row: object) -> None:
        self.deleted.append(row)

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
        if model is Theme and row_id == self.theme.id:
            return self.theme

        if model is ContentSource:
            return self._find_source(row_id)

        if model is Unit:
            return self._find_unit(row_id)

        if model is UnitImage:
            return self._find_image(row_id)

        return None

    def scalars(self, statement: object) -> _ScalarResult:
        sql: str = str(statement)

        if "sources.slug" in sql:
            return _ScalarResult([source.slug for source in self.sources])

        if "units.position" in sql:
            positions: list[int] = []

            for source in self.sources:
                positions.extend(unit.position for unit in list(source.units))

            return _ScalarResult(positions)

        return _ScalarResult([])

    def _attach_unit(self, unit: Unit) -> None:
        source: ContentSource | None = self._find_source(unit.source_id)

        if source is None:
            return

        if unit not in list(source.units):
            source.units.append(unit)

    def _find_source(self, source_id: uuid.UUID) -> ContentSource | None:
        for source in self.sources:
            if source.id == source_id:
                return source

        return None

    def _find_unit(self, unit_id: uuid.UUID) -> Unit | None:
        for source in self.sources:
            for unit in list(source.units):
                if unit.id == unit_id:
                    return unit

        return None

    def _find_image(self, image_id: uuid.UUID) -> UnitImage | None:
        for source in self.sources:
            for unit in list(source.units):
                for image in list(unit.images):
                    if image.id == image_id:
                        return image

        return None


class AlbumAndUnitWriteTests(unittest.TestCase):
    """Create, rename, edit, and the empty-unit rule."""

    def test_admin_creates_album_and_text_unit_then_reads_them_back(self) -> None:
        """A unit stores the value for the theme's text element."""

        session: _MemorySourceSession = _MemorySourceSession()
        text_element: ThemeElement = _title_element(session.theme.id)
        session.theme.elements.append(text_element)
        created: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Harbor notes", theme_id=session.theme.id),
            session,
            None,
        )
        unit: UnitReadResponse = create_unit(
            created.id,
            UnitWriteRequest(
                name="Fog",
                texts=[{
                    "theme_element_id": str(text_element.id),
                    "value": "Fog on the water",
                }],
            ),
            session,
            None,
        )
        loaded: SourceReadResponse = get_content_source(created.id, session)
        loaded_unit: UnitReadResponse = loaded.units[0]

        self.assertEqual(created.slug, "harbor-notes")
        self.assertEqual(created.units, [])
        self.assertEqual(len(loaded.units), 1)
        self.assertEqual(loaded_unit.id, unit.id)
        self.assertEqual(loaded_unit.name, "Fog")
        self.assertEqual(loaded.theme_id, session.theme.id)
        self.assertEqual(loaded_unit.images, [])
        self.assertEqual(len(loaded_unit.texts), 1)
        self.assertEqual(loaded_unit.texts[0].theme_element_id, text_element.id)
        self.assertEqual(loaded_unit.texts[0].value, "Fog on the water")

    def test_second_album_with_the_same_name_gets_a_suffixed_slug(self) -> None:
        """Slug stays unique. Rename does not change it."""

        session: _MemorySourceSession = _MemorySourceSession()
        first: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Harbor", theme_id=session.theme.id),
            session,
            None,
        )
        second: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Harbor", theme_id=session.theme.id),
            session,
            None,
        )
        renamed: SourceReadResponse = patch_content_source(
            first.id,
            SourcePatchRequest(name="Outer harbor"),
            session,
            None,
        )

        self.assertEqual(first.slug, "harbor")
        self.assertEqual(second.slug, "harbor-2")
        self.assertEqual(renamed.name, "Outer harbor")
        self.assertEqual(renamed.slug, "harbor")

    def test_missing_theme_is_not_stored(self) -> None:
        """A source without a real theme is 404 and writes nothing."""

        session: _MemorySourceSession = _MemorySourceSession()

        with self.assertRaises(HTTPException) as raised:
            create_content_source(
                SourceCreateRequest(name="Notes", theme_id=uuid.uuid4()),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(session.sources, [])
        self.assertEqual(session.commit_count, 0)

    def test_picture_theme_without_an_image_is_not_stored(self) -> None:
        """A theme that needs an image rejects a unit that has none."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.theme.background_kind = BackgroundKind.PICTURE
        created: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Empty check", theme_id=session.theme.id),
            session,
            None,
        )

        with self.assertRaises(HTTPException) as empty_error:
            create_unit(
                created.id,
                UnitWriteRequest(name="Empty"),
                session,
                None,
            )

        self.assertEqual(empty_error.exception.status_code, 400)
        self.assertEqual(empty_error.exception.detail, IMAGE_REQUIRED_DETAIL)
        self.assertEqual(get_content_source(created.id, session).units, [])

    def test_unknown_text_element_writes_nothing(self) -> None:
        """A text id from another theme is 400 and leaves the unit as it was."""

        session: _MemorySourceSession = _MemorySourceSession()
        text_element: ThemeElement = _title_element(session.theme.id)
        session.theme.elements.append(text_element)
        created: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Keep text", theme_id=session.theme.id),
            session,
            None,
        )
        unit: UnitReadResponse = create_unit(
            created.id,
            UnitWriteRequest(
                name="Stay",
                texts=[{"theme_element_id": str(text_element.id), "value": "Stay"}],
            ),
            session,
            None,
        )

        with self.assertRaises(HTTPException) as raised:
            patch_unit(
                created.id,
                unit.id,
                UnitWriteRequest(
                    name="Stay",
                    texts=[{"theme_element_id": str(uuid.uuid4()), "value": "Gone"}],
                ),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, UNKNOWN_TEXT_ELEMENT_DETAIL)
        stored: Unit | None = session.get(Unit, unit.id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.element_texts[0].value, "Stay")


class ImageMetadataAndDeleteTests(unittest.TestCase):
    """License gate, packaged file stream, and in-use deletes."""

    def test_license_outside_the_allowlist_is_rejected(self) -> None:
        """The request model does not accept a license the enum omits."""

        with self.assertRaises(ValidationError):
            UnitImageMetadataPatch.model_validate(
                {
                    "license": "copyright",
                    "source": "https://example.com/photo",
                    "license_note": "",
                },
            )

    def test_licensed_without_a_note_leaves_the_row_unchanged(self) -> None:
        """A missing note is 400 and does not commit."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.sources.append(_default_source_from_catalog())
        source: ContentSource = session.sources[0]
        unit: Unit = list(source.units)[0]
        image: UnitImage = list(unit.images)[0]
        original_license: UnitImageLicense = image.license
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
            patch_unit_image_metadata(
                source.id,
                unit.id,
                image.id,
                UnitImageMetadataPatch(
                    alt_text="Skyline",
                    license=UnitImageLicense.LICENSED,
                    source="https://example.com/rights",
                    license_note="  ",
                ),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, LICENSE_NOTE_DETAIL)
        self.assertEqual(image.license, original_license)
        self.assertEqual(image.license_note, "")
        self.assertIsNone(image.alt_text)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(session.deleted, [])

    def test_blank_image_source_leaves_the_row_unchanged(self) -> None:
        """Source is required. The previous source URL stays."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.sources.append(_default_source_from_catalog())
        source: ContentSource = session.sources[0]
        unit: Unit = list(source.units)[0]
        image: UnitImage = list(unit.images)[0]
        original_source: str = image.source

        with self.assertRaises(HTTPException) as raised:
            patch_unit_image_metadata(
                source.id,
                unit.id,
                image.id,
                UnitImageMetadataPatch(
                    license=UnitImageLicense.CC0,
                    source="   ",
                    license_note="ignored",
                ),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(image.source, original_source)
        self.assertEqual(image.license_note, "")

    def test_packaged_default_file_streams_from_the_package(self) -> None:
        """theme-defaults/ is the packaged JPEG, not a copy on disk."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.sources.append(_default_source_from_catalog())
        source: ContentSource = session.sources[0]
        unit: Unit = list(source.units)[0]
        image: UnitImage = list(unit.images)[0]

        response: FileResponse = get_unit_image_file(
            source.id,
            unit.id,
            image.id,
            session,
        )

        self.assertEqual(response.media_type, "image/jpeg")
        self.assertTrue(os.path.isfile(response.path))
        self.assertTrue(str(response.path).endswith(image.relative_path.split("/")[-1]))

    def test_delete_blocks_a_default_image_a_theme_stores(self) -> None:
        """409 comes before the empty-unit check, and the row stays."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.sources.append(_default_source_from_catalog())
        source: ContentSource = session.sources[0]
        unit: Unit = list(source.units)[0]
        image: UnitImage = list(unit.images)[0]

        with patch(
            "app.api.v1.source_writes.stored_paths_in_use",
            return_value={image.relative_path},
        ):
            with self.assertRaises(HTTPException) as image_error:
                delete_unit_image(source.id, unit.id, image.id, session, None)

            with self.assertRaises(HTTPException) as unit_error:
                delete_unit(source.id, unit.id, session, None)

            with self.assertRaises(HTTPException) as album_error:
                delete_content_source(source.id, session, None)

        self.assertEqual(image_error.exception.status_code, 409)
        self.assertEqual(unit_error.exception.status_code, 409)
        self.assertEqual(album_error.exception.status_code, 409)
        self.assertIn(image.relative_path, image_error.exception.detail)
        self.assertEqual(session.deleted, [])
        self.assertIs(session.get(UnitImage, image.id), image)
        self.assertEqual(len(get_content_source(source.id, session).units), 6)

    def test_unused_image_only_unit_cannot_drop_its_only_image(self) -> None:
        """After the in-use check, an empty unit is still 400."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.theme.background_kind = BackgroundKind.PICTURE
        session.sources.append(_default_source_from_catalog())
        source: ContentSource = session.sources[0]
        unit: Unit = list(source.units)[0]
        image: UnitImage = list(unit.images)[0]

        with patch(
            "app.api.v1.source_writes.stored_paths_in_use",
            return_value=set(),
        ):
            with self.assertRaises(HTTPException) as raised:
                delete_unit_image(source.id, unit.id, image.id, session, None)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, IMAGE_REQUIRED_DETAIL)
        self.assertEqual(session.deleted, [])


class UsedPathCollectionTests(unittest.TestCase):
    """Theme backgrounds, image elements, and artifact slides count as use."""

    def test_collect_used_paths_reads_each_store(self) -> None:
        """A path is in use only when one of those stores names it."""

        background_path: str = "albums/source/unit/lamp.jpg"
        element_path: str = "theme-defaults/seoul-skyline.jpg"
        slide_path: str = "albums/source/unit/other.jpg"
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


def _title_element(theme_id: uuid.UUID) -> ThemeElement:
    """One text element the unit form can fill."""

    text_element: ThemeElement = ThemeElement(
        id=uuid.uuid4(),
        theme_id=theme_id,
        band=ThemeElementBand.TOP,
        sort_order=0,
        content_kind=ThemeElementContentKind.TEXT,
        text_source=ThemeElementTextSource.TITLE,
        font_family="DejaVu Sans",
        font_size=32,
        font_color="#112233",
        alignment=ThemeElementAlignment.LEFT,
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
