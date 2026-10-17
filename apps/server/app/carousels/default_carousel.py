"""Seed rows for the Default album of six packaged photos.

Paths stay ``theme-defaults/<filename>``. Bytes stay in the package.
License and source URL come from ``default_images/LICENSES.md``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.models.enums import SlideImageLicense
from app.skeletons.default_images import (
    DEFAULT_IMAGE_FILENAMES,
    SKELETON_DEFAULTS_PREFIX,
    default_image_directory,
)


DEFAULT_ALBUM_SLUG: str = "default"
DEFAULT_ALBUM_NAMESPACE: uuid.UUID = uuid.UUID("c37b5a1e-4c0e-4a11-8d2e-6f0a8b4d1701")
# Spotmu Paper v1, seeded by themes_create. The Default album is the
# shared photo catalog. Binding it here keeps the required skeleton, and
# skeleton pickers still list every carousel.
DEFAULT_ALBUM_SKELETON_ID: uuid.UUID = uuid.UUID("e8700eea-c086-5ce2-859d-b3d689af5c25")

_LICENSE_BY_FILENAME: dict[str, SlideImageLicense] = {
    "hong-kong-skyline.jpg": SlideImageLicense.CC0,
    "joshua-tree-desert.jpg": SlideImageLicense.PUBLIC_DOMAIN,
    "ocean-waves.jpg": SlideImageLicense.CC0,
    "santa-cruz-pacific.jpg": SlideImageLicense.CC0,
    "seoul-skyline.jpg": SlideImageLicense.CC0,
    "utah-dunes.jpg": SlideImageLicense.PUBLIC_DOMAIN,
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
class DefaultSlideSeed:
    """One image-only slide in the seeded Default album."""

    filename: str
    name: str
    slide_id: uuid.UUID
    image_id: uuid.UUID
    position: int
    relative_path: str
    byte_size: int
    width: int
    height: int
    image_license: SlideImageLicense
    source_url: str

    @property
    def unit_id(self) -> uuid.UUID:
        """Stable id stored before slides were renamed. Same value as ``slide_id``."""

        return self.slide_id


def default_slide_display_name(filename: str) -> str:
    """Return a stable name for one packaged photo.

    Args:
        filename: Bundled JPEG name, such as ``hong-kong-skyline.jpg``.

    Returns:
        A title-cased name without the suffix.
    """

    stem: str = filename.rsplit(".", 1)[0]
    display_name: str = " ".join(part.capitalize() for part in stem.split("-"))

    return display_name


def default_album_carousel_id() -> uuid.UUID:
    """Return the stable id of the seeded Default carousel."""

    carousel_id: uuid.UUID = uuid.uuid5(DEFAULT_ALBUM_NAMESPACE, "source:default")

    return carousel_id


def default_library_album_id() -> uuid.UUID:
    """Return the stable id of the Default album of packaged photos.

    The migration uses this same uuid5 value. The carousel id stays the
    older ``source:default`` value.
    """

    album_id: uuid.UUID = uuid.uuid5(DEFAULT_ALBUM_NAMESPACE, "album:default")

    return album_id


def default_slide_seeds() -> tuple[DefaultSlideSeed, ...]:
    """Return the six Default slides, in catalog order.

    Raises:
        KeyError: A bundled filename has no license or source URL.
        FileNotFoundError: A bundled JPEG is missing from the package.
    """

    seeds: list[DefaultSlideSeed] = []
    image_directory: Path = default_image_directory()

    for position, filename in enumerate(DEFAULT_IMAGE_FILENAMES):
        image_license: SlideImageLicense = _LICENSE_BY_FILENAME[filename]
        source_url: str = _SOURCE_URL_BY_FILENAME[filename]
        image_path: Path = image_directory / filename
        byte_size: int = image_path.stat().st_size

        with Image.open(image_path) as image:
            width: int = int(image.size[0])
            height: int = int(image.size[1])

        seed: DefaultSlideSeed = DefaultSlideSeed(
            filename=filename,
            name=default_slide_display_name(filename),
            slide_id=uuid.uuid5(DEFAULT_ALBUM_NAMESPACE, f"unit:{filename}"),
            image_id=uuid.uuid5(DEFAULT_ALBUM_NAMESPACE, f"image:{filename}"),
            position=position,
            relative_path=f"{SKELETON_DEFAULTS_PREFIX}{filename}",
            byte_size=byte_size,
            width=width,
            height=height,
            image_license=image_license,
            source_url=source_url,
        )
        seeds.append(seed)

    return tuple(seeds)
