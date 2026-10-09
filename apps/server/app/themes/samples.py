"""Render one theme frame as a preview PNG.

One request is one frame. Overview bullets stay one text block. This
module does not split slides, read ``carousel_template_v1``, insert
artifacts, insert post jobs, or change theme status.
"""

from __future__ import annotations

import enum
import io
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from PIL import Image, ImageDraw, ImageFont

from app.models.enums import (
    BackgroundKind,
    ThemeElementAlignment,
    ThemeElementContentKind,
)
from app.models.source_item import SourceItem
from app.models.theme import Theme
from app.models.theme_element import ThemeElement
from app.storage.artifacts import (
    ArtifactAssetPathEscapeError,
    ensure_artifact_storage_directory,
    resolve_asset_reference_path,
)
from app.themes.background import (
    GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
    describe_gradient_problem,
    expand_hex_color,
)
from app.themes.elements import ordered_theme_elements
from app.themes.layout import (
    THEME_FRAME_HEIGHT_PIXELS,
    THEME_FRAME_WIDTH_PIXELS,
    LayoutRectangle,
)
from app.themes.measure import (
    MeasureProblem,
    MeasureProblemCode,
    ThemeMeasureElement,
    ThemeMeasurement,
    load_theme_face,
    measure_theme_elements,
    theme_line_height,
    theme_text_width,
    wrap_theme_text,
)
from app.themes.overlap import (
    BandOverlap,
    InstanceOverlap,
    PlacedElement,
    find_band_overlaps,
)
from app.themes.sources import resolve_theme_text


THEME_PREVIEW_DIRECTORY: str = "theme-previews"
BACKGROUND_IMAGE_MISSING_DETAIL: str = "Background image file is missing."
BACKGROUND_IMAGE_UNREADABLE_DETAIL: str = "Background image file could not be read."
BACKGROUND_IMAGE_ESCAPE_DETAIL: str = (
    "Background image path escapes ARTIFACT_STORAGE_DIR."
)
BACKGROUND_COLOR_MISSING_DETAIL: str = "Background color is missing."
BACKGROUND_COLOR_INVALID_DETAIL: str = "Background color is not a hex color."
BACKGROUND_GRADIENT_MISSING_DETAIL: str = "Background gradient is missing."
_OPAQUE_ALPHA: int = 255


class ThemeSampleBlockReason(enum.StrEnum):
    """Why a preview must not ship. The PNG is still written."""

    OVERLAP = "overlap"
    MISSING_ASSET = "missing_asset"
    MEASURE_ERROR = "measure_error"


@dataclass(frozen=True)
class ThemeSampleRender:
    """PNG bytes plus the block payload for one frame."""

    png_bytes: bytes
    blocked: bool
    block_reason: ThemeSampleBlockReason | None
    detail: str | None
    overlaps: tuple[BandOverlap, ...]


@dataclass(frozen=True)
class _ParsedGradient:
    """Angle and color stops ready to rasterize. No radial component."""

    angle_deg: float
    stops: tuple[tuple[float, tuple[int, int, int]], ...]


def render_theme_sample(
    theme: Theme,
    source_item: SourceItem,
    artifact_storage_directory: Path,
) -> ThemeSampleRender:
    """Resolve, measure, place, overlap-check, and draw one frame.

    The background fills the frame first: a solid color, a linear
    gradient, or a picture or texture scaled to cover (no tiling). Each
    element rectangle is drawn next, skipping the fill when
    ``rectangle_color`` is null, then its text or image. Overlap still
    produces a PNG. A missing picture, texture, or image file does not
    invent a fill.

    Args:
        theme: Draft or Live carousel theme. Status is not changed.
        source_item: Spotmu interest whose text fields fill text elements.
        artifact_storage_directory: Root for background and image files.

    Returns:
        PNG bytes, whether the frame is blocked, the reason and detail,
        and the overlap pairs. ``blocked`` is true when ``block_reason``
        is set.
    """

    resolved_storage_directory: Path = artifact_storage_directory.expanduser().resolve()
    ordered_elements: list[ThemeElement] = ordered_theme_elements(theme.elements)
    measure_elements: list[ThemeMeasureElement] = [
        _measure_element(element, source_item) for element in ordered_elements
    ]
    measurement: ThemeMeasurement = measure_theme_elements(
        THEME_FRAME_WIDTH_PIXELS,
        THEME_FRAME_HEIGHT_PIXELS,
        theme.page_margin,
        theme.element_gap,
        theme.element_margin,
        measure_elements,
        resolved_storage_directory,
    )
    elements_by_id: dict[uuid.UUID, ThemeElement] = {
        element.id: element for element in ordered_elements
    }
    measure_by_id: dict[uuid.UUID, ThemeMeasureElement] = {
        element.element_id: element for element in measure_elements
    }
    placed_elements: list[PlacedElement] = []

    for rectangle in measurement.layout.rectangles:
        source_element: ThemeElement = elements_by_id[rectangle.element_id]
        placed_elements.append(
            PlacedElement(
                element_id=rectangle.element_id,
                band=source_element.band,
                x=rectangle.x,
                y=rectangle.y,
                width=rectangle.width,
                height=rectangle.height,
            ),
        )

    overlap: InstanceOverlap = find_band_overlaps((placed_elements,))[0]
    canvas: Image.Image = Image.new(
        "RGBA",
        (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS),
        (0, 0, 0, 0),
    )
    background_problem: tuple[ThemeSampleBlockReason, str] | None = _draw_background(
        canvas,
        theme,
        resolved_storage_directory,
    )
    canvas_draw: ImageDraw.ImageDraw = ImageDraw.Draw(canvas)
    draw_problems: list[MeasureProblem] = []

    for rectangle in measurement.layout.rectangles:
        _draw_element(
            canvas,
            canvas_draw,
            rectangle,
            elements_by_id[rectangle.element_id],
            measure_by_id[rectangle.element_id],
            theme.element_margin,
            resolved_storage_directory,
            draw_problems,
        )

    block_reason: ThemeSampleBlockReason | None
    detail: str | None
    block_reason, detail = _choose_block(
        background_problem,
        measurement.problems + tuple(draw_problems),
        overlap.blocked,
        overlap.overlaps,
    )
    encoded_png: io.BytesIO = io.BytesIO()
    canvas.save(encoded_png, format="PNG")
    png_bytes: bytes = encoded_png.getvalue()
    blocked: bool = block_reason is not None
    rendered: ThemeSampleRender = ThemeSampleRender(
        png_bytes=png_bytes,
        blocked=blocked,
        block_reason=block_reason,
        detail=detail,
        overlaps=overlap.overlaps,
    )

    return rendered


def theme_preview_relative_path(theme_id: uuid.UUID, preview_id: uuid.UUID) -> str:
    """Return ``theme-previews/{theme_id}/{preview_id}.png``.

    Args:
        theme_id: Theme that was sampled.
        preview_id: New id for this PNG. Not an artifact id.

    Returns:
        Path relative to ``ARTIFACT_STORAGE_DIR``.
    """

    relative_path: str = f"{THEME_PREVIEW_DIRECTORY}/{theme_id}/{preview_id}.png"

    return relative_path


def write_theme_preview_png(
    theme_id: uuid.UUID,
    preview_id: uuid.UUID,
    png_bytes: bytes,
    artifact_storage_directory: Path,
) -> Path:
    """Write one preview PNG under the artifact store.

    Args:
        theme_id: Directory name under ``theme-previews``.
        preview_id: File name, without a directory prefix from the client.
        png_bytes: Encoded preview.
        artifact_storage_directory: Configured store. Created if missing.

    Returns:
        Absolute path of the written file.
    """

    resolved_storage_directory: Path = ensure_artifact_storage_directory(
        artifact_storage_directory,
    )
    relative_path: str = theme_preview_relative_path(theme_id, preview_id)
    destination_path: Path = resolve_asset_reference_path(
        relative_path,
        resolved_storage_directory,
    )
    destination_parent: Path = destination_path.parent
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(png_bytes)

    return destination_path


def resolve_theme_preview_file(
    theme_id: uuid.UUID,
    preview_id: uuid.UUID,
    artifact_storage_directory: Path,
) -> Path | None:
    """Return the preview PNG if it is a file inside the store.

    Args:
        theme_id: Theme directory under ``theme-previews``.
        preview_id: Preview file id.
        artifact_storage_directory: Configured store.

    Returns:
        Absolute existing file, or null when it is missing or escapes.
    """

    resolved_storage_directory: Path = artifact_storage_directory.expanduser().resolve()
    relative_path: str = theme_preview_relative_path(theme_id, preview_id)

    try:
        candidate_path: Path = resolve_asset_reference_path(
            relative_path,
            resolved_storage_directory,
        )
    except ArtifactAssetPathEscapeError:

        return None

    if not candidate_path.is_file():

        return None

    return candidate_path


def _measure_element(
    element: ThemeElement,
    source_item: SourceItem,
) -> ThemeMeasureElement:
    """Copy one stored element into the measure input, with text resolved."""

    if element.content_kind == ThemeElementContentKind.IMAGE:
        image_element: ThemeMeasureElement = ThemeMeasureElement(
            element_id=element.id,
            band=element.band,
            sort_order=element.sort_order,
            content_kind=element.content_kind,
            image_asset_ref=element.image_asset_ref,
        )

        return image_element

    resolved_text: str = ""

    if element.text_source is not None:
        resolved_text = resolve_theme_text(source_item, element.text_source)

    text_element: ThemeMeasureElement = ThemeMeasureElement(
        element_id=element.id,
        band=element.band,
        sort_order=element.sort_order,
        content_kind=element.content_kind,
        resolved_text=resolved_text,
        font_family=element.font_family,
        font_size=element.font_size,
        bold=element.bold,
        italic=element.italic,
        underline=element.underline,
        strikethrough=element.strikethrough,
        font_weight=element.font_weight,
        alignment=element.alignment,
    )

    return text_element


def _draw_background(
    canvas: Image.Image,
    theme: Theme,
    resolved_storage_directory: Path,
) -> tuple[ThemeSampleBlockReason, str] | None:
    """Fill the frame. A missing picture or texture leaves it transparent."""

    if theme.background_kind == BackgroundKind.COLOR:

        return _draw_color_background(canvas, theme.background_color)

    if theme.background_kind == BackgroundKind.GRADIENT:

        return _draw_gradient_background(canvas, theme.background_gradient)

    if theme.background_kind == BackgroundKind.PICTURE or theme.background_kind == BackgroundKind.TEXTURE:

        return _draw_asset_background(
            canvas,
            theme.background_asset_ref,
            resolved_storage_directory,
        )

    assert_never(theme.background_kind)


def _draw_color_background(
    canvas: Image.Image,
    background_color: str | None,
) -> tuple[ThemeSampleBlockReason, str] | None:
    """Fill with one hex color, or report a measure error and leave it clear."""

    if background_color is None or background_color.strip() == "":

        return (ThemeSampleBlockReason.MEASURE_ERROR, BACKGROUND_COLOR_MISSING_DETAIL)

    parsed_color: tuple[int, int, int] | None = _parse_hex_color(background_color)

    if parsed_color is None:

        return (ThemeSampleBlockReason.MEASURE_ERROR, BACKGROUND_COLOR_INVALID_DETAIL)

    canvas.paste(_opaque(parsed_color), (0, 0, canvas.size[0], canvas.size[1]))

    return None


def _draw_gradient_background(
    canvas: Image.Image,
    background_gradient: dict[str, object] | None,
) -> tuple[ThemeSampleBlockReason, str] | None:
    """Draw a CSS linear gradient. 0° points up. 90° points right."""

    if background_gradient is None:

        return (
            ThemeSampleBlockReason.MEASURE_ERROR,
            BACKGROUND_GRADIENT_MISSING_DETAIL,
        )

    gradient_problem: str | None = describe_gradient_problem(background_gradient)

    if gradient_problem is not None:

        return (ThemeSampleBlockReason.MEASURE_ERROR, gradient_problem)

    parsed_gradient: _ParsedGradient | None = _parse_gradient(background_gradient)

    if parsed_gradient is None:

        return (
            ThemeSampleBlockReason.MEASURE_ERROR,
            GRADIENT_NEEDS_SECOND_COLOR_DETAIL,
        )

    frame_width: int = canvas.size[0]
    frame_height: int = canvas.size[1]
    gradient_image: Image.Image = _linear_gradient_image(
        frame_width,
        frame_height,
        parsed_gradient,
    )
    canvas.paste(gradient_image, (0, 0))

    return None


def _draw_asset_background(
    canvas: Image.Image,
    background_asset_ref: str | None,
    resolved_storage_directory: Path,
) -> tuple[ThemeSampleBlockReason, str] | None:
    """Scale a picture or texture to cover the frame. Do not tile."""

    if background_asset_ref is None or background_asset_ref.strip() == "":

        return (ThemeSampleBlockReason.MISSING_ASSET, BACKGROUND_IMAGE_MISSING_DETAIL)

    try:
        asset_path: Path = resolve_asset_reference_path(
            background_asset_ref,
            resolved_storage_directory,
        )
    except ArtifactAssetPathEscapeError:

        return (ThemeSampleBlockReason.MEASURE_ERROR, BACKGROUND_IMAGE_ESCAPE_DETAIL)

    if not asset_path.is_file():

        return (ThemeSampleBlockReason.MISSING_ASSET, BACKGROUND_IMAGE_MISSING_DETAIL)

    if asset_path.suffix.lower() == ".svg":

        return (
            ThemeSampleBlockReason.MEASURE_ERROR,
            BACKGROUND_IMAGE_UNREADABLE_DETAIL,
        )

    raster_image: Image.Image | None = _open_raster(asset_path)

    if raster_image is None:

        return (
            ThemeSampleBlockReason.MEASURE_ERROR,
            BACKGROUND_IMAGE_UNREADABLE_DETAIL,
        )

    frame_width: int = canvas.size[0]
    frame_height: int = canvas.size[1]
    covered_image: Image.Image = _cover_image(raster_image, frame_width, frame_height)
    canvas.paste(covered_image, (0, 0))

    return None


def _draw_element(
    canvas: Image.Image,
    canvas_draw: ImageDraw.ImageDraw,
    rectangle: LayoutRectangle,
    element: ThemeElement,
    measure_element: ThemeMeasureElement,
    element_margin: int,
    resolved_storage_directory: Path,
    draw_problems: list[MeasureProblem],
) -> None:
    """Draw one rectangle, then the content inset by ``element_margin``."""

    rectangle_color: tuple[int, int, int] | None = _parse_hex_color(element.rectangle_color)

    if element.rectangle_color is not None and rectangle_color is not None:
        _fill_rectangle(canvas_draw, rectangle, rectangle_color)

    content_box: tuple[int, int, int, int] | None = _content_box(rectangle, element_margin)

    if content_box is None:

        return

    content_x: int = content_box[0]
    content_y: int = content_box[1]
    content_width: int = content_box[2]
    content_height: int = content_box[3]

    if element.content_kind == ThemeElementContentKind.IMAGE:
        _draw_image_content(
            canvas,
            element.id,
            element.image_asset_ref,
            (content_x, content_y),
            (content_width, content_height),
            resolved_storage_directory,
            draw_problems,
        )

        return

    font_color: tuple[int, int, int] | None = _parse_hex_color(element.font_color)

    if font_color is None:

        return

    _draw_text_content(
        canvas_draw,
        measure_element,
        (content_x, content_y),
        content_width,
        font_color,
    )


def _fill_rectangle(
    canvas_draw: ImageDraw.ImageDraw,
    rectangle: LayoutRectangle,
    color: tuple[int, int, int],
) -> None:
    """Fill an integer rectangle. Pillow's box includes the far edge."""

    if rectangle.width <= 0 or rectangle.height <= 0:

        return

    far_x: int = rectangle.x + rectangle.width - 1
    far_y: int = rectangle.y + rectangle.height - 1
    canvas_draw.rectangle(
        (rectangle.x, rectangle.y, far_x, far_y),
        fill=_opaque(color),
    )


def _content_box(
    rectangle: LayoutRectangle,
    element_margin: int,
) -> tuple[int, int, int, int] | None:
    """Return x, y, width, height inside the rectangle, or null when empty."""

    content_width: int = rectangle.width - element_margin - element_margin
    content_height: int = rectangle.height - element_margin - element_margin

    if content_width <= 0 or content_height <= 0:

        return None

    content_x: int = rectangle.x + element_margin
    content_y: int = rectangle.y + element_margin

    return content_x, content_y, content_width, content_height


def _draw_text_content(
    canvas_draw: ImageDraw.ImageDraw,
    measure_element: ThemeMeasureElement,
    content_origin: tuple[int, int],
    content_width: int,
    font_color: tuple[int, int, int],
) -> None:
    """Draw wrapped lines. Empty text draws nothing. Decoration is not size."""

    resolved_text: str = measure_element.resolved_text or ""

    if resolved_text == "":

        return

    face: ImageFont.ImageFont = load_theme_face(
        measure_element.font_family or "",
        measure_element.font_size or 1,
        measure_element.bold,
        measure_element.italic,
        measure_element.font_weight,
    )
    wrapped_lines: list[str] = wrap_theme_text(resolved_text, face, content_width)
    line_height: int = theme_line_height(face)
    alignment: ThemeElementAlignment = (
        measure_element.alignment or ThemeElementAlignment.LEFT
    )
    fill: tuple[int, int, int, int] = _opaque(font_color)
    stroke_width: int = max(1, (measure_element.font_size or 1) // 16)
    content_x: int = content_origin[0]
    content_y: int = content_origin[1]

    for line_index, line in enumerate(wrapped_lines):
        line_top: int = content_y + line_index * line_height
        line_width: int = theme_text_width(face, line)
        line_x: int = _aligned_x(content_x, content_width, line_width, alignment)
        canvas_draw.text((line_x, line_top), line, font=face, fill=fill)
        line_end: int = line_x + max(line_width - 1, 0)

        if measure_element.underline and line != "":
            metrics: tuple[int, int] = face.getmetrics()
            ascent: int = metrics[0]
            underline_y: int = line_top + ascent + stroke_width
            canvas_draw.line(
                (line_x, underline_y, line_end, underline_y),
                fill=fill,
                width=stroke_width,
            )

        if measure_element.strikethrough and line != "":
            strike_y: int = line_top + line_height // 2
            canvas_draw.line(
                (line_x, strike_y, line_end, strike_y),
                fill=fill,
                width=stroke_width,
            )


def _draw_image_content(
    canvas: Image.Image,
    element_id: uuid.UUID,
    image_asset_ref: str | None,
    content_origin: tuple[int, int],
    content_size: tuple[int, int],
    resolved_storage_directory: Path,
    draw_problems: list[MeasureProblem],
) -> None:
    """Paste a PNG or JPEG into the content box. SVG stays a rectangle only."""

    if image_asset_ref is None or image_asset_ref.strip() == "":
        draw_problems.append(
            MeasureProblem(
                element_id=element_id,
                code=MeasureProblemCode.MISSING_ASSET,
                detail="image file is missing",
            ),
        )

        return

    try:
        image_path: Path = resolve_asset_reference_path(
            image_asset_ref,
            resolved_storage_directory,
        )
    except ArtifactAssetPathEscapeError:
        draw_problems.append(
            MeasureProblem(
                element_id=element_id,
                code=MeasureProblemCode.PATH_ESCAPE,
                detail="image_asset_ref escapes ARTIFACT_STORAGE_DIR",
            ),
        )

        return

    if image_path.suffix.lower() == ".svg":

        return

    if not image_path.is_file():
        draw_problems.append(
            MeasureProblem(
                element_id=element_id,
                code=MeasureProblemCode.MISSING_ASSET,
                detail="image file is missing",
            ),
        )

        return

    raster_image: Image.Image | None = _open_raster(image_path)

    if raster_image is None:
        draw_problems.append(
            MeasureProblem(
                element_id=element_id,
                code=MeasureProblemCode.UNREADABLE_ASSET,
                detail="image file could not be read",
            ),
        )

        return

    content_width: int = content_size[0]
    content_height: int = content_size[1]
    fitted_image: Image.Image = raster_image.resize(
        (content_width, content_height),
        Image.Resampling.LANCZOS,
    )
    canvas.paste(fitted_image, content_origin, fitted_image)


def _aligned_x(
    content_x: int,
    content_width: int,
    line_width: int,
    alignment: ThemeElementAlignment,
) -> int:
    """Return the left edge of one line inside the content box."""

    if alignment == ThemeElementAlignment.CENTER:
        centered_x: int = content_x + (content_width - line_width) // 2

        return centered_x

    if alignment == ThemeElementAlignment.RIGHT:
        right_x: int = content_x + content_width - line_width

        return right_x

    return content_x


def _choose_block(
    background_problem: tuple[ThemeSampleBlockReason, str] | None,
    problems: Sequence[MeasureProblem],
    overlap_blocked: bool,
    overlaps: tuple[BandOverlap, ...],
) -> tuple[ThemeSampleBlockReason | None, str | None]:
    """Pick one reason. Missing asset wins, then measure error, then overlap."""

    missing_detail: str | None = _missing_asset_detail(background_problem, problems)

    if missing_detail is not None:

        return ThemeSampleBlockReason.MISSING_ASSET, missing_detail

    if background_problem is not None and background_problem[0] == ThemeSampleBlockReason.MEASURE_ERROR:

        return ThemeSampleBlockReason.MEASURE_ERROR, background_problem[1]

    for problem in problems:

        return ThemeSampleBlockReason.MEASURE_ERROR, problem.detail

    if overlap_blocked:
        overlap_detail: str = _overlap_detail(overlaps)

        return ThemeSampleBlockReason.OVERLAP, overlap_detail

    return None, None


def _missing_asset_detail(
    background_problem: tuple[ThemeSampleBlockReason, str] | None,
    problems: Sequence[MeasureProblem],
) -> str | None:
    """Return the first missing-file detail, or null when every file was read."""

    if background_problem is not None and background_problem[0] == ThemeSampleBlockReason.MISSING_ASSET:

        return background_problem[1]

    for problem in problems:

        if problem.code == MeasureProblemCode.MISSING_ASSET:

            return problem.detail

    return None


def _overlap_detail(overlaps: tuple[BandOverlap, ...]) -> str:
    """Name each colliding band pair. ``band_a`` is the earlier band."""

    pair_details: list[str] = []

    for overlap in overlaps:
        pair_detail: str = f"{overlap.band_a.value} overlaps {overlap.band_b.value}."
        pair_details.append(pair_detail)

    detail: str = " ".join(pair_details)

    return detail


def _parse_hex_color(color_value: str | None) -> tuple[int, int, int] | None:
    """Return RGB for ``#`` plus six hex digits, or null."""

    expanded_color: str | None = expand_hex_color(color_value)

    if expanded_color is None:

        return None

    red: int = int(expanded_color[1:3], 16)
    green: int = int(expanded_color[3:5], 16)
    blue: int = int(expanded_color[5:7], 16)

    return red, green, blue


def _parse_gradient(gradient_value: dict[str, object]) -> _ParsedGradient | None:
    """Read the locked gradient object. Return null when it cannot be drawn."""

    angle_value: object = gradient_value.get("angle_deg")
    stops_value: object = gradient_value.get("stops")

    if isinstance(angle_value, bool) or not isinstance(angle_value, (int, float)):

        return None

    if not isinstance(stops_value, list) or len(stops_value) < 2:

        return None

    angle_deg: float = float(angle_value)

    if angle_deg < 0 or angle_deg > 360:

        return None

    parsed_stops: list[tuple[float, tuple[int, int, int]]] = []

    for stop_value in stops_value:

        if not isinstance(stop_value, dict):

            return None

        offset_value: object = stop_value.get("offset")
        color_value: object = stop_value.get("color")

        if isinstance(offset_value, bool) or not isinstance(offset_value, (int, float)):

            return None

        if not isinstance(color_value, str):

            return None

        offset: float = float(offset_value)

        if offset < 0 or offset > 1:

            return None

        stop_color: tuple[int, int, int] | None = _parse_hex_color(color_value)

        if stop_color is None:

            return None

        parsed_stops.append((offset, stop_color))

    parsed_stops.sort(key=lambda stop: stop[0])
    parsed_gradient: _ParsedGradient = _ParsedGradient(
        angle_deg=angle_deg,
        stops=tuple(parsed_stops),
    )

    return parsed_gradient


def _linear_gradient_image(
    frame_width: int,
    frame_height: int,
    parsed_gradient: _ParsedGradient,
) -> Image.Image:
    """Rasterize one linear gradient in screen space.

    CSS angles start at 0° pointing up and increase clockwise. The first
    stop is the start of that line. There is no radial mode.
    """

    direction: tuple[float, float] = _gradient_direction(parsed_gradient.angle_deg)
    direction_x: float = direction[0]
    direction_y: float = direction[1]
    corner_projections: list[float] = [
        x * direction_x + y * direction_y
        for x in (0, frame_width - 1)
        for y in (0, frame_height - 1)
    ]
    minimum_projection: float = min(corner_projections)
    maximum_projection: float = max(corner_projections)
    projection_span: float = maximum_projection - minimum_projection

    if projection_span <= 0:
        projection_span = 1

    pixels: list[tuple[int, int, int]] = []

    for pixel_y in range(frame_height):

        for pixel_x in range(frame_width):
            projection: float = pixel_x * direction_x + pixel_y * direction_y
            offset: float = (projection - minimum_projection) / projection_span
            pixels.append(_color_at_offset(parsed_gradient.stops, offset))

    gradient_image: Image.Image = Image.new("RGB", (frame_width, frame_height))
    gradient_image.putdata(pixels)

    return gradient_image


def _gradient_direction(angle_deg: float) -> tuple[float, float]:
    """Return a unit vector. 0° is up, 90° is right, in screen coordinates."""

    normalized_angle: float = angle_deg % 360

    if abs(normalized_angle - 0) < 1e-6 or abs(normalized_angle - 360) < 1e-6:

        return (0.0, -1.0)

    if abs(normalized_angle - 90) < 1e-6:

        return (1.0, 0.0)

    if abs(normalized_angle - 180) < 1e-6:

        return (0.0, 1.0)

    if abs(normalized_angle - 270) < 1e-6:

        return (-1.0, 0.0)

    angle_radians: float = math.radians(normalized_angle)
    direction_x: float = math.sin(angle_radians)
    direction_y: float = -math.cos(angle_radians)

    return direction_x, direction_y


def _color_at_offset(
    stops: tuple[tuple[float, tuple[int, int, int]], ...],
    offset: float,
) -> tuple[int, int, int]:
    """Interpolate RGB. Offsets before the first stop use the first color."""

    first_offset: float = stops[0][0]
    first_color: tuple[int, int, int] = stops[0][1]

    if offset <= first_offset:

        return first_color

    last_offset: float = stops[-1][0]
    last_color: tuple[int, int, int] = stops[-1][1]

    if offset >= last_offset:

        return last_color

    for stop_index in range(len(stops) - 1):
        left_offset: float = stops[stop_index][0]
        right_offset: float = stops[stop_index + 1][0]

        if offset > right_offset:

            continue

        left_color: tuple[int, int, int] = stops[stop_index][1]
        right_color: tuple[int, int, int] = stops[stop_index + 1][1]
        span: float = right_offset - left_offset

        if span <= 0:

            return right_color

        weight: float = (offset - left_offset) / span
        mixed_color: tuple[int, int, int] = _mix_color(left_color, right_color, weight)

        return mixed_color

    return last_color


def _mix_color(
    left_color: tuple[int, int, int],
    right_color: tuple[int, int, int],
    weight: float,
) -> tuple[int, int, int]:
    """Blend two RGB colors. ``weight`` 0 is the left color."""

    red: int = int(round(left_color[0] + (right_color[0] - left_color[0]) * weight))
    green: int = int(round(left_color[1] + (right_color[1] - left_color[1]) * weight))
    blue: int = int(round(left_color[2] + (right_color[2] - left_color[2]) * weight))

    return red, green, blue


def _cover_image(raster_image: Image.Image, frame_width: int, frame_height: int) -> Image.Image:
    """Scale until the frame is covered, then center-crop. Do not tile."""

    image_width: int = raster_image.size[0]
    image_height: int = raster_image.size[1]
    scale: float = max(frame_width / image_width, frame_height / image_height)
    scaled_width: int = max(frame_width, int(round(image_width * scale)))
    scaled_height: int = max(frame_height, int(round(image_height * scale)))
    resized_image: Image.Image = raster_image.resize(
        (scaled_width, scaled_height),
        Image.Resampling.LANCZOS,
    )
    crop_left: int = (scaled_width - frame_width) // 2
    crop_top: int = (scaled_height - frame_height) // 2
    covered_image: Image.Image = resized_image.crop(
        (crop_left, crop_top, crop_left + frame_width, crop_top + frame_height),
    )

    return covered_image


def _open_raster(image_path: Path) -> Image.Image | None:
    """Open a PNG or JPEG as RGBA, or null when Pillow cannot read it."""

    try:
        with Image.open(image_path) as image:
            raster_image: Image.Image = image.convert("RGBA").copy()
    except OSError:

        return None

    if raster_image.size[0] <= 0 or raster_image.size[1] <= 0:

        return None

    return raster_image


def _opaque(color: tuple[int, int, int]) -> tuple[int, int, int, int]:
    """Add a solid alpha channel."""

    opaque_color: tuple[int, int, int, int] = (
        color[0],
        color[1],
        color[2],
        _OPAQUE_ALPHA,
    )

    return opaque_color
