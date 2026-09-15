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
