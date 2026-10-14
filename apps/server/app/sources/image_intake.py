"""Turn upload bytes or one URL into an album image. Failures write nothing.

SVG, PNG, and JPEG only. 8 MB. A thumbnail is a JPEG whose longest edge
is 480. SVG is stored as-is and has no thumbnail.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import SplitResult, urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from app.models.enums import UnitImageMediaType


MAX_IMAGE_BYTES: int = 8 * 1024 * 1024
THUMBNAIL_LONGEST_EDGE: int = 480
DOWNLOAD_TIMEOUT_SECONDS: float = 20.0
IMAGE_TOO_LARGE_DETAIL: str = "Image files must be 8 MB or smaller."
IMAGE_TYPE_DETAIL: str = "Image files must be SVG, PNG, or JPEG."
IMAGE_UNREADABLE_DETAIL: str = "Image file could not be read."
IMAGE_URL_DETAIL: str = "The image URL could not be downloaded."
IMAGE_URL_STATUS_DETAIL: str = "The image URL did not return the file."
IMAGE_URL_SCHEME_DETAIL: str = "The image URL must be http or https."
IMAGE_URL_HOST_DETAIL: str = "That image URL is not allowed."

JPEG_MAGIC: bytes = b"\xff\xd8\xff"
PNG_MAGIC: bytes = b"\x89PNG\r\n\x1a\n"
EXTENSION_BY_MEDIA_TYPE: dict[UnitImageMediaType, str] = {
    UnitImageMediaType.JPEG: "jpg",
    UnitImageMediaType.PNG: "png",
    UnitImageMediaType.SVG: "svg",
}


class ImageIntakeError(ValueError):
    """The bytes or URL cannot be stored. Nothing was written."""

    def __init__(self, detail: str) -> None:

        super().__init__(detail)
        self.detail: str = detail


@dataclass(frozen=True)
class PreparedUnitImage:
    """Bytes that passed the type, size, and thumbnail checks."""

    media_type: UnitImageMediaType
    payload: bytes
    thumbnail_jpeg: bytes | None
    width: int | None
    height: int | None
    extension: str


def prepare_image_bytes(payload: bytes) -> PreparedUnitImage:
    """Sniff type, enforce 8 MB, and build a thumbnail for raster images.

    Args:
        payload: Uploaded or downloaded bytes.

    Returns:
        A prepared image. SVG has no thumbnail and no pixel size.

    Raises:
        ImageIntakeError: The payload is empty, too large, the wrong
            type, or not readable. No file is written here.
    """

    if len(payload) == 0:
        raise ImageIntakeError(IMAGE_TYPE_DETAIL)

    if len(payload) > MAX_IMAGE_BYTES:
        raise ImageIntakeError(IMAGE_TOO_LARGE_DETAIL)

    media_type: UnitImageMediaType = _sniff_media_type(payload)

    if media_type == UnitImageMediaType.SVG:
        prepared_svg: PreparedUnitImage = PreparedUnitImage(
            media_type=media_type,
            payload=payload,
            thumbnail_jpeg=None,
            width=None,
            height=None,
            extension=EXTENSION_BY_MEDIA_TYPE[media_type],
        )

        return prepared_svg

    width, height, thumbnail_jpeg = _raster_size_and_thumbnail(payload)
    prepared_raster: PreparedUnitImage = PreparedUnitImage(
        media_type=media_type,
        payload=payload,
        thumbnail_jpeg=thumbnail_jpeg,
        width=width,
        height=height,
        extension=EXTENSION_BY_MEDIA_TYPE[media_type],
    )

    return prepared_raster


def download_image_once(image_url: str, http_client: httpx.Client) -> bytes:
    """GET the URL once and return the body. Redirects are not followed.

    Args:
        image_url: http or https URL.
        http_client: Client to use. Tests pass a mock transport.

    Returns:
        Response bytes, at most 8 MB.

    Raises:
        ImageIntakeError: The URL is not allowed, the download failed,
            or the body is over the size limit.
    """

    _reject_disallowed_url(image_url)

    try:
        response: httpx.Response = http_client.get(
            image_url,
            follow_redirects=False,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as timeout_error:
        raise ImageIntakeError(IMAGE_URL_DETAIL) from timeout_error
    except httpx.HTTPError as http_error:
        raise ImageIntakeError(IMAGE_URL_DETAIL) from http_error

    if response.status_code != 200:
        raise ImageIntakeError(IMAGE_URL_STATUS_DETAIL)

    payload: bytes = response.content

    if len(payload) > MAX_IMAGE_BYTES:
        raise ImageIntakeError(IMAGE_TOO_LARGE_DETAIL)

    return payload


def _sniff_media_type(payload: bytes) -> UnitImageMediaType:
    """Return the media type from the bytes, not the filename."""

    if payload.startswith(PNG_MAGIC):

        return UnitImageMediaType.PNG

    if payload.startswith(JPEG_MAGIC):

        return UnitImageMediaType.JPEG

    if _looks_like_svg(payload):

        return UnitImageMediaType.SVG

    raise ImageIntakeError(IMAGE_TYPE_DETAIL)


def _looks_like_svg(payload: bytes) -> bool:
    """True when the payload is XML whose root is an svg element."""

    try:
        decoded_text: str = payload.decode("utf-8")
    except UnicodeDecodeError:

        return False

    stripped_text: str = decoded_text.lstrip("\ufeff \t\r\n")
    lowered_start: str = stripped_text[:200].lower()

    if not (lowered_start.startswith("<svg") or lowered_start.startswith("<?xml")):

        return False

    return "<svg" in lowered_start or "<svg" in stripped_text[:2000].lower()


def _raster_size_and_thumbnail(payload: bytes) -> tuple[int, int, bytes]:
    """Read pixel size and encode a JPEG thumbnail."""

    try:
        with Image.open(io.BytesIO(payload)) as opened_image:
            opened_image.load()
            width: int = opened_image.width
            height: int = opened_image.height
            thumbnail_source: Image.Image = opened_image.convert("RGB")
    except (UnidentifiedImageError, OSError) as image_error:
        raise ImageIntakeError(IMAGE_UNREADABLE_DETAIL) from image_error

    if width <= 0 or height <= 0:
        raise ImageIntakeError(IMAGE_UNREADABLE_DETAIL)

    thumbnail_source.thumbnail(
        (THUMBNAIL_LONGEST_EDGE, THUMBNAIL_LONGEST_EDGE),
        Image.Resampling.LANCZOS,
    )
    thumbnail_buffer: io.BytesIO = io.BytesIO()
    thumbnail_source.save(thumbnail_buffer, format="JPEG", quality=85)
    thumbnail_jpeg: bytes = thumbnail_buffer.getvalue()

    return width, height, thumbnail_jpeg


def _reject_disallowed_url(image_url: str) -> None:
    """Allow public http(s). Refuse other schemes and link-local hosts."""

    stripped_url: str = image_url.strip()
    parts: SplitResult = urlsplit(stripped_url)

    if parts.scheme not in {"http", "https"} or parts.hostname is None:
        raise ImageIntakeError(IMAGE_URL_SCHEME_DETAIL)

    hostname: str = parts.hostname.rstrip(".").lower()

    if hostname == "" or hostname in {"localhost", "localhost.localdomain"}:
        raise ImageIntakeError(IMAGE_URL_HOST_DETAIL)

    try:
        parsed_address: IPv4Address | IPv6Address = ip_address(hostname)
    except ValueError:

        return

    if (
        parsed_address.is_link_local
        or parsed_address.is_unspecified
        or parsed_address.is_multicast
    ):
        raise ImageIntakeError(IMAGE_URL_HOST_DETAIL)
