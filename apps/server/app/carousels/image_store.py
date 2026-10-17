"""Local disk for album images. Callers use save, open, and delete.

Files live under ``ARTIFACT_STORAGE_DIR`` at
``albums/<carousel_id>/<slide_id>/<image_id>.<ext>``. Thumbnails use the
same folder and a ``-thumb.jpg`` name. ``theme-defaults/`` stays in the
package; delete refuses to touch it. S3 is a later implementation.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.storage.artifacts import (
    ArtifactAssetPathEscapeError,
    ensure_artifact_storage_directory,
    resolve_asset_reference_path,
)
from app.skeletons.default_images import resolve_skeleton_image_path


ALBUM_IMAGE_PREFIX: str = "albums/"


class LocalAlbumImageStore:
    """save, open, and delete for album image bytes on the local disk."""

    def __init__(self, storage_directory: Path) -> None:
        self._storage_directory: Path = storage_directory

    def save(self, relative_path: str, payload: bytes) -> None:
        """Write bytes at an ``albums/`` path. Parents are created.

        Args:
            relative_path: Path relative to the artifact store.
            payload: File bytes.

        Raises:
            ArtifactAssetPathEscapeError: The path leaves the store or
                is not under ``albums/``.
        """

        destination_path: Path = self._album_path(relative_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(payload)

    def open(self, relative_path: str) -> Path:
        """Return the file path. ``theme-defaults/`` is the package file.

        Args:
            relative_path: Stored image or thumbnail path.

        Returns:
            Absolute path. It may not exist.

        Raises:
            ArtifactAssetPathEscapeError: The path leaves its root.
        """

        storage_root: Path = self._root()
        opened_path: Path = resolve_skeleton_image_path(relative_path, storage_root)

        return opened_path

    def delete(self, relative_path: str) -> None:
        """Remove an ``albums/`` file. Other prefixes are left in place.

        Args:
            relative_path: Stored path. Package defaults are ignored.
        """

        if not relative_path.startswith(ALBUM_IMAGE_PREFIX):

            return

        try:
            candidate_path: Path = self._album_path(relative_path)
        except ArtifactAssetPathEscapeError:

            return

        if candidate_path.is_file():
            candidate_path.unlink()

    def _album_path(self, relative_path: str) -> Path:
        """Resolve an albums path and reject escape."""

        if not relative_path.startswith(ALBUM_IMAGE_PREFIX):
            raise ArtifactAssetPathEscapeError(relative_path)

        storage_root: Path = self._root()
        candidate_path: Path = resolve_asset_reference_path(relative_path, storage_root)

        return candidate_path

    def _root(self) -> Path:
        """Create the artifact root if needed and return it."""

        root_path: Path = ensure_artifact_storage_directory(self._storage_directory)

        return root_path


def configured_album_image_store() -> LocalAlbumImageStore:
    """Return a store rooted at the process ``ARTIFACT_STORAGE_DIR``."""

    from app.settings import get_settings

    storage_directory: Path = Path(get_settings().artifact_storage_dir)
    image_store: LocalAlbumImageStore = LocalAlbumImageStore(storage_directory)

    return image_store


def album_image_relative_path(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_id: uuid.UUID,
    extension: str,
) -> str:
    """Return ``albums/<carousel>/<slide>/<image>.<ext>``."""

    relative_path: str = f"{ALBUM_IMAGE_PREFIX}{carousel_id}/{slide_id}/{image_id}.{extension}"

    return relative_path


def album_thumbnail_relative_path(
    carousel_id: uuid.UUID,
    slide_id: uuid.UUID,
    image_id: uuid.UUID,
) -> str:
    """Return the JPEG thumbnail path beside the original."""

    thumbnail_path: str = (
        f"{ALBUM_IMAGE_PREFIX}{carousel_id}/{slide_id}/{image_id}-thumb.jpg"
    )

    return thumbnail_path
