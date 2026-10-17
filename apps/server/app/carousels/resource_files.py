"""Validate a resource upload before anything is written.

Markdown or TXT, UTF-8, 2 MB. A PDF, a binary file, or an empty file
is rejected. The stored bytes are the upload.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.carousel import RESOURCE_FILE_MAX_BYTES
from app.models.enums import ResourceFileMediaType


RESOURCE_TYPE_DETAIL: str = "Resource files must be Markdown (.md) or plain text (.txt)."
RESOURCE_TOO_LARGE_DETAIL: str = "Resource files must be 2 MB or smaller."
RESOURCE_EMPTY_DETAIL: str = "Resource file is empty."
RESOURCE_ENCODING_DETAIL: str = "Resource files must be UTF-8 text."
BLANK_PROVENANCE_DETAIL: str = "A resource needs a provenance note."
PDF_MAGIC: bytes = b"%PDF"


class ResourceFileError(ValueError):
    """The upload cannot be stored. Nothing was written."""

    def __init__(self, detail: str) -> None:

        super().__init__(detail)
        self.detail: str = detail


@dataclass(frozen=True)
class PreparedResourceFile:
    """Bytes that passed the type and size checks."""

    media_type: ResourceFileMediaType
    extension: str
    payload: bytes
    original_filename: str


def prepare_resource_upload(filename: str, payload: bytes) -> PreparedResourceFile:
    """Check the name, type, encoding, and size. Does not write.

    Args:
        filename: The name the operator uploaded.
        payload: File bytes.

    Returns:
        The media type and the original filename.

    Raises:
        ResourceFileError: The file is empty, too large, not UTF-8, or
            not Markdown or TXT.
    """

    original_filename: str = _basename(filename)
    media_type, extension = _media_type_for_filename(original_filename)

    if len(payload) == 0:
        raise ResourceFileError(RESOURCE_EMPTY_DETAIL)

    if len(payload) > RESOURCE_FILE_MAX_BYTES:
        raise ResourceFileError(RESOURCE_TOO_LARGE_DETAIL)

    if payload.startswith(PDF_MAGIC) or b"\x00" in payload:
        raise ResourceFileError(RESOURCE_TYPE_DETAIL)

    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as encoding_error:
        raise ResourceFileError(RESOURCE_ENCODING_DETAIL) from encoding_error

    prepared_file: PreparedResourceFile = PreparedResourceFile(
        media_type=media_type,
        extension=extension,
        payload=payload,
        original_filename=original_filename,
    )

    return prepared_file


def require_provenance(provenance: str) -> str:
    """Return a stripped note. Blank is rejected.

    Args:
        provenance: Where the synthesis came from.

    Returns:
        The stripped note.

    Raises:
        ResourceFileError: The note is blank.
    """

    cleaned_provenance: str = provenance.strip()

    if cleaned_provenance == "":
        raise ResourceFileError(BLANK_PROVENANCE_DETAIL)

    return cleaned_provenance


def _basename(filename: str) -> str:
    """Return the file name without a directory. Empty is rejected."""

    stripped_name: str = filename.strip().replace("\\", "/").rsplit("/", maxsplit=1)[-1]

    if stripped_name == "" or stripped_name in {".", ".."}:
        raise ResourceFileError(RESOURCE_TYPE_DETAIL)

    return stripped_name


def _media_type_for_filename(filename: str) -> tuple[ResourceFileMediaType, str]:
    """Map a suffix to markdown or plain text."""

    lowered_name: str = filename.lower()

    if lowered_name.endswith(".md"):

        return ResourceFileMediaType.MARKDOWN, "md"

    if lowered_name.endswith(".txt"):

        return ResourceFileMediaType.PLAIN, "txt"

    raise ResourceFileError(RESOURCE_TYPE_DETAIL)
