"""Bundled default photos for picture backgrounds and image elements.

Files live in ``default_images/`` next to this module and are package
data, so an installed server can read them without seeding
``ARTIFACT_STORAGE_DIR``. A chosen photo is stored as a concrete
``theme-defaults/<filename>`` path. Other asset refs still resolve
under the artifact store.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from app.storage.artifacts import (
    ArtifactAssetPathEscapeError,
    resolve_asset_reference_path,
)


THEME_DEFAULTS_PREFIX: str = "theme-defaults/"
DEFAULT_ALBUM_ID: str = "default"
DEFAULT_ALBUM_NAME: str = "Default"
DEFAULT_IMAGE_FILENAMES: tuple[str, ...] = (
    "hong-kong-skyline.jpg",
    "joshua-tree-desert.jpg",
    "ocean-waves.jpg",
    "santa-cruz-pacific.jpg",
    "seoul-skyline.jpg",
    "utah-dunes.jpg",
)


@dataclass(frozen=True)
class ThemeImageAlbum:
    """One named set of concrete asset refs. More albums can be added later."""

    album_id: str
    name: str
    asset_refs: tuple[str, ...]


def default_image_directory() -> Path:
    """Return the package directory that holds the bundled JPEGs."""

    image_directory: Path = Path(__file__).resolve().parent / "default_images"

    return image_directory


def list_theme_image_albums() -> tuple[ThemeImageAlbum, ...]:
    """Return the albums an operator can pick. Only Default exists today."""

    present_refs: list[str] = []
    image_directory: Path = default_image_directory()

    for filename in DEFAULT_IMAGE_FILENAMES:
        image_path: Path = image_directory / filename

        if image_path.is_file():
            present_refs.append(f"{THEME_DEFAULTS_PREFIX}{filename}")

    default_album: ThemeImageAlbum = ThemeImageAlbum(
        album_id=DEFAULT_ALBUM_ID,
        name=DEFAULT_ALBUM_NAME,
        asset_refs=tuple(present_refs),
    )

    return (default_album,)


def choose_default_image(
    exclude: str | None,
    rng: random.Random,
    album_id: str = DEFAULT_ALBUM_ID,
) -> str:
    """Pick one concrete path from an album.

    When ``exclude`` is another file in the album, the result is a
    different path. A one-file album returns that only path.

    Args:
        exclude: Stored path to avoid, or null.
        rng: Caller-owned generator so a test can fix the choice.
        album_id: Album to draw from.

    Returns:
        A ``theme-defaults/`` path that is in the album.

    Raises:
        KeyError: ``album_id`` is not in the catalog.
        ValueError: The album has no files on disk.
    """

    albums_by_id: dict[str, ThemeImageAlbum] = {
        album.album_id: album for album in list_theme_image_albums()
    }
    album: ThemeImageAlbum | None = albums_by_id.get(album_id)

    if album is None:
        raise KeyError(album_id)

    asset_refs: tuple[str, ...] = album.asset_refs

    if len(asset_refs) == 0:
        raise ValueError("Album has no images.")

    pool: list[str] = [asset_ref for asset_ref in asset_refs if asset_ref != exclude]

    if len(pool) == 0:
        pool = list(asset_refs)

    chosen_ref: str = rng.choice(pool)

    return chosen_ref


def resolve_theme_image_path(
    asset_reference: str,
    resolved_storage_directory: Path,
) -> Path:
    """Resolve a theme image ref to a file path.

    ``theme-defaults/<filename>`` is read from this package. Every other
    ref, including an older ``backgrounds/harbor.png``, is resolved
    against the artifact store.

    Args:
        asset_reference: Stored relative path.
        resolved_storage_directory: Absolute artifact store root.

    Returns:
        Absolute candidate path. It may not exist.

    Raises:
        ArtifactAssetPathEscapeError: The ref leaves the package dir or the store.
    """

    default_filename: str | None = _theme_default_filename(asset_reference)

    if default_filename is None:

        return resolve_asset_reference_path(
            asset_reference,
            resolved_storage_directory,
        )

    image_directory: Path = default_image_directory()
    candidate_path: Path = (image_directory / default_filename).resolve()

    if not candidate_path.is_relative_to(image_directory):
        raise ArtifactAssetPathEscapeError(asset_reference)

    return candidate_path


def _theme_default_filename(asset_reference: str) -> str | None:
    """Return the single filename under ``theme-defaults/``, or null."""

    stripped_reference: str = asset_reference.strip()

    if not stripped_reference.startswith(THEME_DEFAULTS_PREFIX):

        return None

    filename: str = stripped_reference[len(THEME_DEFAULTS_PREFIX):]

    if filename == "" or "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise ArtifactAssetPathEscapeError(asset_reference)

    return filename
