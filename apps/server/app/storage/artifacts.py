"""Write carousel slide bytes under the local artifact store.

On-disk layout (1.4b-ii):

    {ARTIFACT_STORAGE_DIR}/{artifact_id}/{slide_index}_{role}.png

`asset_ref` is that path relative to `ARTIFACT_STORAGE_DIR`. S3 is not
used (1.4b-iii).
"""

from __future__ import annotations

import uuid
from pathlib import Path


def ensure_artifact_storage_directory(artifact_storage_directory: Path) -> Path:
    """Create the artifact root if needed and return its resolved path.

    Args:
        artifact_storage_directory: Configured store (may be relative).

    Returns:
        Absolute directory path that now exists.
    """

    expanded_directory: Path = artifact_storage_directory.expanduser()
    expanded_directory.mkdir(parents=True, exist_ok=True)
    resolved_directory: Path = expanded_directory.resolve()

    return resolved_directory


def resolve_configured_artifact_storage_directory() -> Path:
    """Create and return the process `ARTIFACT_STORAGE_DIR`.

    Returns:
        Resolved local store path from settings.
    """

    from app.settings import get_settings

    configured_directory: str = get_settings().artifact_storage_dir
    configured_path: Path = Path(configured_directory)
    resolved_directory: Path = ensure_artifact_storage_directory(configured_path)

    return resolved_directory


def write_artifact_slide_png_bytes(
    artifact_identifier: uuid.UUID,
    slide_index: int,
    role: str,
    png_bytes: bytes,
    artifact_storage_directory: Path,
) -> str:
    """Write one PNG and return the relative `asset_ref`.

    Args:
        artifact_identifier: Artifact UUID (directory name).
        slide_index: 0-based order in `slides`.
        role: Slide role (`cover`, `heading`, `bullet`, `cta`).
        png_bytes: Encoded PNG payload.
        artifact_storage_directory: Store root (created if missing).

    Returns:
        Relative path `{artifact_id}/{slide_index}_{role}.png`.
    """

    resolved_storage_directory: Path = ensure_artifact_storage_directory(
        artifact_storage_directory,
    )
    sanitized_role: str = sanitize_slide_role(role)
    relative_asset_reference: str = (
        f"{artifact_identifier}/{slide_index}_{sanitized_role}.png"
    )
    destination_path: Path = resolved_storage_directory / relative_asset_reference
    destination_parent: Path = destination_path.parent
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(png_bytes)

    return relative_asset_reference


def resolve_slide_png_path_for_index(
    artifact_slides: list[object] | None,
    slide_index: int,
    artifact_storage_directory: Path,
) -> Path | None:
    """Return the on-disk PNG for `slides[index]`, or None when missing.

    Rejects path escape. A present `asset_ref` that is not a file is
    treated as missing (caller should 404).

    Args:
        artifact_slides: Ordered `artifacts.slides` JSON list.
        slide_index: 0-based index from the image route.
        artifact_storage_directory: Store root.

    Returns:
        Absolute existing PNG path, or None.
    """

    if artifact_slides is None:

        return None

    if slide_index < 0 or slide_index >= len(artifact_slides):

        return None

    stored_slide: object = artifact_slides[slide_index]
    asset_reference: str | None = _asset_reference_from_stored_slide(stored_slide)

    if asset_reference is None:

        return None

    resolved_storage_directory: Path = ensure_artifact_storage_directory(
        artifact_storage_directory,
    )

    try:
        candidate_path: Path = resolve_asset_reference_path(
            asset_reference,
            resolved_storage_directory,
        )
    except ArtifactAssetPathEscapeError:

        return None

    if not candidate_path.is_file():

        return None

    return candidate_path


def resolve_asset_reference_path(
    asset_reference: str,
    resolved_storage_directory: Path,
) -> Path:
    """Join `asset_ref` onto the store and reject path escape.

    Args:
        asset_reference: Relative path stored on the slide.
        resolved_storage_directory: Absolute artifact store root.

    Returns:
        Absolute candidate path (may not exist yet).

    Raises:
        ArtifactAssetPathEscapeError: Resolved path is outside the store.
    """

    candidate_path: Path = (resolved_storage_directory / asset_reference).resolve()

    if not candidate_path.is_relative_to(resolved_storage_directory):
        raise ArtifactAssetPathEscapeError(asset_reference)

    return candidate_path


def _asset_reference_from_stored_slide(stored_slide: object) -> str | None:
    """Read a non-empty `asset_ref` string from a slides JSON object."""

    if not isinstance(stored_slide, dict):

        return None

    raw_asset_reference: object = stored_slide.get("asset_ref")

    if not isinstance(raw_asset_reference, str):

        return None

    stripped_asset_reference: str = raw_asset_reference.strip()

    if stripped_asset_reference == "":

        return None

    return stripped_asset_reference


class ArtifactAssetPathEscapeError(ValueError):
    """`asset_ref` resolved outside `ARTIFACT_STORAGE_DIR`."""

    def __init__(self, asset_reference: str) -> None:

        super().__init__(f"asset_ref escapes artifact store: {asset_reference}")
        self.asset_reference: str = asset_reference


def sanitize_slide_role(role: str) -> str:
    """Keep filename-safe role tokens (lowercase letters, digits, underscore).

    Args:
        role: Raw role string from the template.

    Returns:
        Sanitized role, or `slide` when nothing usable remains.
    """

    lowered_role: str = role.strip().lower()
    sanitized_characters: list[str] = []

    for character in lowered_role:

        if character.isalnum() or character == "_":
            sanitized_characters.append(character)

    sanitized_role: str = "".join(sanitized_characters)

    if sanitized_role == "":

        return "slide"

    return sanitized_role
