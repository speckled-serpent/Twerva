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
from app.models.enums import ContentSourceKind, UnitImageLicense
from app.sources.editing import (
    EMPTY_UNIT_DETAIL,
    LICENSE_NOTE_DETAIL,
    collect_used_paths,
)
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
        """A text-only unit with a field and a tag is still there on GET."""

        session: _MemorySourceSession = _MemorySourceSession()
        created: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Harbor notes", kind=ContentSourceKind.ALBUM),
            session,
            None,
        )
        unit: UnitReadResponse = create_unit(
            created.id,
            UnitWriteRequest(
                free_text="Fog on the water",
                tags=[" coast ", "coast", ""],
                fields=[{"label": " Place ", "value": " Harbor "}],
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
        self.assertEqual(loaded_unit.free_text, "Fog on the water")
        self.assertEqual(loaded_unit.tags, ["coast"])
        self.assertEqual(loaded_unit.images, [])
        self.assertEqual(len(loaded_unit.fields), 1)
        self.assertEqual(loaded_unit.fields[0].label, "Place")
        self.assertEqual(loaded_unit.fields[0].value, "Harbor")

    def test_second_album_with_the_same_name_gets_a_suffixed_slug(self) -> None:
        """Slug stays unique. Rename does not change it."""

        session: _MemorySourceSession = _MemorySourceSession()
        first: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Harbor", kind=ContentSourceKind.ALBUM),
            session,
            None,
        )
        second: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Harbor", kind=ContentSourceKind.ALBUM),
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

    def test_resource_kind_is_rejected(self) -> None:
        """Phase 2 does not create resources."""

        session: _MemorySourceSession = _MemorySourceSession()

        with self.assertRaises(HTTPException) as raised:
            create_content_source(
                SourceCreateRequest(name="Notes", kind=ContentSourceKind.RESOURCE),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(session.sources, [])
        self.assertEqual(session.commit_count, 0)

    def test_empty_unit_is_rejected_and_not_stored(self) -> None:
        """Tags alone do not count. A half-filled field is also 400."""

        session: _MemorySourceSession = _MemorySourceSession()
        created: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Empty check", kind=ContentSourceKind.ALBUM),
            session,
            None,
        )

        with self.assertRaises(HTTPException) as empty_error:
            create_unit(
                created.id,
                UnitWriteRequest(free_text="  ", tags=["  "], fields=[]),
                session,
                None,
            )

        self.assertEqual(empty_error.exception.status_code, 400)
        self.assertEqual(empty_error.exception.detail, EMPTY_UNIT_DETAIL)
        self.assertEqual(get_content_source(created.id, session).units, [])

        with self.assertRaises(HTTPException) as field_error:
            create_unit(
                created.id,
                UnitWriteRequest(
                    free_text=None,
                    tags=[],
                    fields=[{"label": "Place", "value": "  "}],
                ),
                session,
                None,
            )

        self.assertEqual(field_error.exception.status_code, 400)
        self.assertEqual(get_content_source(created.id, session).units, [])

    def test_patch_that_would_empty_a_text_unit_writes_nothing(self) -> None:
        """The stored text stays when the replacement has no content."""

        session: _MemorySourceSession = _MemorySourceSession()
        created: SourceReadResponse = create_content_source(
            SourceCreateRequest(name="Keep text", kind=ContentSourceKind.ALBUM),
            session,
            None,
        )
        unit: UnitReadResponse = create_unit(
            created.id,
            UnitWriteRequest(free_text="Stay", tags=["keep"], fields=[]),
            session,
            None,
        )

        with self.assertRaises(HTTPException) as raised:
            patch_unit(
                created.id,
                unit.id,
                UnitWriteRequest(free_text="", tags=[], fields=[]),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        stored: Unit | None = session.get(Unit, unit.id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.free_text, "Stay")
        self.assertEqual(list(stored.tags), ["keep"])


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
        self.assertEqual(raised.exception.detail, EMPTY_UNIT_DETAIL)
        self.assertEqual(session.deleted, [])


class UsedPathCollectionTests(unittest.TestCase):
    """Theme backgrounds, image elements, and artifact slides count as use."""

    def test_collect_used_paths_reads_each_store(self) -> None:
        """A path is in use only when one of those stores names it."""

        background_path: str = "theme-defaults/ocean-waves.jpg"
        element_path: str = "theme-defaults/seoul-skyline.jpg"
        slide_path: str = "theme-defaults/utah-dunes.jpg"
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


if __name__ == "__main__":
    unittest.main()
