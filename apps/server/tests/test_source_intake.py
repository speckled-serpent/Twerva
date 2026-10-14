"""Upload, URL import, thumbnails, and the license gate. No theme-picker change."""

import io
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

import httpx
from fastapi import HTTPException
from PIL import Image

from app.api.v1.schemas import UnitImageImportRequest, UnitWriteRequest
from app.api.v1.source_intake import add_images_from_payloads, import_unit_image
from app.api.v1.source_writes import delete_unit_image
from app.models.enums import UnitImageIntake, UnitImageLicense, UnitImageMediaType
from app.models.content_source import Unit
from app.sources.editing import LICENSE_NOTE_DETAIL
from app.sources.image_intake import (
    IMAGE_TOO_LARGE_DETAIL,
    IMAGE_TYPE_DETAIL,
    MAX_IMAGE_BYTES,
    THUMBNAIL_LONGEST_EDGE,
    download_image_once,
    prepare_image_bytes,
)
from app.sources.image_store import LocalAlbumImageStore
from app.themes.default_images import list_theme_image_albums, resolve_theme_image_path
from app.sources.default_album import default_unit_seeds
from tests.test_source_writes import _MemorySourceSession


SVG_BYTES: bytes = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="8"></svg>'
)


class ImageInspectionTests(unittest.TestCase):
    """Type, size, and thumbnail rules before any file is written."""

    def test_jpeg_thumbnail_longest_edge_is_480(self) -> None:
        """A wide JPEG keeps its full size on the row and a smaller thumb."""

        jpeg_bytes: bytes = _jpeg_bytes(960, 200)
        prepared = prepare_image_bytes(jpeg_bytes)

        self.assertEqual(prepared.media_type, UnitImageMediaType.JPEG)
        self.assertEqual(prepared.extension, "jpg")
        self.assertEqual(prepared.width, 960)
        self.assertEqual(prepared.height, 200)
        self.assertIsNotNone(prepared.thumbnail_jpeg)

        with Image.open(io.BytesIO(prepared.thumbnail_jpeg or b"")) as thumbnail:
            longest_edge: int = max(thumbnail.size)

        self.assertLessEqual(longest_edge, THUMBNAIL_LONGEST_EDGE)
        self.assertEqual(longest_edge, 480)

    def test_svg_has_no_thumbnail_or_pixel_size(self) -> None:
        """SVG is stored as-is."""

        prepared = prepare_image_bytes(SVG_BYTES)

        self.assertEqual(prepared.media_type, UnitImageMediaType.SVG)
        self.assertIsNone(prepared.thumbnail_jpeg)
        self.assertIsNone(prepared.width)
        self.assertIsNone(prepared.height)

    def test_oversize_and_wrong_type_raise_before_a_write(self) -> None:
        """8 MB and SVG/PNG/JPEG are the limits."""

        oversize: bytes = b"\xff\xd8\xff" + (b"0" * MAX_IMAGE_BYTES)
        gif_bytes: bytes = b"GIF89a" + b"\x00" * 16

        with self.assertRaises(Exception) as oversize_error:
            prepare_image_bytes(oversize)

        with self.assertRaises(Exception) as type_error:
            prepare_image_bytes(gif_bytes)

        self.assertIn(IMAGE_TOO_LARGE_DETAIL, str(oversize_error.exception))
        self.assertIn(IMAGE_TYPE_DETAIL, str(type_error.exception))


class AlbumImageIntakeTests(unittest.TestCase):
    """Rows and files appear together, or not at all."""

    def test_upload_jpeg_and_png_records_license_and_source(self) -> None:
        """Two files in one batch share the license and the provenance."""

        session, source_id, unit_id, store, directory = _text_unit_store()
        jpeg_bytes: bytes = _jpeg_bytes(32, 16)
        png_bytes: bytes = _png_bytes(16, 16)
        created = add_images_from_payloads(
            source_id,
            unit_id,
            [jpeg_bytes, png_bytes],
            UnitImageLicense.OWNED,
            " desk photo ",
            "  ",
            "",
            UnitImageIntake.UPLOAD,
            session,
            store,
        )

        self.assertEqual(len(created), 2)
        self.assertEqual(created[0].license, UnitImageLicense.OWNED)
        self.assertEqual(created[0].source, "desk photo")
        self.assertEqual(created[0].intake, UnitImageIntake.UPLOAD)
        self.assertEqual(created[0].media_type, UnitImageMediaType.JPEG)
        self.assertTrue(created[0].relative_path.startswith(f"albums/{source_id}/{unit_id}/"))
        self.assertTrue(created[0].relative_path.endswith(".jpg"))
        self.assertIsNotNone(created[0].thumbnail_path)
        self.assertEqual(created[1].media_type, UnitImageMediaType.PNG)
        self.assertTrue((directory / created[0].relative_path).is_file())
        self.assertTrue((directory / (created[0].thumbnail_path or "")).is_file())
        self.assertTrue((directory / created[1].relative_path).is_file())

    def test_missing_license_note_and_oversize_leave_no_row_or_file(self) -> None:
        """The license gate and the size gate write nothing."""

        session, source_id, unit_id, store, directory = _text_unit_store()
        commits_before: int = session.commit_count
        jpeg_bytes: bytes = _jpeg_bytes(8, 8)

        with self.assertRaises(HTTPException) as note_error:
            add_images_from_payloads(
                source_id,
                unit_id,
                [jpeg_bytes],
                UnitImageLicense.LICENSED,
                "https://example.com/rights",
                None,
                "  ",
                UnitImageIntake.UPLOAD,
                session,
                store,
            )

        oversize: bytes = b"\xff\xd8\xff" + (b"0" * MAX_IMAGE_BYTES)

        with self.assertRaises(HTTPException) as size_error:
            add_images_from_payloads(
                source_id,
                unit_id,
                [jpeg_bytes, oversize],
                UnitImageLicense.CC0,
                "https://example.com/photo",
                None,
                "",
                UnitImageIntake.UPLOAD,
                session,
                store,
            )

        self.assertEqual(note_error.exception.status_code, 400)
        self.assertEqual(note_error.exception.detail, LICENSE_NOTE_DETAIL)
        self.assertEqual(size_error.exception.status_code, 400)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(list(directory.rglob("*")), [])
        stored_unit: Unit | None = session.get(Unit, unit_id)
        self.assertIsNotNone(stored_unit)
        assert stored_unit is not None
        self.assertEqual(list(stored_unit.images), [])

    def test_second_bad_file_does_not_keep_the_first(self) -> None:
        """One GIF in the batch rejects the JPEG beside it."""

        session, source_id, unit_id, store, directory = _text_unit_store()
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException):
            add_images_from_payloads(
                source_id,
                unit_id,
                [_jpeg_bytes(8, 8), b"GIF89ahello"],
                UnitImageLicense.CC0,
                "https://example.com/photo",
                None,
                "",
                UnitImageIntake.UPLOAD,
                session,
                store,
            )

        self.assertEqual(list(directory.rglob("*")), [])
        self.assertEqual(session.commit_count, commits_before)

    def test_url_import_downloads_once_and_records_the_source_url(self) -> None:
        """intake is url. Provenance is the source field. The GET happens once."""

        session, source_id, unit_id, store, directory = _text_unit_store()
        image_url: str = "https://example.com/plate.png"
        png_bytes: bytes = _png_bytes(16, 16)
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))

            return httpx.Response(200, content=png_bytes)

        download_client: httpx.Client = httpx.Client(
            transport=httpx.MockTransport(handler),
        )

        with patch(
            "app.api.v1.source_intake.configured_album_image_store",
            return_value=store,
        ):
            with patch("app.api.v1.source_intake.httpx.Client", return_value=download_client):
                created = import_unit_image(
                    source_id,
                    unit_id,
                    UnitImageImportRequest(
                        url=image_url,
                        license=UnitImageLicense.CC0,
                        source=image_url,
                        license_note="",
                    ),
                    session,
                    None,
                )

        self.assertEqual(calls, [image_url])
        self.assertEqual(created.intake, UnitImageIntake.URL)
        self.assertEqual(created.license, UnitImageLicense.CC0)
        self.assertEqual(created.source, image_url)
        self.assertEqual(created.media_type, UnitImageMediaType.PNG)
        self.assertTrue((directory / created.relative_path).is_file())
        self.assertTrue((directory / (created.thumbnail_path or "")).is_file())

    def test_link_local_url_is_refused_without_a_download(self) -> None:
        """Metadata addresses are not fetched."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError(request.url)

        client: httpx.Client = httpx.Client(transport=httpx.MockTransport(handler))

        with self.assertRaises(Exception) as raised:
            download_image_once("http://169.254.169.254/latest/meta-data", client)

        self.assertIn("not allowed", str(raised.exception))

    def test_delete_removes_album_files_and_leaves_package_defaults(self) -> None:
        """An uploaded file is unlinked. A theme-defaults path is not."""

        session, source_id, unit_id, store, directory = _text_unit_store()
        created = add_images_from_payloads(
            source_id,
            unit_id,
            [_jpeg_bytes(8, 8)],
            UnitImageLicense.PUBLIC_DOMAIN,
            "https://example.com/scan",
            None,
            "",
            UnitImageIntake.UPLOAD,
            session,
            store,
        )
        image_path: Path = directory / created[0].relative_path
        thumb_path: Path = directory / (created[0].thumbnail_path or "")
        package_path: Path = resolve_theme_image_path(
            default_unit_seeds()[0].relative_path,
            directory,
        )

        with patch(
            "app.sources.image_store.configured_album_image_store",
            return_value=store,
        ):
            delete_unit_image(source_id, unit_id, created[0].id, session, None)

        self.assertFalse(image_path.exists())
        self.assertFalse(thumb_path.exists())
        self.assertTrue(package_path.is_file())
        self.assertEqual(len(list_theme_image_albums()), 1)
        self.assertEqual(list_theme_image_albums()[0].album_id, "default")

    def test_store_delete_ignores_theme_defaults(self) -> None:
        """delete does not remove a file outside albums/."""

        with tempfile.TemporaryDirectory() as storage_directory:
            root: Path = Path(storage_directory)
            kept_path: Path = root / "theme-defaults" / "kept.jpg"
            kept_path.parent.mkdir(parents=True)
            kept_path.write_bytes(b"keep")
            store: LocalAlbumImageStore = LocalAlbumImageStore(root)
            store.delete("theme-defaults/kept.jpg")

            self.assertTrue(kept_path.is_file())


def _jpeg_bytes(width: int, height: int) -> bytes:
    """Return a small RGB JPEG."""

    return _encoded_image(width, height, "JPEG")


def _png_bytes(width: int, height: int) -> bytes:
    """Return a small RGB PNG."""

    return _encoded_image(width, height, "PNG")


def _encoded_image(width: int, height: int, image_format: str) -> bytes:
    """Encode a solid image."""

    image: Image.Image = Image.new("RGB", (width, height), (20, 80, 140))
    buffer: io.BytesIO = io.BytesIO()
    image.save(buffer, format=image_format)

    return buffer.getvalue()


def _text_unit_store() -> tuple[_MemorySourceSession, uuid.UUID, uuid.UUID, LocalAlbumImageStore, Path]:
    """Create an album with a text unit and a temp artifact directory."""

    from app.api.v1.schemas import SourceCreateRequest
    from app.api.v1.source_writes import create_content_source, create_unit
    from app.models.enums import ContentSourceKind

    session: _MemorySourceSession = _MemorySourceSession()
    created = create_content_source(
        SourceCreateRequest(name="Intake", kind=ContentSourceKind.ALBUM),
        session,
        None,
    )
    unit = create_unit(
        created.id,
        UnitWriteRequest(free_text="Notes", tags=[], fields=[]),
        session,
        None,
    )
    directory: Path = Path(tempfile.mkdtemp(prefix="twerva-albums-"))
    store: LocalAlbumImageStore = LocalAlbumImageStore(directory)

    return session, created.id, unit.id, store, directory


