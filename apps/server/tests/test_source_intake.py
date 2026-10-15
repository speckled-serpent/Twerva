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

from app.api.v1.schemas import (
    UnitImageCreateItem,
    UnitImageImportRequest,
    UnitWithImagesCreateRequest,
    UnitWriteRequest,
)
from app.api.v1.source_intake import (
    UnitImageAttachment,
    add_images_from_payloads,
    attachments_for_new_unit,
    create_unit_with_images,
    import_unit_image,
    parse_unit_with_images_json,
)
from app.sources.editing import LICENSE_NOTE_DETAIL, ONE_IMAGE_DETAIL
from app.sources.unit_theme import IMAGE_REQUIRED_DETAIL
from app.api.v1.source_writes import delete_unit_image
from app.models.enums import (
    BackgroundKind,
    UnitImageIntake,
    UnitImageLicense,
    UnitImageMediaType,
)
from app.models.content_source import Unit
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
        """One file records the license and the provenance. A second file is refused."""

        session, source_id, unit_id, store, directory = _text_unit_store()
        jpeg_bytes: bytes = _jpeg_bytes(32, 16)
        png_bytes: bytes = _png_bytes(16, 16)
        created = add_images_from_payloads(
            source_id,
            unit_id,
            [jpeg_bytes],
            UnitImageLicense.OWNED,
            " desk photo ",
            "  ",
            "",
            UnitImageIntake.UPLOAD,
            session,
            store,
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].license, UnitImageLicense.OWNED)
        self.assertEqual(created[0].source, "desk photo")
        self.assertEqual(created[0].intake, UnitImageIntake.UPLOAD)
        self.assertEqual(created[0].media_type, UnitImageMediaType.JPEG)
        self.assertTrue(created[0].relative_path.startswith(f"albums/{source_id}/{unit_id}/"))
        self.assertTrue(created[0].relative_path.endswith(".jpg"))
        self.assertIsNotNone(created[0].thumbnail_path)
        self.assertTrue((directory / created[0].relative_path).is_file())
        self.assertTrue((directory / (created[0].thumbnail_path or "")).is_file())

        with self.assertRaises(HTTPException) as second_image:
            add_images_from_payloads(
                source_id,
                unit_id,
                [png_bytes],
                UnitImageLicense.CC0,
                "https://example.com/photo",
                None,
                "",
                UnitImageIntake.UPLOAD,
                session,
                store,
            )

        self.assertEqual(second_image.exception.status_code, 400)
        self.assertEqual(second_image.exception.detail, ONE_IMAGE_DETAIL)

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
                [oversize],
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
        """Two files in one call are refused and write nothing."""

        session, source_id, unit_id, store, directory = _text_unit_store()
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as raised:
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

        self.assertEqual(raised.exception.detail, ONE_IMAGE_DETAIL)

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
        """A picture theme keeps its last image. A color theme unlinks the upload."""

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
            with self.assertRaises(HTTPException) as raised:
                delete_unit_image(source_id, unit_id, created[0].id, session, None)

            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(raised.exception.detail, IMAGE_REQUIRED_DETAIL)
            self.assertTrue(image_path.exists())
            session.theme.background_kind = BackgroundKind.COLOR
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


class ImageOnlyUnitCreateTests(unittest.TestCase):
    """Add unit can store images in the same step as the unit."""

    def test_image_only_unit_keeps_each_license_on_disk(self) -> None:
        """No free text. One image, its license, and a file under albums/."""

        session, source_id, store, directory = _empty_album_store()
        created = create_unit_with_images(
            source_id,
            UnitWriteRequest(name="Desk"),
            [
                UnitImageAttachment(
                    payload=_jpeg_bytes(24, 12),
                    intake=UnitImageIntake.UPLOAD,
                    image_license=UnitImageLicense.OWNED,
                    source="Desk photo",
                    license_note="",
                    alt_text=None,
                ),
            ],
            session,
            store,
        )

        self.assertEqual(created.name, "Desk")
        self.assertEqual(created.texts, [])
        self.assertEqual(len(created.images), 1)
        self.assertEqual(created.images[0].license, UnitImageLicense.OWNED)
        self.assertEqual(created.images[0].source, "Desk photo")
        self.assertEqual(created.images[0].intake, UnitImageIntake.UPLOAD)
        self.assertTrue((directory / created.images[0].relative_path).is_file())
        self.assertTrue((directory / (created.images[0].thumbnail_path or "")).is_file())
        self.assertTrue(created.images[0].relative_path.startswith("albums/"))

    def test_missing_license_note_and_bad_type_leave_no_unit_or_file(self) -> None:
        """The license gate and the type gate write nothing."""

        session, source_id, store, directory = _empty_album_store()
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as note_error:
            create_unit_with_images(
                source_id,
                UnitWriteRequest(name="Desk"),
                [
                    UnitImageAttachment(
                        payload=_jpeg_bytes(8, 8),
                        intake=UnitImageIntake.UPLOAD,
                        image_license=UnitImageLicense.LICENSED,
                        source="https://example.com/rights",
                        license_note="  ",
                        alt_text=None,
                    ),
                ],
                session,
                store,
            )

        with self.assertRaises(HTTPException) as type_error:
            create_unit_with_images(
                source_id,
                UnitWriteRequest(name="Desk"),
                [
                    UnitImageAttachment(
                        payload=b"GIF89ahello",
                        intake=UnitImageIntake.UPLOAD,
                        image_license=UnitImageLicense.CC0,
                        source="https://example.com/photo",
                        license_note="",
                        alt_text=None,
                    ),
                ],
                session,
                store,
            )

        self.assertEqual(note_error.exception.status_code, 400)
        self.assertEqual(note_error.exception.detail, LICENSE_NOTE_DETAIL)
        self.assertEqual(type_error.exception.status_code, 400)
        self.assertEqual(type_error.exception.detail, IMAGE_TYPE_DETAIL)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(_unit_count(session, source_id), 0)
        self.assertEqual(list(directory.rglob("*")), [])

    def test_text_without_images_still_rejects_an_empty_unit(self) -> None:
        """The multipart path keeps the empty-unit rule."""

        session, source_id, store, directory = _empty_album_store()

        with self.assertRaises(HTTPException) as raised:
            create_unit_with_images(
                source_id,
                UnitWriteRequest(name="Empty"),
                [],
                session,
                store,
            )

        self.assertEqual(raised.exception.detail, IMAGE_REQUIRED_DETAIL)
        self.assertEqual(_unit_count(session, source_id), 0)
        self.assertEqual(list(directory.rglob("*")), [])

    def test_license_failure_does_not_download_the_url(self) -> None:
        """A missing note is rejected before the URL is fetched."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError(request.url)

        client: httpx.Client = httpx.Client(transport=httpx.MockTransport(handler))
        create_request: UnitWithImagesCreateRequest = UnitWithImagesCreateRequest(
            name="Plate",
            images=[
                UnitImageCreateItem(
                    kind="url",
                    url="https://example.com/plate.png",
                    license=UnitImageLicense.LICENSED,
                    source="https://example.com/rights",
                    license_note=" ",
                ),
            ],
        )

        with self.assertRaises(HTTPException) as raised:
            attachments_for_new_unit(create_request, [], client)

        self.assertEqual(raised.exception.detail, LICENSE_NOTE_DETAIL)

    def test_url_item_is_downloaded_once_and_a_bad_license_json_is_400(self) -> None:
        """The form parser rejects an unknown license. A good URL is fetched once."""

        with self.assertRaises(HTTPException) as raised:
            parse_unit_with_images_json(
                '{"name":"Plate","images":[{"kind":"file","license":"copyright","source":"desk"}]}',
            )

        image_url: str = "https://example.com/plate.png"
        png_bytes: bytes = _png_bytes(8, 8)
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))

            return httpx.Response(200, content=png_bytes)

        client: httpx.Client = httpx.Client(transport=httpx.MockTransport(handler))
        create_request: UnitWithImagesCreateRequest = UnitWithImagesCreateRequest(
            name="Plate",
            images=[
                UnitImageCreateItem(
                    kind="url",
                    url=image_url,
                    license=UnitImageLicense.CC0,
                    source=image_url,
                    license_note="",
                ),
            ],
        )
        attachments = attachments_for_new_unit(create_request, [], client)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(calls, [image_url])
        self.assertEqual(attachments[0].payload, png_bytes)
        self.assertEqual(attachments[0].intake, UnitImageIntake.URL)
        self.assertEqual(attachments[0].source, image_url)


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
    from app.api.v1.source_writes import create_content_source
    session: _MemorySourceSession = _MemorySourceSession()
    created = create_content_source(
        SourceCreateRequest(name="Intake", theme_id=session.theme.id),
        session,
        None,
    )
    session.theme.background_kind = BackgroundKind.PICTURE
    unit_id: uuid.UUID = uuid.uuid4()
    text_unit: Unit = Unit(
        id=unit_id,
        source_id=created.id,
        position=0,
        name="Notes",
    )
    text_unit.images = []
    text_unit.element_texts = []
    session.add(text_unit)
    directory: Path = Path(tempfile.mkdtemp(prefix="twerva-albums-"))
    store: LocalAlbumImageStore = LocalAlbumImageStore(directory)

    return session, created.id, unit_id, store, directory


def _empty_album_store() -> tuple[_MemorySourceSession, uuid.UUID, LocalAlbumImageStore, Path]:
    """Create an album with no units and a temp artifact directory."""

    from app.api.v1.schemas import SourceCreateRequest
    from app.api.v1.source_writes import create_content_source
    session: _MemorySourceSession = _MemorySourceSession()
    session.theme.background_kind = BackgroundKind.PICTURE
    created = create_content_source(
        SourceCreateRequest(name="Image only", theme_id=session.theme.id),
        session,
        None,
    )
    directory: Path = Path(tempfile.mkdtemp(prefix="twerva-albums-"))
    store: LocalAlbumImageStore = LocalAlbumImageStore(directory)

    return session, created.id, store, directory


def _unit_count(session: _MemorySourceSession, source_id: uuid.UUID) -> int:
    """Return how many units the memory session has on this album."""

    from app.models.content_source import ContentSource

    found = session.get(ContentSource, source_id)
    assert isinstance(found, ContentSource)

    return len(list(found.units))


