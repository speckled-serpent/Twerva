"""Seed rows for the Default album of six packaged photos.

Paths stay ``theme-defaults/<filename>``. Bytes stay in the package.
License and source URL come from ``default_images/LICENSES.md``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.models.enums import UnitImageLicense
from app.themes.default_images import (
    DEFAULT_IMAGE_FILENAMES,
    THEME_DEFAULTS_PREFIX,
    default_image_directory,
)


DEFAULT_ALBUM_SLUG: str = "default"
DEFAULT_ALBUM_NAMESPACE: uuid.UUID = uuid.UUID("c37b5a1e-4c0e-4a11-8d2e-6f0a8b4d1701")

_LICENSE_BY_FILENAME: dict[str, UnitImageLicense] = {
    "hong-kong-skyline.jpg": UnitImageLicense.CC0,
    "joshua-tree-desert.jpg": UnitImageLicense.PUBLIC_DOMAIN,
    "ocean-waves.jpg": UnitImageLicense.CC0,
    "santa-cruz-pacific.jpg": UnitImageLicense.CC0,
    "seoul-skyline.jpg": UnitImageLicense.CC0,
    "utah-dunes.jpg": UnitImageLicense.PUBLIC_DOMAIN,
}
_SOURCE_URL_BY_FILENAME: dict[str, str] = {
    "hong-kong-skyline.jpg": (
        "https://commons.wikimedia.org/wiki/File:"
        "Hong_Kong_skyscrapers_in_a_night_of_typhoon.jpg"
    ),
    "joshua-tree-desert.jpg": (
        "https://commons.wikimedia.org/wiki/File:"
        "A_Desert_Landscape_(53437341027).jpg"
    ),
    "ocean-waves.jpg": (
        "https://commons.wikimedia.org/wiki/File:Waves_in_sea.jpg"
    ),
    "santa-cruz-pacific.jpg": (
        "https://commons.wikimedia.org/wiki/File:"
        "Pacific_Ocean_along_Cliff_Drive,_Santa_Cruz_CA_Aug_2019.jpg"
    ),
    "seoul-skyline.jpg": (
        "https://commons.wikimedia.org/wiki/File:Seoul_Skyline_Night_2018.jpg"
    ),
    "utah-dunes.jpg": (
        "https://commons.wikimedia.org/wiki/File:"
        "Utah_Dunes_Landscape_-_West_Desert_District.jpg"
    ),
}


@dataclass(frozen=True)
class DefaultUnitSeed:
    """One image-only unit in the seeded Default album."""

    filename: str
    unit_id: uuid.UUID
    image_id: uuid.UUID
    position: int
    relative_path: str
    byte_size: int
    width: int
    height: int
    image_license: UnitImageLicense
    source_url: str


def default_album_source_id() -> uuid.UUID:
    """Return the stable id of the seeded Default album."""

    source_id: uuid.UUID = uuid.uuid5(DEFAULT_ALBUM_NAMESPACE, "source:default")

    return source_id


def default_unit_seeds() -> tuple[DefaultUnitSeed, ...]:
    """Return the six Default units, in catalog order.

    Raises:
        KeyError: A bundled filename has no license or source URL.
        FileNotFoundError: A bundled JPEG is missing from the package.
    """

    seeds: list[DefaultUnitSeed] = []
    image_directory: Path = default_image_directory()

    for position, filename in enumerate(DEFAULT_IMAGE_FILENAMES):
        image_license: UnitImageLicense = _LICENSE_BY_FILENAME[filename]
        source_url: str = _SOURCE_URL_BY_FILENAME[filename]
        image_path: Path = image_directory / filename
        byte_size: int = image_path.stat().st_size

        with Image.open(image_path) as image:
            width: int = int(image.size[0])
            height: int = int(image.size[1])

        seed: DefaultUnitSeed = DefaultUnitSeed(
            filename=filename,
            unit_id=uuid.uuid5(DEFAULT_ALBUM_NAMESPACE, f"unit:{filename}"),
            image_id=uuid.uuid5(DEFAULT_ALBUM_NAMESPACE, f"image:{filename}"),
            position=position,
            relative_path=f"{THEME_DEFAULTS_PREFIX}{filename}",
            byte_size=byte_size,
            width=width,
            height=height,
            image_license=image_license,
            source_url=source_url,
        )
        seeds.append(seed)

    return tuple(seeds)
