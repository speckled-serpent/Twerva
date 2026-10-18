"""Image type, size, and thumbnail rules. No slide upload route.

Album upload and URL import use these checks. A slide does not take a
file or a URL of its own.
"""

import io
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

import httpx
from PIL import Image

from app.models.enums import SlideImageMediaType
from app.carousels.image_intake import (
    IMAGE_TOO_LARGE_DETAIL,
    IMAGE_TYPE_DETAIL,
    MAX_IMAGE_BYTES,
    THUMBNAIL_LONGEST_EDGE,
    download_image_once,
    prepare_image_bytes,
)
from app.carousels.image_store import LocalAlbumImageStore


SVG_BYTES: bytes = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="8"></svg>'
)


class ImageInspectionTests(unittest.TestCase):
    """Type, size, and thumbnail rules before any file is written."""

    def test_jpeg_thumbnail_longest_edge_is_480(self) -> None:
        """A wide JPEG keeps its full size on the row and a smaller thumb."""

        jpeg_bytes: bytes = _jpeg_bytes(960, 200)
        prepared = prepare_image_bytes(jpeg_bytes)

        self.assertEqual(prepared.media_type, SlideImageMediaType.JPEG)
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

        self.assertEqual(prepared.media_type, SlideImageMediaType.SVG)
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

    def test_link_local_url_is_refused_without_a_download(self) -> None:
        """Metadata addresses are not fetched."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError(request.url)

        client: httpx.Client = httpx.Client(transport=httpx.MockTransport(handler))

        with self.assertRaises(Exception) as raised:
            download_image_once("http://169.254.169.254/latest/meta-data", client)

        self.assertIn("not allowed", str(raised.exception))

    def test_store_delete_ignores_skeleton_defaults(self) -> None:
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


def _encoded_image(width: int, height: int, image_format: str) -> bytes:
    """Encode a solid image."""

    image: Image.Image = Image.new("RGB", (width, height), (20, 80, 140))
    buffer: io.BytesIO = io.BytesIO()
    image.save(buffer, format=image_format)

    return buffer.getvalue()
