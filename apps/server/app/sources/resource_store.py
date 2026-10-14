"""Local disk for a resource file. Callers use save, open, and delete.

The file lives under ``ARTIFACT_STORAGE_DIR`` at
``resources/<source_id>/body.md`` or ``body.txt``. The bytes are the
upload, unchanged. S3 is a later implementation.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.storage.artifacts import (
    ArtifactAssetPathEscapeError,
    ensure_artifact_storage_directory,
    resolve_asset_reference_path,
)


RESOURCE_FILE_PREFIX: str = "resources/"


class LocalResourceFileStore:
    """save, open, and delete for one resource file on the local disk."""

    def __init__(self, storage_directory: Path) -> None:
        self._storage_directory: Path = storage_directory

    def save(self, relative_path: str, payload: bytes) -> None:
        """Write bytes at a ``resources/`` path. Parents are created.

        Args:
            relative_path: Path relative to the artifact store.
            payload: File bytes, unchanged.

        Raises:
            ArtifactAssetPathEscapeError: The path leaves the store or
                is not under ``resources/``.
        """

        destination_path: Path = self._resource_path(relative_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(payload)

    def open(self, relative_path: str) -> Path:
        """Return the file path. It may not exist yet.

        Args:
            relative_path: Stored resource path.

        Returns:
            Absolute path under the artifact store.

        Raises:
            ArtifactAssetPathEscapeError: The path leaves the store.
        """

        opened_path: Path = self._resource_path(relative_path)

        return opened_path

    def delete(self, relative_path: str) -> None:
        """Remove a ``resources/`` file. Other prefixes are left in place.

        Args:
            relative_path: Stored path.
        """

        if not relative_path.startswith(RESOURCE_FILE_PREFIX):

            return

        try:
            candidate_path: Path = self._resource_path(relative_path)
        except ArtifactAssetPathEscapeError:

            return

        if candidate_path.is_file():
            candidate_path.unlink()

    def _resource_path(self, relative_path: str) -> Path:
        """Resolve a resources path and reject escape."""

        if not relative_path.startswith(RESOURCE_FILE_PREFIX):
            raise ArtifactAssetPathEscapeError(relative_path)

        storage_root: Path = ensure_artifact_storage_directory(self._storage_directory)
        candidate_path: Path = resolve_asset_reference_path(relative_path, storage_root)

        return candidate_path


def configured_resource_file_store() -> LocalResourceFileStore:
    """Return a store rooted at the process ``ARTIFACT_STORAGE_DIR``."""

    from app.settings import get_settings

    storage_directory: Path = Path(get_settings().artifact_storage_dir)
    file_store: LocalResourceFileStore = LocalResourceFileStore(storage_directory)

    return file_store


def resource_body_relative_path(source_id: uuid.UUID, extension: str) -> str:
    """Return ``resources/<source_id>/body.<ext>``."""

    relative_path: str = f"{RESOURCE_FILE_PREFIX}{source_id}/body.{extension}"

    return relative_path
