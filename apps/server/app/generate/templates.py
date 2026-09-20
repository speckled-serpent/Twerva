"""Named Spotmu carousel templates (internal, restricted set).

Phase 1–2: Spotmu-only variants that share the 1080×1080 text-led rules
in `docs/planning/carousel_template_v1.md`. No freeform brand designer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.generate.errors import CarouselUnknownTemplateError


TEMPLATE_ID_SPOTMU_PAPER_V1: str = "spotmu_paper_v1"
TEMPLATE_ID_SPOTMU_BOLD_V1: str = "spotmu_bold_v1"
DEFAULT_CAROUSEL_TEMPLATE_ID: str = TEMPLATE_ID_SPOTMU_PAPER_V1
CANVAS_WIDTH_PIXELS: int = 1080
CANVAS_HEIGHT_PIXELS: int = 1080


@dataclass(frozen=True)
class CarouselTemplate:
    """Visual tokens for one restricted Spotmu carousel template."""

    template_id: str
    name: str
    description: str
    color_background: str
    color_ink: str
    color_muted: str
    color_accent: str
    color_rule: str
    accent_rule_width_pixels: int
    accent_rule_height_pixels: int
    left_edge_stripe_width_pixels: int
    body_align_center: bool


SPOTMU_PAPER_V1: CarouselTemplate = CarouselTemplate(
    template_id=TEMPLATE_ID_SPOTMU_PAPER_V1,
    name="Spotmu Paper v1",
    description="Warm paper, near-black ink, thin teal accent. Current MVP look.",
    color_background="#F6F1E8",
    color_ink="#1C1917",
    color_muted="#57534E",
    color_accent="#0F766E",
    color_rule="#D6D3D1",
    accent_rule_width_pixels=120,
    accent_rule_height_pixels=4,
    left_edge_stripe_width_pixels=0,
    body_align_center=True,
)
SPOTMU_BOLD_V1: CarouselTemplate = CarouselTemplate(
    template_id=TEMPLATE_ID_SPOTMU_BOLD_V1,
    name="Spotmu Bold v1",
    description="Dark ground, cream ink, stronger teal accent and left stripe.",
    color_background="#1C1917",
    color_ink="#F6F1E8",
    color_muted="#A8A29E",
    color_accent="#2DD4BF",
    color_rule="#44403C",
    accent_rule_width_pixels=280,
    accent_rule_height_pixels=12,
    left_edge_stripe_width_pixels=20,
    body_align_center=False,
)
CAROUSEL_TEMPLATES_BY_ID: dict[str, CarouselTemplate] = {
    TEMPLATE_ID_SPOTMU_PAPER_V1: SPOTMU_PAPER_V1,
    TEMPLATE_ID_SPOTMU_BOLD_V1: SPOTMU_BOLD_V1,
}
CAROUSEL_TEMPLATE_ORDER: tuple[str, ...] = (
    TEMPLATE_ID_SPOTMU_PAPER_V1,
    TEMPLATE_ID_SPOTMU_BOLD_V1,
)


def list_carousel_templates() -> list[CarouselTemplate]:
    """Return the restricted Spotmu template set in display order.

    Returns:
        Frozen template tokens. Always at least two variants.
    """

    carousel_templates: list[CarouselTemplate] = [
        CAROUSEL_TEMPLATES_BY_ID[template_id]
        for template_id in CAROUSEL_TEMPLATE_ORDER
    ]

    return carousel_templates


def resolve_carousel_template(template_id: str | None) -> CarouselTemplate:
    """Resolve a template id, defaulting to paper v1.

    Args:
        template_id: Named template, or None / blank for the default.

    Returns:
        Template tokens.

    Raises:
        CarouselUnknownTemplateError: Id is set but not in the registry.
    """

    if template_id is None:

        return SPOTMU_PAPER_V1

    stripped_template_id: str = template_id.strip()

    if stripped_template_id == "":

        return SPOTMU_PAPER_V1

    found_template: CarouselTemplate | None = CAROUSEL_TEMPLATES_BY_ID.get(
        stripped_template_id,
    )

    if found_template is None:
        raise CarouselUnknownTemplateError(stripped_template_id)

    return found_template
