"""Default image catalog, one-time picker, and stored-path rendering."""

import os
import random
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from PIL import Image

from app.api.v1.schemas import ThemeElementCreateRequest, ThemePreviewRequest
from app.api.v1.themes import themes_router
from app.models import BackgroundKind, SourceType
from app.models.enums import ThemeElementBand, ThemeElementContentKind
from app.storage.artifacts import ArtifactAssetPathEscapeError
from app.themes.default_images import (
    DEFAULT_ALBUM_ID,
    DEFAULT_ALBUM_NAME,
    DEFAULT_IMAGE_FILENAMES,
    THEME_DEFAULTS_PREFIX,
    choose_default_image,
    default_image_directory,
    list_theme_image_albums,
    resolve_theme_image_path,
)
from tests.test_theme_preview import (
    _decoded_image,
    _preview,
    _source_item,
    _PreviewMemorySession,
)


class ThemeDefaultImageTests(unittest.TestCase):
    """The Default album stores a concrete path and keeps rendering it."""

    def test_catalog_files_exist_and_are_the_only_album(self) -> None:
        """Default lists each bundled JPEG, and no other album is offered yet."""

        albums = list_theme_image_albums()
        image_directory: Path = default_image_directory()

        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0].album_id, DEFAULT_ALBUM_ID)
        self.assertEqual(albums[0].name, DEFAULT_ALBUM_NAME)
        self.assertEqual(len(albums[0].asset_refs), len(DEFAULT_IMAGE_FILENAMES))

        for filename in DEFAULT_IMAGE_FILENAMES:
            asset_ref: str = f"{THEME_DEFAULTS_PREFIX}{filename}"
            image_path: Path = image_directory / filename

            self.assertIn(asset_ref, albums[0].asset_refs)
            self.assertTrue(image_path.is_file())
            with Image.open(image_path) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (1080, 1920))

    def test_picker_stores_a_catalog_path_and_shuffle_changes_it(self) -> None:
        """One seeded draw stays in the album. Excluding it draws another file."""

        rng: random.Random = random.Random(0)
        first_ref: str = choose_default_image(None, rng)
        albums = list_theme_image_albums()
        shuffled_ref: str = choose_default_image(first_ref, random.Random(0))

        self.assertIn(first_ref, albums[0].asset_refs)
        self.assertTrue(first_ref.startswith(THEME_DEFAULTS_PREFIX))
        self.assertIn(shuffled_ref, albums[0].asset_refs)
        self.assertNotEqual(shuffled_ref, first_ref)
        self.assertEqual(choose_default_image(None, random.Random(0)), first_ref)

    def test_same_stored_path_resolves_to_the_package_file(self) -> None:
        """A stored default path is the bundled file, not the artifact store."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            asset_ref: str = f"{THEME_DEFAULTS_PREFIX}{DEFAULT_IMAGE_FILENAMES[0]}"
            resolved_path: Path = resolve_theme_image_path(asset_ref, storage.resolve())

            self.assertEqual(
                resolved_path,
                default_image_directory() / DEFAULT_IMAGE_FILENAMES[0],
            )
            self.assertTrue(resolved_path.is_file())
            self.assertFalse(resolved_path.is_relative_to(storage.resolve()))

    def test_old_asset_ref_stays_on_the_artifact_store(self) -> None:
        """A legacy path is not rewritten onto the package directory."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory).resolve()
            resolved_path: Path = resolve_theme_image_path("backgrounds/harbor.png", storage)

            self.assertEqual(resolved_path, storage / "backgrounds" / "harbor.png")
            self.assertFalse(resolved_path.is_file())

    def test_theme_defaults_escape_is_rejected(self) -> None:
        """A theme-defaults ref cannot climb out of the package directory."""

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory).resolve()

            with self.assertRaises(ArtifactAssetPathEscapeError):
                resolve_theme_image_path("theme-defaults/../secret.jpg", storage)

    def test_stored_default_path_preview_is_stable(self) -> None:
        """The same stored path renders twice, and a missing old file still blocks."""

        stored_ref: str = choose_default_image(None, random.Random(1))

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            source_item = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            preview_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref=stored_ref,
            )

            first_response = _preview(preview_request, session, storage)
            second_response = _preview(preview_request, session, storage)
            first_image: Image.Image = _decoded_image(first_response)
            missing_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref="backgrounds/missing.png",
            )
            missing_response = _preview(missing_request, session, storage)
            image_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                elements=[
                    ThemeElementCreateRequest(
                        band=ThemeElementBand.MIDDLE,
                        content_kind=ThemeElementContentKind.IMAGE,
                        image_asset_ref=stored_ref,
                    ),
                ],
            )
            image_response = _preview(image_request, session, storage)

            self.assertFalse(first_response.blocked)
            self.assertIsNone(first_response.block_reason)
            self.assertEqual(first_image.size, (1080, 1920))
            self.assertNotEqual(first_image.getpixel((540, 200)), (0xF6, 0xF1, 0xE8, 255))
            self.assertEqual(first_response.image_png_base64, second_response.image_png_base64)
            self.assertTrue(missing_response.blocked)
            self.assertEqual(missing_response.block_reason, "missing_asset")
            self.assertFalse(image_response.blocked)

    def test_uploaded_album_path_preview_stays_on_that_file(self) -> None:
        """An album JPEG in the artifact store paints twice from the stored path."""

        album_path: str = "albums/source/unit/lamp.jpg"
        other_path: str = "albums/source/unit/other.jpg"

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            _write_solid_jpeg(storage / album_path, (220, 20, 20))
            _write_solid_jpeg(storage / other_path, (20, 20, 220))
            source_item = _source_item(SourceType.SPOTMU_INTEREST)
            session: _PreviewMemorySession = _PreviewMemorySession(source_item)
            album_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref=album_path,
            )

            first_response = _preview(album_request, session, storage)
            second_response = _preview(album_request, session, storage)
            first_image: Image.Image = _decoded_image(first_response)
            other_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref=other_path,
            )
            other_response = _preview(other_request, session, storage)
            element_request: ThemePreviewRequest = ThemePreviewRequest(
                source_item_id=source_item.id,
                elements=[
                    ThemeElementCreateRequest(
                        band=ThemeElementBand.MIDDLE,
                        content_kind=ThemeElementContentKind.IMAGE,
                        image_asset_ref=album_path,
                    ),
                ],
            )
            element_response = _preview(element_request, session, storage)
            red_pixel: tuple[int, ...] = first_image.getpixel((540, 960))

            self.assertFalse(first_response.blocked)
            self.assertGreater(red_pixel[0], 180)
            self.assertLess(red_pixel[2], 80)
            self.assertEqual(first_response.image_png_base64, second_response.image_png_base64)
            self.assertNotEqual(first_response.image_png_base64, other_response.image_png_base64)
            self.assertFalse(element_response.blocked)
            self.assertEqual(album_request.background_asset_ref, album_path)

    def test_default_images_route_is_registered_before_theme_id(self) -> None:
        """GET /default-images must not be captured by GET /{theme_id}."""

        get_paths: list[str] = []

        for route in themes_router.routes:
            methods: set[str] = getattr(route, "methods", set()) or set()
            path: str = getattr(route, "path", "")

            if "GET" in methods:
                get_paths.append(path)

        self.assertLess(
            get_paths.index("/themes/default-images"),
            get_paths.index("/themes/{theme_id}"),
        )


def _write_solid_jpeg(image_path: Path, color: tuple[int, int, int]) -> None:
    """Write a small JPEG under the artifact store."""

    image_path.parent.mkdir(parents=True, exist_ok=True)
    image: Image.Image = Image.new("RGB", (64, 64), color)
    image.save(image_path, format="JPEG")


if __name__ == "__main__":
    unittest.main()
