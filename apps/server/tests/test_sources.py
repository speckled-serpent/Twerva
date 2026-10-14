"""Default album seed, read API, and unchanged theme-defaults rendering."""

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from PIL import Image

from app.api.v1.schemas import SourceReadResponse, ThemePreviewRequest
from app.api.v1.sources import (
    content_sources_list_statement,
    get_content_source,
    list_content_sources,
    sources_router,
)
from app.models.content_source import ContentSource, Unit, UnitImage
from app.models.enums import (
    ContentSourceKind,
    UnitImageIntake,
    UnitImageLicense,
    UnitImageMediaType,
)
from app.sources.default_album import (
    DEFAULT_ALBUM_SLUG,
    default_album_source_id,
    default_unit_seeds,
)
from app.themes.default_images import (
    DEFAULT_ALBUM_NAME,
    DEFAULT_IMAGE_FILENAMES,
    THEME_DEFAULTS_PREFIX,
    default_image_directory,
)
from app.models import BackgroundKind, SourceType
from tests.test_theme_preview import _decoded_image, _preview, _source_item


LICENSES_PATH: Path = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "themes"
    / "default_images"
    / "LICENSES.md"
)


class DefaultAlbumSeedTests(unittest.TestCase):
    """The six packaged photos become image-only units with CC0 or PD."""

    def test_seed_matches_licenses_and_packaged_files(self) -> None:
        """Each unit keeps theme-defaults/ and the license file's source URL."""

        seeds = default_unit_seeds()
        seeds_by_filename = {seed.filename: seed for seed in seeds}
        licenses_text: str = LICENSES_PATH.read_text(encoding="utf-8")
        sections: list[str] = licenses_text.split("\n## ")

        self.assertEqual(len(seeds), len(DEFAULT_IMAGE_FILENAMES))
        self.assertEqual(
            [seed.filename for seed in seeds],
            list(DEFAULT_IMAGE_FILENAMES),
        )

        for section in sections[1:]:
            filename: str = section.split("\n", 1)[0].strip()
            source_line: str = next(
                line for line in section.splitlines() if line.startswith("- Source: ")
            )
            source_url: str = source_line.removeprefix("- Source: ").strip()
            seed = seeds_by_filename[filename]
            image_path: Path = default_image_directory() / filename

            self.assertEqual(seed.source_url, source_url)
            self.assertEqual(seed.relative_path, f"{THEME_DEFAULTS_PREFIX}{filename}")
            self.assertEqual(seed.byte_size, image_path.stat().st_size)
            self.assertEqual(seed.width, 1080)
            self.assertEqual(seed.height, 1920)
            self.assertIn(
                seed.image_license,
                {UnitImageLicense.CC0, UnitImageLicense.PUBLIC_DOMAIN},
            )

            if "License: CC0" in section:
                self.assertEqual(seed.image_license, UnitImageLicense.CC0)
            else:
                self.assertIn("License: Public domain", section)
                self.assertEqual(seed.image_license, UnitImageLicense.PUBLIC_DOMAIN)

    def test_seed_ids_are_stable(self) -> None:
        """Re-reading the catalog does not mint new ids."""

        first_source_id: uuid.UUID = default_album_source_id()
        second_source_id: uuid.UUID = default_album_source_id()
        first_seeds = default_unit_seeds()
        second_seeds = default_unit_seeds()

        self.assertEqual(first_source_id, second_source_id)
        self.assertEqual(
            [seed.unit_id for seed in first_seeds],
            [seed.unit_id for seed in second_seeds],
        )
        self.assertEqual(len({seed.unit_id for seed in first_seeds}), 6)
        self.assertEqual(len({seed.image_id for seed in first_seeds}), 6)


class ContentSourceReadApiTests(unittest.TestCase):
    """GET list and GET one source. No write routes."""

    def test_get_default_returns_six_licensed_image_only_units(self) -> None:
        """Detail includes each path, license, and empty text, fields, and tags."""

        source: ContentSource = _default_source_from_catalog()
        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = source

        response: SourceReadResponse = get_content_source(source.id, fake_session)
        licenses: set[UnitImageLicense] = set()

        self.assertEqual(response.slug, DEFAULT_ALBUM_SLUG)
        self.assertEqual(response.name, DEFAULT_ALBUM_NAME)
        self.assertEqual(response.kind, ContentSourceKind.ALBUM)
        self.assertEqual(len(response.units), 6)

        for unit, filename in zip(response.units, DEFAULT_IMAGE_FILENAMES, strict=True):
            self.assertIsNone(unit.free_text)
            self.assertEqual(unit.tags, [])
            self.assertEqual(unit.fields, [])
            self.assertEqual(len(unit.images), 1)
            image = unit.images[0]
            licenses.add(image.license)

            self.assertEqual(image.relative_path, f"{THEME_DEFAULTS_PREFIX}{filename}")
            self.assertEqual(image.media_type, UnitImageMediaType.JPEG)
            self.assertEqual(image.intake, UnitImageIntake.UPLOAD)
            self.assertEqual(image.license_note, "")
            self.assertTrue(image.source.startswith("https://commons.wikimedia.org/"))
            self.assertIsNone(image.thumbnail_path)

        self.assertEqual(
            licenses,
            {UnitImageLicense.CC0, UnitImageLicense.PUBLIC_DOMAIN},
        )

    def test_list_kind_album_returns_the_default_count(self) -> None:
        """The album filter query is used, and the list item counts units."""

        source: ContentSource = _default_source_from_catalog()
        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = [source]

        list_items = list_content_sources(ContentSourceKind.ALBUM, fake_session)
        statement = fake_session.scalars.call_args.args[0]
        where_sql: str = str(statement.whereclause)

        self.assertEqual(len(list_items), 1)
        self.assertEqual(list_items[0].slug, DEFAULT_ALBUM_SLUG)
        self.assertEqual(list_items[0].unit_count, 6)
        self.assertIn("kind", where_sql)
        self.assertIsNone(content_sources_list_statement(None).whereclause)

    def test_missing_source_is_not_found(self) -> None:
        """An unknown id is HTTP 404 and does not write."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            get_content_source(missing_id, fake_session)

        self.assertEqual(raised_http.exception.status_code, 404)
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()

    def test_sources_routes_are_get_only(self) -> None:
        """Phase 1 does not register create, update, or delete."""

        methods_by_path: dict[str, set[str]] = {}

        for route in sources_router.routes:
            path: str = getattr(route, "path", "")
            methods: set[str] = set(getattr(route, "methods", set()) or set())
            methods_by_path[path] = methods

        self.assertEqual(methods_by_path["/sources"], {"GET"})
        self.assertEqual(methods_by_path["/sources/{source_id}"], {"GET"})


class ThemeDefaultsRenderingUnchangedTests(unittest.TestCase):
    """A stored theme-defaults path still renders. The request path stays put."""

    def test_catalog_path_still_renders_and_is_not_rewritten(self) -> None:
        """Preview uses the seeded path and leaves that path on the request."""

        stored_ref: str = default_unit_seeds()[0].relative_path

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item = _source_item(SourceType.SPOTMU_INTEREST)
            from tests.test_theme_preview import _PreviewMemorySession

            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref=stored_ref,
            )

            response = _preview(preview_request, session, storage)
            rendered: Image.Image = _decoded_image(response)

            self.assertEqual(preview_request.background_asset_ref, stored_ref)
            self.assertFalse(response.blocked)
            self.assertEqual(rendered.size, (1080, 1920))


def _default_source_from_catalog() -> ContentSource:
    """Build the seeded album in memory, the way a migrated row would look."""

    now: datetime = datetime.now(timezone.utc)
    source: ContentSource = ContentSource(
        id=default_album_source_id(),
        kind=ContentSourceKind.ALBUM,
        name=DEFAULT_ALBUM_NAME,
        slug=DEFAULT_ALBUM_SLUG,
        created_at=now,
        updated_at=now,
    )
    units: list[Unit] = []

    for seed in default_unit_seeds():
        unit: Unit = Unit(
            id=seed.unit_id,
            source_id=source.id,
            position=seed.position,
            free_text=None,
            tags=[],
            created_at=now,
            updated_at=now,
        )
        image: UnitImage = UnitImage(
            id=seed.image_id,
            unit_id=unit.id,
            position=0,
            relative_path=seed.relative_path,
            media_type=UnitImageMediaType.JPEG,
            byte_size=seed.byte_size,
            width=seed.width,
            height=seed.height,
            alt_text=None,
            license=seed.image_license,
            source=seed.source_url,
            license_note="",
            intake=UnitImageIntake.UPLOAD,
            thumbnail_path=None,
            created_at=now,
            updated_at=now,
        )
        unit.images = [image]
        unit.fields = []
        units.append(unit)

    source.units = units

    return source


if __name__ == "__main__":
    unittest.main()
