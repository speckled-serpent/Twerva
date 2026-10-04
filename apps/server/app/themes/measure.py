"""Measure theme text and images, then place the frame.

Text wraps inside the content width and the 1.10d layout reflows each
band. Images keep their aspect ratio. A missing or unreadable image is
a measure problem and gets no rectangle. This module does not write
PNGs or decide overlap.
"""

from __future__ import annotations

import enum
import math
import uuid
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFont

from app.generate.carousel import (
    SYSTEM_BOLD_FONT_PATHS,
    SYSTEM_REGULAR_FONT_PATHS,
)
from app.models.enums import (
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
)
from app.storage.artifacts import (
    ArtifactAssetPathEscapeError,
    resolve_asset_reference_path,
)
from app.themes.layout import (
    LayoutElement,
    ThemeLayout,
    place_theme_elements,
)


_FONT_ROOTS: tuple[Path, ...] = (
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
)
_FONT_SUFFIXES: frozenset[str] = frozenset({".ttf", ".otf", ".ttc"})
_RASTER_SUFFIXES: frozenset[str] = frozenset({".png", ".jpg", ".jpeg"})
_LIGHT_WEIGHT: int = 300
_MEDIUM_WEIGHT: int = 500
_SEMIBOLD_WEIGHT: int = 600
_BOLD_WEIGHT: int = 700
_FONT_FILES_BY_KEY: dict[str, Path] | None = None


class MeasureProblemCode(enum.StrEnum):
    """Why one element could not be measured. No rectangle is invented."""

    MISSING_ASSET = "missing_asset"
    UNREADABLE_ASSET = "unreadable_asset"
    PATH_ESCAPE = "path_escape"


@dataclass(frozen=True)
class ThemeMeasureElement:
    """One element plus the content needed to measure it.

    Text ``resolved_text`` is already chosen (for example by
    ``resolve_theme_text``). Underline, strikethrough, and alignment are
    stored and do not change the measured width or height.
    """

    element_id: uuid.UUID
    band: ThemeElementBand
    sort_order: int
    content_kind: ThemeElementContentKind
    resolved_text: str | None = None
    font_family: str | None = None
    font_size: int | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    font_weight: int | None = None
    alignment: ThemeElementAlignment | None = None
    image_asset_ref: str | None = None


@dataclass(frozen=True)
class MeasureProblem:
    """A structured failure for one element. That element has no rectangle."""

    element_id: uuid.UUID
    code: MeasureProblemCode
    detail: str


@dataclass(frozen=True)
class ThemeMeasurement:
    """Placed frame plus problems for elements that were not placed."""

    layout: ThemeLayout
    problems: tuple[MeasureProblem, ...]


@dataclass(frozen=True)
class _ImageMeasureFailure:
    """Image failure before it is attached to an element id."""

    code: MeasureProblemCode
    detail: str


def measure_theme_elements(
    frame_width: int,
    frame_height: int,
    page_margin: int,
    element_gap: int,
    element_margin: int,
    elements: Sequence[ThemeMeasureElement],
    artifact_storage_directory: Path,
) -> ThemeMeasurement:
    """Measure each element and place the frame with those heights.

    Text content height is the wrapped line count times one line of the
    face. Empty text is one line. An image's content height is its
    aspect ratio scaled to the content width. ``place_theme_elements``
    then stacks top downward, bottom upward, and recenters middle.

    Args:
        frame_width: Frame width in pixels. Carousel themes use 1080.
        frame_height: Frame height in pixels. Carousel themes use 1080.
        page_margin: Inset applied on every edge of the frame.
        element_gap: Space between rectangles in the same band.
        element_margin: Space between content and each edge of the rectangle.
        elements: Text with resolved copy, or images with an asset ref.
        artifact_storage_directory: Root for ``image_asset_ref`` files.

    Returns:
        The layout, and one problem per image that could not be read.
        A problem's element is omitted from ``layout.rectangles``.
    """

    content_width: int = _content_width(frame_width, page_margin, element_margin)
    layout_elements: list[LayoutElement] = []
    problems: list[MeasureProblem] = []

    for element in elements:
        content_height: int | None = _content_height_for_element(
            element,
            content_width,
            artifact_storage_directory,
            problems,
        )

        if content_height is None:

            continue

        layout_elements.append(
            LayoutElement(
                element_id=element.element_id,
                band=element.band,
                sort_order=element.sort_order,
                content_height=content_height,
            ),
        )

    layout: ThemeLayout = place_theme_elements(
        frame_width,
        frame_height,
        page_margin,
        element_gap,
        element_margin,
        layout_elements,
    )

    return ThemeMeasurement(layout=layout, problems=tuple(problems))


def _content_height_for_element(
    element: ThemeMeasureElement,
    content_width: int,
    artifact_storage_directory: Path,
    problems: list[MeasureProblem],
) -> int | None:
    """Return a content height, or record a problem and return null."""

    if element.content_kind == ThemeElementContentKind.IMAGE:

        image_height: int | _ImageMeasureFailure = _image_content_height(
            element.image_asset_ref or "",
            content_width,
            artifact_storage_directory,
        )

        if isinstance(image_height, _ImageMeasureFailure):
            problems.append(
                MeasureProblem(
                    element_id=element.element_id,
                    code=image_height.code,
                    detail=image_height.detail,
                ),
            )

            return None

        return image_height

    text_height: int = _text_content_height(
        element.resolved_text or "",
        element.font_family or "",
        element.font_size or 1,
        element.bold,
        element.italic,
        element.font_weight,
        content_width,
    )

    return text_height


def _content_width(frame_width: int, page_margin: int, element_margin: int) -> int:
    """Return the width text and images wrap or scale into.

    Element width is the frame inside ``page_margin``. Content width
    insets that by ``element_margin`` on the left and right.
    """

    element_width: int = frame_width - page_margin - page_margin
    content_width: int = element_width - element_margin - element_margin

    return content_width


def _text_content_height(
    text: str,
    font_family: str,
    font_size: int,
    bold: bool,
    italic: bool,
    font_weight: int | None,
    content_width: int,
) -> int:
    """Return wrapped text height. Empty text is one line of the face."""

    face: ImageFont.ImageFont = _load_face(
        font_family,
        font_size,
        bold,
        italic,
        font_weight,
    )
    line_height: int = _line_height(face)

    if text == "":

        return line_height

    wrapped_lines: list[str] = _wrap_text(text, face, content_width)
    line_count: int = len(wrapped_lines)

    if line_count < 1:

        return line_height

    content_height: int = line_count * line_height

    return content_height


def _wrap_text(
    text: str,
    face: ImageFont.ImageFont,
    content_width: int,
) -> list[str]:
    """Wrap on spaces inside ``content_width``. Newlines start a line."""

    paragraphs: list[str] = text.split("\n")
    wrapped_lines: list[str] = []

    for paragraph in paragraphs:

        if content_width <= 0:
            wrapped_lines.append(paragraph)

            continue

        words: list[str] = paragraph.split()

        if not words:
            wrapped_lines.append("")

            continue

        current_words: list[str] = []

        for word in words:
            candidate_words: list[str] = current_words + [word]
            candidate_line: str = " ".join(candidate_words)
            candidate_width: int = _text_width(face, candidate_line)

            if current_words and candidate_width > content_width:
                wrapped_lines.append(" ".join(current_words))
                current_words = [word]

                continue

            current_words = candidate_words

        if current_words:
            wrapped_lines.append(" ".join(current_words))

    if not wrapped_lines:

        return [""]

    return wrapped_lines


def _text_width(face: ImageFont.ImageFont, text: str) -> int:
    """Return the advance width in whole pixels, rounded up."""

    length_getter: object = getattr(face, "getlength", None)

    if length_getter is not None:
        measured_width: float = float(length_getter(text))

        if measured_width <= 0:

            return 0

        return math.ceil(measured_width)

    text_bbox: tuple[int, int, int, int] = face.getbbox(text)
    bbox_width: int = text_bbox[2] - text_bbox[0]

    return bbox_width


def _line_height(face: ImageFont.ImageFont) -> int:
    """Return one line of this face. Decoration does not add pixels."""

    ascent: int
    descent: int
    ascent, descent = face.getmetrics()
    line_height: int = ascent + descent

    if line_height < 1:

        return 1

    return line_height


def _load_face(
    font_family: str,
    font_size: int,
    bold: bool,
    italic: bool,
    font_weight: int | None,
) -> ImageFont.ImageFont:
    """Load the requested face, or the carousel DejaVu / Liberation fallback."""

    safe_size: int = font_size if font_size > 0 else 1
    family_face: ImageFont.FreeTypeFont | None = _load_family_face(
        font_family,
        safe_size,
        bold,
        italic,
        font_weight,
    )

    if family_face is not None:
        _apply_weight_axis(family_face, font_weight)

        return family_face

    use_bold_fallback: bool = bold or _weight_requests_bold(font_weight)
    fallback_face: ImageFont.ImageFont = _load_fallback_face(safe_size, use_bold_fallback)

    if isinstance(fallback_face, ImageFont.FreeTypeFont):
        _apply_weight_axis(fallback_face, font_weight)

    return fallback_face


def _load_family_face(
    font_family: str,
    font_size: int,
    bold: bool,
    italic: bool,
    font_weight: int | None,
) -> ImageFont.FreeTypeFont | None:
    """Return a file for this family and style, or null when none exists."""

    font_files: dict[str, Path] = _font_files_by_key()

    for candidate_key in _candidate_font_keys(font_family, bold, italic, font_weight):
        font_path: Path | None = font_files.get(candidate_key)

        if font_path is None:

            continue

        loaded_face: ImageFont.FreeTypeFont | None = _load_font_file(font_path, font_size)

        if loaded_face is not None:

            return loaded_face

    return None


def _load_fallback_face(font_size: int, bold: bool) -> ImageFont.ImageFont:
    """Same file order as ``app.generate.carousel._load_canvas_font``."""

    font_path_candidates: tuple[str, ...] = SYSTEM_REGULAR_FONT_PATHS

    if bold:
        font_path_candidates = SYSTEM_BOLD_FONT_PATHS

    for font_path_candidate in font_path_candidates:
        font_path: Path = Path(font_path_candidate)

        if not font_path.is_file():

            continue

        loaded_face: ImageFont.FreeTypeFont | None = _load_font_file(font_path, font_size)

        if loaded_face is not None:

            return loaded_face

    default_face: ImageFont.ImageFont = ImageFont.load_default(size=font_size)

    return default_face


def _load_font_file(font_path: Path, font_size: int) -> ImageFont.FreeTypeFont | None:
    """Open a font file, or null when FreeType rejects it."""

    try:
        loaded_face: ImageFont.FreeTypeFont = ImageFont.truetype(str(font_path), font_size)
    except OSError:

        return None

    return loaded_face


def _candidate_font_keys(
    font_family: str,
    bold: bool,
    italic: bool,
    font_weight: int | None,
) -> tuple[str, ...]:
    """Family file names to try, precise weight first."""

    family_key: str = _normalize_font_name(font_family)
    weight_token: str = _weight_token(font_weight, bold)
    italic_tokens: tuple[str, ...] = ("",)

    if italic:
        italic_tokens = ("italic", "oblique")

    candidate_keys: list[str] = []

    for italic_token in italic_tokens:
        candidate_keys.append(family_key + weight_token + italic_token)

    coarse_token: str = ""

    if bold or _weight_requests_bold(font_weight):
        coarse_token = "bold"

    if coarse_token != weight_token:

        for italic_token in italic_tokens:
            candidate_keys.append(family_key + coarse_token + italic_token)

    candidate_keys.append(family_key + weight_token)
    candidate_keys.append(family_key + "regular")
    candidate_keys.append(family_key)
    unique_keys: list[str] = []
    seen_keys: set[str] = set()

    for candidate_key in candidate_keys:

        if candidate_key == "" or candidate_key in seen_keys:

            continue

        seen_keys.add(candidate_key)
        unique_keys.append(candidate_key)

    return tuple(unique_keys)


def _weight_token(font_weight: int | None, bold: bool) -> str:
    """Map a CSS weight, or the bold flag, onto a file-name token."""

    if font_weight is None:

        if bold:

            return "bold"

        return ""

    if font_weight >= _BOLD_WEIGHT:

        return "bold"

    if font_weight >= _SEMIBOLD_WEIGHT:

        return "semibold"

    if font_weight >= _MEDIUM_WEIGHT:

        return "medium"

    if font_weight <= _LIGHT_WEIGHT:

        return "light"

    return ""


def _weight_requests_bold(font_weight: int | None) -> bool:
    """True when a numeric weight should select a bold cut."""

    if font_weight is None:

        return False

    return font_weight >= _SEMIBOLD_WEIGHT


def _normalize_font_name(font_name: str) -> str:
    """Lowercase letters and digits only, so ``DejaVu Sans`` matches the file."""

    normalized_name: str = "".join(
        character.lower()
        for character in font_name
        if character.isalnum()
    )

    return normalized_name


def _font_files_by_key() -> dict[str, Path]:
    """Index installed font files by a normalized stem. Cached after first use."""

    global _FONT_FILES_BY_KEY

    if _FONT_FILES_BY_KEY is not None:

        return _FONT_FILES_BY_KEY

    found_files: dict[str, Path] = {}

    for font_root in _FONT_ROOTS:

        if not font_root.is_dir():

            continue

        for font_path in font_root.rglob("*"):

            if font_path.suffix.lower() not in _FONT_SUFFIXES:

                continue

            font_key: str = _normalize_font_name(font_path.stem)

            if font_key in found_files:

                continue

            found_files[font_key] = font_path

    _FONT_FILES_BY_KEY = found_files

    return found_files


def _apply_weight_axis(face: ImageFont.FreeTypeFont, font_weight: int | None) -> None:
    """Set a variable font's ``wght`` axis when the face has one."""

    if font_weight is None:

        return

    variation_getter: object = getattr(face, "get_variation_axes", None)

    if variation_getter is None:

        return

    try:
        raw_axes: object = variation_getter()
    except OSError:

        return

    if not isinstance(raw_axes, list) or len(raw_axes) == 0:

        return

    coordinates: list[float] = []
    found_weight_axis: bool = False

    for raw_axis in raw_axes:

        if not isinstance(raw_axis, dict):

            return

        axis_name: object = raw_axis.get("name")

        if isinstance(axis_name, bytes):
            axis_name = axis_name.decode("ascii", "replace")

        if axis_name == "wght":
            minimum: float = float(raw_axis.get("minimum", font_weight))
            maximum: float = float(raw_axis.get("maximum", font_weight))
            clamped_weight: float = min(max(float(font_weight), minimum), maximum)
            coordinates.append(clamped_weight)
            found_weight_axis = True

            continue

        default_value: object = raw_axis.get("default", 0)
        coordinates.append(float(default_value))

    if not found_weight_axis:

        return

    variation_setter: object = getattr(face, "set_variation_by_axes", None)

    if variation_setter is None:

        return

    try:
        variation_setter(coordinates)
    except OSError:

        return


def _image_content_height(
    image_asset_ref: str,
    content_width: int,
    artifact_storage_directory: Path,
) -> int | _ImageMeasureFailure:
    """Scale an on-disk image to ``content_width`` and return that height."""

    if image_asset_ref.strip() == "":

        return _ImageMeasureFailure(
            code=MeasureProblemCode.MISSING_ASSET,
            detail="image file is missing",
        )

    resolved_storage_directory: Path = artifact_storage_directory.resolve()

    try:
        image_path: Path = resolve_asset_reference_path(
            image_asset_ref,
            resolved_storage_directory,
        )
    except ArtifactAssetPathEscapeError:

        return _ImageMeasureFailure(
            code=MeasureProblemCode.PATH_ESCAPE,
            detail="image_asset_ref escapes ARTIFACT_STORAGE_DIR",
        )

    if not image_path.is_file():

        return _ImageMeasureFailure(
            code=MeasureProblemCode.MISSING_ASSET,
            detail="image file is missing",
        )

    intrinsic_size: tuple[float, float] | _ImageMeasureFailure = _intrinsic_size(image_path)

    if isinstance(intrinsic_size, _ImageMeasureFailure):

        return intrinsic_size

    intrinsic_width: float = intrinsic_size[0]
    intrinsic_height: float = intrinsic_size[1]

    if content_width <= 0:

        return 0

    scaled_height: float = content_width * intrinsic_height / intrinsic_width
    content_height: int = int(round(scaled_height))

    if content_height < 0:

        return 0

    return content_height


def _intrinsic_size(image_path: Path) -> tuple[float, float] | _ImageMeasureFailure:
    """Read PNG, JPEG, or SVG pixel size. Do not guess when the file is bad."""

    suffix: str = image_path.suffix.lower()

    if suffix == ".svg":

        return _svg_intrinsic_size(image_path)

    if suffix not in _RASTER_SUFFIXES:

        return _ImageMeasureFailure(
            code=MeasureProblemCode.UNREADABLE_ASSET,
            detail="image file could not be read",
        )

    return _raster_intrinsic_size(image_path)


def _raster_intrinsic_size(image_path: Path) -> tuple[float, float] | _ImageMeasureFailure:
    """Read a PNG or JPEG size with Pillow."""

    try:
        with Image.open(image_path) as image:
            image_width: int = image.size[0]
            image_height: int = image.size[1]
    except OSError:

        return _ImageMeasureFailure(
            code=MeasureProblemCode.UNREADABLE_ASSET,
            detail="image file could not be read",
        )

    if image_width <= 0 or image_height <= 0:

        return _ImageMeasureFailure(
            code=MeasureProblemCode.UNREADABLE_ASSET,
            detail="image file could not be read",
        )

    return float(image_width), float(image_height)


def _svg_intrinsic_size(image_path: Path) -> tuple[float, float] | _ImageMeasureFailure:
    """Read SVG ``width``/``height``, otherwise ``viewBox``. No SVG library."""

    try:
        svg_root: ElementTree.Element = ElementTree.parse(image_path).getroot()
    except (ElementTree.ParseError, OSError):

        return _ImageMeasureFailure(
            code=MeasureProblemCode.UNREADABLE_ASSET,
            detail="image file could not be read",
        )

    svg_width: float | None = _parse_svg_length(svg_root.get("width"))
    svg_height: float | None = _parse_svg_length(svg_root.get("height"))

    if svg_width is not None and svg_height is not None:

        return svg_width, svg_height

    view_box_size: tuple[float, float] | None = _parse_view_box(svg_root.get("viewBox"))

    if view_box_size is None:

        return _ImageMeasureFailure(
            code=MeasureProblemCode.UNREADABLE_ASSET,
            detail="image file could not be read",
        )

    return view_box_size


def _parse_svg_length(raw_length: str | None) -> float | None:
    """Parse a positive SVG length. ``px`` is optional. Percentages are not."""

    if raw_length is None:

        return None

    stripped_length: str = raw_length.strip()

    if stripped_length.endswith("px"):
        stripped_length = stripped_length[:-2].strip()

    try:
        parsed_length: float = float(stripped_length)
    except ValueError:

        return None

    if parsed_length <= 0:

        return None

    return parsed_length


def _parse_view_box(raw_view_box: str | None) -> tuple[float, float] | None:
    """Return ``viewBox`` width and height, or null when the box is unusable."""

    if raw_view_box is None:

        return None

    view_box_parts: list[str] = raw_view_box.replace(",", " ").split()

    if len(view_box_parts) != 4:

        return None

    try:
        view_box_width: float = float(view_box_parts[2])
        view_box_height: float = float(view_box_parts[3])
    except ValueError:

        return None

    if view_box_width <= 0 or view_box_height <= 0:

        return None

    return view_box_width, view_box_height
