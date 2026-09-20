"""Plan and render a v1 text-led carousel from Spotmu-shaped source fields.

Template lock: `docs/planning/carousel_template_v1.md`. This module does
not open Postgres or settings. Callers pass a local storage directory.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.generate.templates import (
    CANVAS_HEIGHT_PIXELS,
    CANVAS_WIDTH_PIXELS,
    CarouselTemplate,
    resolve_carousel_template,
)
from app.storage.artifacts import write_artifact_slide_png_bytes


SAFE_INSET_PIXELS: int = 96
MAX_BULLET_CHARACTERS: int = 160
SLIDE_ROLE_COVER: str = "cover"
SLIDE_ROLE_HEADING: str = "heading"
SLIDE_ROLE_BULLET: str = "bullet"
SLIDE_ROLE_CTA: str = "cta"
COLOR_BACKGROUND: str = "#F6F1E8"
COLOR_INK: str = "#1C1917"
COLOR_MUTED: str = "#57534E"
COLOR_ACCENT: str = "#0F766E"
COLOR_RULE: str = "#D6D3D1"
CTA_PROMPT_TEXT: str = "Read more on Spotmu"
FOOTER_MARK_TEXT: str = "spotmu.com"
FALLBACK_CTA_URL: str = "https://spotmu.com"
SPOTMU_INTEREST_CTA_URL_PREFIX: str = "https://spotmu.com/interest/"
DEFAULT_HASHTAGS: tuple[str, ...] = (
    "#spotmu",
    "#learn",
    "#curiosity",
    "#ideas",
    "#carousel",
    "#readmore",
    "#interests",
)
ROLE_LABELS: dict[str, str] = {
    SLIDE_ROLE_COVER: "SPOTMU",
    SLIDE_ROLE_HEADING: "THE BRIEF",
    SLIDE_ROLE_BULLET: "NOTE",
    SLIDE_ROLE_CTA: "CONTINUE",
}
BODY_FONT_SIZES: dict[str, int] = {
    SLIDE_ROLE_COVER: 64,
    SLIDE_ROLE_HEADING: 56,
    SLIDE_ROLE_BULLET: 48,
    SLIDE_ROLE_CTA: 44,
}
LABEL_FONT_SIZE: int = 22
FOOTER_FONT_SIZE: int = 20
SYSTEM_REGULAR_FONT_PATHS: tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)
SYSTEM_BOLD_FONT_PATHS: tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
PNG_FORMAT_NAME: str = "PNG"


@dataclass(frozen=True)
class CarouselSourceFields:
    """Fields the template reads from a Spotmu-shaped SourceItem."""

    title: str
    interest_heading: str | None
    overview_bullets: list[str]
    canonical_url: str | None
    external_key: str | None


@dataclass(frozen=True)
class PlannedSlide:
    """One slide before pixels are written."""

    role: str
    text: str


@dataclass(frozen=True)
class RenderedSlide:
    """One slide after the PNG is on disk."""

    role: str
    text: str
    asset_ref: str


@dataclass(frozen=True)
class CarouselRenderResult:
    """Rendered frames plus caption and landing URL."""

    slides: list[RenderedSlide]
    caption: str
    cta_url: str


def render_carousel_from_source_fields(
    source_fields: CarouselSourceFields,
    artifact_identifier: uuid.UUID,
    artifact_storage_directory: Path,
    template_id: str | None = None,
) -> CarouselRenderResult:
    """Plan slides, draw PNGs, and write them under the artifact id.

    Args:
        source_fields: Title, heading, bullets, and URL fields.
        artifact_identifier: Destination folder name (Artifact UUID).
        artifact_storage_directory: Local `ARTIFACT_STORAGE_DIR`.
        template_id: Restricted Spotmu template; default paper v1.

    Returns:
        Ordered rendered slides, caption string, and `cta_url`.
    """

    carousel_template: CarouselTemplate = resolve_carousel_template(template_id)
    planned_slides: list[PlannedSlide] = plan_carousel_slides(source_fields)
    cta_url: str = resolve_carousel_cta_url(source_fields)
    caption: str = build_carousel_caption(source_fields, cta_url)
    rendered_slides: list[RenderedSlide] = []
    slide_count: int = len(planned_slides)

    for slide_index, planned_slide in enumerate(planned_slides):
        png_bytes: bytes = render_carousel_slide_png_bytes(
            planned_slide,
            slide_index,
            slide_count,
            carousel_template,
        )
        relative_asset_reference: str = write_artifact_slide_png_bytes(
            artifact_identifier,
            slide_index,
            planned_slide.role,
            png_bytes,
            artifact_storage_directory,
        )
        rendered_slide: RenderedSlide = RenderedSlide(
            role=planned_slide.role,
            text=planned_slide.text,
            asset_ref=relative_asset_reference,
        )
        rendered_slides.append(rendered_slide)

    carousel_render_result: CarouselRenderResult = CarouselRenderResult(
        slides=rendered_slides,
        caption=caption,
        cta_url=cta_url,
    )

    return carousel_render_result


def render_carousel_slide_png_bytes(
    planned_slide: PlannedSlide,
    slide_index: int,
    slide_count: int,
    carousel_template: CarouselTemplate | None = None,
) -> bytes:
    """Draw one 1080×1080 text-led slide and return PNG bytes.

    Args:
        planned_slide: Role and body copy.
        slide_index: 0-based index (footer counter).
        slide_count: Total slides in this carousel.
        carousel_template: Visual tokens; default paper v1.

    Returns:
        Encoded PNG payload.
    """

    resolved_template: CarouselTemplate

    if carousel_template is None:
        resolved_template = resolve_carousel_template(None)
    else:
        resolved_template = carousel_template

    canvas_image: Image.Image = Image.new(
        "RGB",
        (CANVAS_WIDTH_PIXELS, CANVAS_HEIGHT_PIXELS),
        resolved_template.color_background,
    )
    canvas_draw: ImageDraw.ImageDraw = ImageDraw.Draw(canvas_image)
    label_font: ImageFont.ImageFont = _load_canvas_font(LABEL_FONT_SIZE, bold=True)
    body_font_size: int = BODY_FONT_SIZES.get(planned_slide.role, 48)
    body_font: ImageFont.ImageFont = _load_canvas_font(body_font_size, bold=True)
    footer_font: ImageFont.ImageFont = _load_canvas_font(FOOTER_FONT_SIZE, bold=False)
    role_label: str = ROLE_LABELS.get(planned_slide.role, planned_slide.role.upper())
    content_width: int = CANVAS_WIDTH_PIXELS - (SAFE_INSET_PIXELS * 2)

    _draw_left_edge_stripe(canvas_draw, resolved_template)
    _draw_slide_label(canvas_draw, role_label, label_font, resolved_template)
    _draw_accent_rule(canvas_draw, resolved_template)
    _draw_body_text(
        canvas_draw,
        planned_slide.text,
        body_font,
        content_width,
        resolved_template,
    )
    _draw_slide_footer(
        canvas_draw,
        footer_font,
        slide_index,
        slide_count,
        resolved_template,
    )

    png_buffer: io.BytesIO = io.BytesIO()
    canvas_image.save(png_buffer, format=PNG_FORMAT_NAME)
    png_bytes: bytes = png_buffer.getvalue()

    return png_bytes


def _draw_left_edge_stripe(
    canvas_draw: ImageDraw.ImageDraw,
    carousel_template: CarouselTemplate,
) -> None:
    """Paint an optional full-height accent stripe on the left edge."""

    stripe_width: int = carousel_template.left_edge_stripe_width_pixels

    if stripe_width <= 0:

        return

    canvas_draw.rectangle(
        (0, 0, stripe_width, CANVAS_HEIGHT_PIXELS),
        fill=carousel_template.color_accent,
    )


def _draw_slide_label(
    canvas_draw: ImageDraw.ImageDraw,
    role_label: str,
    label_font: ImageFont.ImageFont,
    carousel_template: CarouselTemplate,
) -> None:
    """Paint the small role word at the top inset."""

    canvas_draw.text(
        (SAFE_INSET_PIXELS, SAFE_INSET_PIXELS),
        role_label,
        fill=carousel_template.color_muted,
        font=label_font,
    )


def _draw_accent_rule(
    canvas_draw: ImageDraw.ImageDraw,
    carousel_template: CarouselTemplate,
) -> None:
    """Paint an accent bar under the role label."""

    rule_top: int = SAFE_INSET_PIXELS + 48
    rule_bottom: int = rule_top + carousel_template.accent_rule_height_pixels
    rule_right: int = SAFE_INSET_PIXELS + carousel_template.accent_rule_width_pixels
    canvas_draw.rectangle(
        (SAFE_INSET_PIXELS, rule_top, rule_right, rule_bottom),
        fill=carousel_template.color_accent,
    )


def _draw_body_text(
    canvas_draw: ImageDraw.ImageDraw,
    body_text: str,
    body_font: ImageFont.ImageFont,
    content_width: int,
    carousel_template: CarouselTemplate,
) -> None:
    """Wrap and place the main copy (centered or left-aligned)."""

    wrapped_lines: list[str] = _wrap_text_to_width(
        body_text,
        body_font,
        content_width,
        canvas_draw,
    )
    line_height: int = _measure_line_height(body_font, canvas_draw)
    block_height: int = line_height * len(wrapped_lines)
    block_top: int = (CANVAS_HEIGHT_PIXELS - block_height) // 2
    line_top: int = block_top

    for wrapped_line in wrapped_lines:
        line_width: int = _measure_text_width(wrapped_line, body_font, canvas_draw)
        line_left: int

        if carousel_template.body_align_center:
            line_left = (CANVAS_WIDTH_PIXELS - line_width) // 2
        else:
            line_left = SAFE_INSET_PIXELS

        canvas_draw.text(
            (line_left, line_top),
            wrapped_line,
            fill=carousel_template.color_ink,
            font=body_font,
        )
        line_top += line_height


def _draw_slide_footer(
    canvas_draw: ImageDraw.ImageDraw,
    footer_font: ImageFont.ImageFont,
    slide_index: int,
    slide_count: int,
    carousel_template: CarouselTemplate,
) -> None:
    """Paint the spotmu.com mark and slide counter."""

    footer_top: int = CANVAS_HEIGHT_PIXELS - SAFE_INSET_PIXELS
    canvas_draw.text(
        (SAFE_INSET_PIXELS, footer_top),
        FOOTER_MARK_TEXT,
        fill=carousel_template.color_muted,
        font=footer_font,
    )
    counter_text: str = f"{slide_index + 1} / {slide_count}"
    counter_width: int = _measure_text_width(counter_text, footer_font, canvas_draw)
    counter_left: int = CANVAS_WIDTH_PIXELS - SAFE_INSET_PIXELS - counter_width
    canvas_draw.text(
        (counter_left, footer_top),
        counter_text,
        fill=carousel_template.color_muted,
        font=footer_font,
    )


def plan_carousel_slides(source_fields: CarouselSourceFields) -> list[PlannedSlide]:
    """Build the ordered cover → heading → bullets → CTA plan.

    Args:
        source_fields: Source title, heading, and overview bullets.

    Returns:
        Planned slides. Always includes cover, heading, and CTA.
    """

    cover_text: str = _first_non_blank_text(source_fields.title, "Untitled")
    heading_text: str = _first_non_blank_text(
        source_fields.interest_heading,
        cover_text,
    )
    planned_slides: list[PlannedSlide] = [
        PlannedSlide(role=SLIDE_ROLE_COVER, text=cover_text),
        PlannedSlide(role=SLIDE_ROLE_HEADING, text=heading_text),
    ]
    bullet_slide_texts: list[str] = _collect_bullet_slide_texts(
        source_fields.overview_bullets,
    )

    for bullet_text in bullet_slide_texts:
        planned_slides.append(PlannedSlide(role=SLIDE_ROLE_BULLET, text=bullet_text))

    cta_url: str = resolve_carousel_cta_url(source_fields)
    cta_text: str = f"{CTA_PROMPT_TEXT}\n{cta_url}"
    planned_slides.append(PlannedSlide(role=SLIDE_ROLE_CTA, text=cta_text))

    return planned_slides


def _collect_bullet_slide_texts(overview_bullets: list[str]) -> list[str]:
    """Skip empty bullets and split overflow past the character cap."""

    bullet_slide_texts: list[str] = []

    for raw_bullet in overview_bullets:
        stripped_bullet: str = str(raw_bullet).strip()

        if stripped_bullet == "":
            continue

        overflow_chunks: list[str] = _split_text_to_character_limit(
            stripped_bullet,
            MAX_BULLET_CHARACTERS,
        )
        bullet_slide_texts.extend(overflow_chunks)

    return bullet_slide_texts


def build_carousel_caption(source_fields: CarouselSourceFields, cta_url: str) -> str:
    """Build the short caption plus the locked safe hashtag set.

    Args:
        source_fields: Title and optional heading.
        cta_url: Already-resolved landing URL.

    Returns:
        Non-empty caption string for `artifact.caption`.
    """

    title_text: str = _first_non_blank_text(source_fields.title, "Untitled")
    heading_text: str = (source_fields.interest_heading or "").strip()
    caption_lines: list[str] = [title_text]

    if heading_text != "" and heading_text != title_text:
        caption_lines.append("")
        caption_lines.append(heading_text)

    caption_lines.append("")
    caption_lines.append(cta_url)
    caption_lines.append("")
    hashtag_line: str = " ".join(DEFAULT_HASHTAGS)
    caption_lines.append(hashtag_line)
    caption: str = "\n".join(caption_lines)

    return caption


def resolve_carousel_cta_url(source_fields: CarouselSourceFields) -> str:
    """Resolve `cta_url` from canonical URL, slug, or the Spotmu origin.

    Args:
        source_fields: Canonical URL and optional external key / slug.

    Returns:
        Absolute https URL.
    """

    canonical_url: str = (source_fields.canonical_url or "").strip()

    if canonical_url != "":

        return canonical_url

    external_key: str = (source_fields.external_key or "").strip()

    if external_key != "":

        return f"{SPOTMU_INTEREST_CTA_URL_PREFIX}{external_key}"

    return FALLBACK_CTA_URL


def carousel_source_fields_from_values(
    title: str,
    interest_heading: str | None,
    overview_bullets: list[object] | None,
    canonical_url: str | None,
    external_key: str | None,
) -> CarouselSourceFields:
    """Coerce source-item-like values into template fields.

    Args:
        title: Cover title.
        interest_heading: Optional heading.
        overview_bullets: JSONB list (strings preferred).
        canonical_url: Optional landing URL.
        external_key: Optional Spotmu slug.

    Returns:
        Typed source fields for plan/render.
    """

    bullet_texts: list[str] = []

    if overview_bullets is not None:

        for overview_bullet in overview_bullets:
            bullet_texts.append(str(overview_bullet))

    source_fields: CarouselSourceFields = CarouselSourceFields(
        title=title,
        interest_heading=interest_heading,
        overview_bullets=bullet_texts,
        canonical_url=canonical_url,
        external_key=external_key,
    )

    return source_fields


def _split_text_to_character_limit(text: str, character_limit: int) -> list[str]:
    """Split on words; hard-split a single token that exceeds the cap."""

    stripped_text: str = text.strip()

    if stripped_text == "":

        return []

    if len(stripped_text) <= character_limit:

        return [stripped_text]

    words: list[str] = stripped_text.split()
    chunks: list[str] = []
    current_words: list[str] = []

    for word in words:

        if not current_words and len(word) > character_limit:
            start_index: int = 0

            while start_index < len(word):
                chunks.append(word[start_index:start_index + character_limit])
                start_index += character_limit

            continue

        candidate_text: str = " ".join(current_words + [word])

        if current_words and len(candidate_text) > character_limit:
            chunks.append(" ".join(current_words))
            current_words = [word]
            continue

        current_words.append(word)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def _wrap_text_to_width(
    text: str,
    font: ImageFont.ImageFont,
    maximum_width: int,
    canvas_draw: ImageDraw.ImageDraw,
) -> list[str]:
    """Wrap on spaces so each line fits the content width."""

    source_lines: list[str] = text.splitlines() or [""]
    wrapped_lines: list[str] = []

    for source_line in source_lines:
        stripped_source_line: str = source_line.strip()

        if stripped_source_line == "":
            wrapped_lines.append("")
            continue

        words: list[str] = stripped_source_line.split()
        current_words: list[str] = []

        for word in words:
            candidate_line: str = " ".join(current_words + [word])
            candidate_width: int = _measure_text_width(
                candidate_line,
                font,
                canvas_draw,
            )

            if current_words and candidate_width > maximum_width:
                wrapped_lines.append(" ".join(current_words))
                current_words = [word]
                continue

            current_words.append(word)

        if current_words:
            wrapped_lines.append(" ".join(current_words))

    if not wrapped_lines:

        return [text]

    return wrapped_lines


def _measure_text_width(
    text: str,
    font: ImageFont.ImageFont,
    canvas_draw: ImageDraw.ImageDraw,
) -> int:
    """Return pixel width of `text` in `font`."""

    text_bbox: tuple[int, int, int, int] = canvas_draw.textbbox((0, 0), text, font=font)
    text_width: int = text_bbox[2] - text_bbox[0]

    return text_width


def _measure_line_height(
    font: ImageFont.ImageFont,
    canvas_draw: ImageDraw.ImageDraw,
) -> int:
    """Return a generous line box for wrapping."""

    sample_bbox: tuple[int, int, int, int] = canvas_draw.textbbox(
        (0, 0),
        "Hg",
        font=font,
    )
    line_height: int = (sample_bbox[3] - sample_bbox[1]) + 16

    return line_height


def _load_canvas_font(font_size: int, bold: bool) -> ImageFont.ImageFont:
    """Load a system TTF, or Pillow's default bitmap font."""

    font_path_candidates: tuple[str, ...]

    if bold:
        font_path_candidates = SYSTEM_BOLD_FONT_PATHS
    else:
        font_path_candidates = SYSTEM_REGULAR_FONT_PATHS

    for font_path_candidate in font_path_candidates:
        font_path: Path = Path(font_path_candidate)

        if not font_path.is_file():
            continue

        loaded_font: ImageFont.FreeTypeFont = ImageFont.truetype(
            str(font_path),
            font_size,
        )

        return loaded_font

    default_font: ImageFont.ImageFont = ImageFont.load_default()

    return default_font


def _first_non_blank_text(candidate_text: str | None, fallback_text: str) -> str:
    """Return stripped text, or `fallback_text` when blank."""

    if candidate_text is None:

        return fallback_text

    stripped_candidate: str = candidate_text.strip()

    if stripped_candidate == "":

        return fallback_text

    return stripped_candidate
