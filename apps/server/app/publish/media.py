"""Resolve slide `asset_ref` files under ARTIFACT_STORAGE_DIR (1.6c-iii)."""

from __future__ import annotations

from pathlib import Path

from app.models import Artifact
from app.publish.errors import PublishMediaMissingError, PublishMediaPathEscapeError
from app.storage.artifacts import ensure_artifact_storage_directory


def resolve_artifact_slide_media_paths(
    artifact: Artifact,
    artifact_storage_directory: Path,
) -> list[Path]:
    """Return existing on-disk files for each slide `asset_ref`, in order.

    Slides without `asset_ref` are skipped. A set `asset_ref` that is
    missing on disk or that escapes the store is an error.

    Args:
        artifact: Row whose `slides` JSON holds relative `asset_ref`s.
        artifact_storage_directory: Configured store root.

    Returns:
        Absolute paths, one per present `asset_ref`, slide order.

    Raises:
        PublishMediaMissingError: File does not exist.
        PublishMediaPathEscapeError: `asset_ref` walked outside the store.
    """

    stored_slides: list[object] | None = artifact.slides

    if stored_slides is None:
        empty_media_paths: list[Path] = []

        return empty_media_paths

    resolved_storage_directory: Path = ensure_artifact_storage_directory(
        artifact_storage_directory,
    )
    resolved_media_paths: list[Path] = []

    for stored_slide in stored_slides:
        asset_reference: str | None = asset_reference_from_stored_slide(stored_slide)

        if asset_reference is None:
            continue

        resolved_media_path: Path = resolve_asset_reference_path(
            asset_reference,
            resolved_storage_directory,
        )

        if not resolved_media_path.is_file():
            raise PublishMediaMissingError(asset_reference, resolved_media_path)

        resolved_media_paths.append(resolved_media_path)

    return resolved_media_paths


def asset_reference_from_stored_slide(stored_slide: object) -> str | None:
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
        PublishMediaPathEscapeError: Resolved path is outside the store.
    """

    candidate_path: Path = (resolved_storage_directory / asset_reference).resolve()

    if not candidate_path.is_relative_to(resolved_storage_directory):
        raise PublishMediaPathEscapeError(asset_reference)

    return candidate_path
