"""Validate one theme background. Does not draw or upload files."""

from __future__ import annotations

import re

from app.models.enums import BackgroundKind, ThemeStatus


HEX_COLOR_PATTERN: re.Pattern[str] = re.compile(r"^#[0-9A-Fa-f]{6}$")
HEX_DIGIT_PATTERN: re.Pattern[str] = re.compile(r"^[0-9A-Fa-f]+$")
ASSET_REF_SUFFIXES: tuple[str, ...] = (".svg", ".png", ".jpg", ".jpeg")

DEFAULT_GRADIENT_ANGLE_DEG: int = 180
DEFAULT_GRADIENT_START_COLOR: str = "#4A4A4A"
DEFAULT_GRADIENT_END_COLOR: str = "#BDBDBD"

BACKGROUND_KIND_REQUIRED_DETAIL: str = "background_kind is required."
BACKGROUND_COLOR_DETAIL: str = "background_color must be # plus six hex digits."
BACKGROUND_GRADIENT_DETAIL: str = (
    "background_gradient must match "
    '{"angle_deg": <0-360>, "stops": [{"offset": <0-1>, "color": "#rrggbb"}, ...]} '
    "with at least two stops."
)
GRADIENT_NEEDS_SECOND_COLOR_DETAIL: str = "Can't draw gradient: add a second color"
GRADIENT_OFFSET_DETAIL: str = "Stop offsets must be between 0% and 100%"
GRADIENT_ANGLE_DETAIL: str = "Angle must be 0-360"
BACKGROUND_ASSET_REF_DETAIL: str = (
    "background_asset_ref must be a relative path with no .. and no scheme, "
    "ending in .svg, .png, .jpg, or .jpeg."
)
LIVE_COLOR_PAYLOAD_DETAIL: str = "A live color theme requires a background color."
LIVE_GRADIENT_PAYLOAD_DETAIL: str = (
    "A live gradient theme requires a background gradient."
)
LIVE_ASSET_PAYLOAD_DETAIL: str = (
    "A live picture or texture theme requires a background asset ref."
)


class ThemeBackgroundError(Exception):
    """A background value breaks the locked shape or the Live payload rule."""

    def __init__(self, detail: str) -> None:

        super().__init__(detail)
        self.detail: str = detail


class ResolvedThemeBackground:
    """Background fields after a partial patch, before they are written."""

    def __init__(
        self,
        background_kind: BackgroundKind,
        background_color: str | None,
        background_gradient: dict[str, object] | None,
        background_asset_ref: str | None,
    ) -> None:

        self.background_kind: BackgroundKind = background_kind
        self.background_color: str | None = background_color
        self.background_gradient: dict[str, object] | None = background_gradient
        self.background_asset_ref: str | None = background_asset_ref


def resolve_patched_background(
    current_kind: BackgroundKind,
    current_color: str | None,
    current_gradient: dict[str, object] | None,
    current_asset_ref: str | None,
    kind_is_set: bool,
    patched_kind: BackgroundKind | None,
    color_is_set: bool,
    patched_color: str | None,
    gradient_is_set: bool,
    patched_gradient: object | None,
    asset_ref_is_set: bool,
    patched_asset_ref: str | None,
    resulting_status: ThemeStatus,
) -> ResolvedThemeBackground:
    """Return the background a partial patch would store.

    A present color, gradient, or asset ref must match the locked shape.
    Blank color and asset ref store as null. Draft may leave the payload
    for the chosen kind empty. Live requires that payload.

    Args:
        current_kind: Kind already stored on the row.
        current_color: Color already stored, or null.
        current_gradient: Gradient already stored, or null.
        current_asset_ref: Asset ref already stored, or null.
        kind_is_set: True when the client sent ``background_kind``.
        patched_kind: Kind from the body.
        color_is_set: True when the client sent ``background_color``.
        patched_color: Color from the body.
        gradient_is_set: True when the client sent ``background_gradient``.
        patched_gradient: Gradient object from the body.
        asset_ref_is_set: True when the client sent ``background_asset_ref``.
        patched_asset_ref: Asset ref from the body.
        resulting_status: Status after this same patch.

    Returns:
        The kind and payloads to keep, including fields the client omitted.

    Raises:
        ThemeBackgroundError: The value is the wrong shape, or Live is
            missing the payload for its kind.
    """

    background_kind: BackgroundKind = _kind_after_patch(
        current_kind,
        kind_is_set,
        patched_kind,
    )
    background_color: str | None = current_color
    background_gradient: dict[str, object] | None = current_gradient
    background_asset_ref: str | None = current_asset_ref

    if color_is_set:
        background_color = normalize_background_color(patched_color)

    if gradient_is_set:
        background_gradient = normalize_background_gradient(patched_gradient)

    if asset_ref_is_set:
        background_asset_ref = normalize_background_asset_ref(patched_asset_ref)

    if resulting_status == ThemeStatus.LIVE:
        require_live_background_payload(
            background_kind,
            background_color,
            background_gradient,
            background_asset_ref,
        )

    resolved_background: ResolvedThemeBackground = ResolvedThemeBackground(
        background_kind,
        background_color,
        background_gradient,
        background_asset_ref,
    )

    return resolved_background


def normalize_background_color(color_value: str | None) -> str | None:
    """Return a hex color, or null when the client sent a blank string.

    Three or six hex digits are accepted, with or without a leading ``#``.
    The stored form is uppercase ``#RRGGBB``.

    Args:
        color_value: Raw color, or null.

    Returns:
        ``#`` plus six hex digits, or null when blank.

    Raises:
        ThemeBackgroundError: The text is not blank and not a hex color.
    """

    if color_value is None:

        return None

    stripped_color: str = color_value.strip()

    if stripped_color == "":

        return None

    expanded_color: str | None = expand_hex_color(stripped_color)

    if expanded_color is None:
        raise ThemeBackgroundError(BACKGROUND_COLOR_DETAIL)

    return expanded_color


def normalize_background_gradient(
    gradient_value: object | None,
) -> dict[str, object] | None:
    """Return the locked gradient object, or null when the client sent null.

    Shape: ``{"angle_deg": <0-360>, "stops": [{"offset": <0-1>,
    "color": "#rrggbb"}, ...]}`` with at least two stops.

    Args:
        gradient_value: JSON object from the patch, or null.

    Returns:
        The same shape with only ``angle_deg`` and ``stops``, or null.

    Raises:
        ThemeBackgroundError: The object is not that shape.
    """

    if gradient_value is None:

        return None

    gradient_problem: str | None = describe_gradient_problem(gradient_value)

    if gradient_problem is not None:
        raise ThemeBackgroundError(gradient_problem)

    if not isinstance(gradient_value, dict):
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    gradient_object: dict[object, object] = gradient_value

    if set(gradient_object) != {"angle_deg", "stops"}:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    stops_value: object = gradient_object["stops"]
    normalized_stops: list[dict[str, object]] = [
        _normalize_gradient_stop(stop_value, stop_index)
        for stop_index, stop_value in enumerate(stops_value)
    ]
    normalized_gradient: dict[str, object] = {
        "angle_deg": gradient_object["angle_deg"],
        "stops": normalized_stops,
    }

    return normalized_gradient


def normalize_background_asset_ref(asset_ref: str | None) -> str | None:
    """Return a relative asset path, or null when the client sent a blank string.

    Args:
        asset_ref: Raw path, or null.

    Returns:
        A relative path ending in ``.svg``, ``.png``, ``.jpg``, or ``.jpeg``.

    Raises:
        ThemeBackgroundError: The text is not blank and not an allowed path.
    """

    if asset_ref is None:

        return None

    stripped_asset_ref: str = asset_ref.strip()

    if stripped_asset_ref == "":

        return None

    if not _asset_ref_is_relative(stripped_asset_ref):
        raise ThemeBackgroundError(BACKGROUND_ASSET_REF_DETAIL)

    return stripped_asset_ref


def require_live_background_payload(
    background_kind: BackgroundKind,
    background_color: str | None,
    background_gradient: dict[str, object] | None,
    background_asset_ref: str | None,
) -> None:
    """Require the payload that belongs to a Live background kind.

    Args:
        background_kind: Kind after the patch.
        background_color: Color after the patch.
        background_gradient: Gradient after the patch.
        background_asset_ref: Asset ref after the patch.

    Raises:
        ThemeBackgroundError: Live is missing the payload for ``background_kind``.
    """

    if background_kind == BackgroundKind.COLOR and background_color is None:
        raise ThemeBackgroundError(LIVE_COLOR_PAYLOAD_DETAIL)

    if background_kind == BackgroundKind.GRADIENT and background_gradient is None:
        raise ThemeBackgroundError(LIVE_GRADIENT_PAYLOAD_DETAIL)

    asset_kinds: set[BackgroundKind] = {
        BackgroundKind.PICTURE,
        BackgroundKind.TEXTURE,
    }

    if background_kind in asset_kinds and background_asset_ref is None:
        raise ThemeBackgroundError(LIVE_ASSET_PAYLOAD_DETAIL)


def _kind_after_patch(
    current_kind: BackgroundKind,
    kind_is_set: bool,
    patched_kind: BackgroundKind | None,
) -> BackgroundKind:
    """Return the kind to store. Null kind is rejected."""

    if not kind_is_set:

        return current_kind

    if patched_kind is None:
        raise ThemeBackgroundError(BACKGROUND_KIND_REQUIRED_DETAIL)

    return patched_kind


def default_theme_gradient() -> dict[str, object]:
    """Return the two-stop gradient the editor prefills.

    Angle 180 runs from the top of the frame to the bottom. The first
    stop is ``#4A4A4A`` at 0% and the second is ``#BDBDBD`` at 100%.

    Returns:
        The locked gradient object.
    """

    default_gradient: dict[str, object] = {
        "angle_deg": DEFAULT_GRADIENT_ANGLE_DEG,
        "stops": [
            {"offset": 0, "color": DEFAULT_GRADIENT_START_COLOR},
            {"offset": 1, "color": DEFAULT_GRADIENT_END_COLOR},
        ],
    }

    return default_gradient


def expand_hex_color(color_value: str | None) -> str | None:
    """Return ``#RRGGBB``, or null when the text is blank or not hex.

    A leading ``#`` is optional. Three digits expand (``abc`` becomes
    ``#AABBCC``). Six digits are uppercased. Anything else is null.

    Args:
        color_value: Raw color text, or null.

    Returns:
        Uppercase ``#`` plus six hex digits, or null.
    """

    if color_value is None:

        return None

    stripped_color: str = color_value.strip()

    if stripped_color == "":

        return None

    hex_body: str = stripped_color[1:] if stripped_color.startswith("#") else stripped_color

    if HEX_DIGIT_PATTERN.fullmatch(hex_body) is None:

        return None

    if len(hex_body) == 3:
        expanded_body: str = "".join(character * 2 for character in hex_body)

        return f"#{expanded_body.upper()}"

    if len(hex_body) == 6:

        return f"#{hex_body.upper()}"

    return None


def describe_gradient_problem(gradient_value: object) -> str | None:
    """Return the fix for a gradient that cannot be drawn, or null.

    Args:
        gradient_value: JSON object from the form or a patch.

    Returns:
        A sentence naming the problem, or null when the gradient can be drawn.
    """

    if not isinstance(gradient_value, dict):

        return GRADIENT_NEEDS_SECOND_COLOR_DETAIL

    angle_deg: object = gradient_value.get("angle_deg")
    stops_value: object = gradient_value.get("stops")

    if not _is_number(angle_deg) or angle_deg < 0 or angle_deg > 360:

        return GRADIENT_ANGLE_DETAIL

    if not isinstance(stops_value, list) or len(stops_value) < 2:

        return GRADIENT_NEEDS_SECOND_COLOR_DETAIL

    for stop_index, stop_value in enumerate(stops_value):
        stop_problem: str | None = _gradient_stop_problem(stop_value, stop_index)

        if stop_problem is not None:

            return stop_problem

    return None


def clamp_stop_offset(offsets: list[float], index: int, next_offset: float) -> float:
    """Keep one stop between its neighbors so the list stays in order.

    Dragging past the next stop stops at that stop. The stops are not
    reordered, so the row being edited does not jump.

    Args:
        offsets: Current offsets, already in order, each 0 through 1.
        index: Stop being moved.
        next_offset: Requested offset before the neighbor limit.

    Returns:
        The offset to store, still between 0 and 1.
    """

    lower_neighbor: float = 0 if index <= 0 else offsets[index - 1]
    upper_neighbor: float = 1 if index >= len(offsets) - 1 else offsets[index + 1]
    lower_bound: float = max(0, lower_neighbor)
    upper_bound: float = min(1, upper_neighbor)
    clamped_offset: float = min(upper_bound, max(lower_bound, next_offset))

    return clamped_offset


def gradient_stop_color_detail(stop_number: int) -> str:
    """Return the hex error for one stop. ``stop_number`` is 1-based."""

    detail: str = f"Stop {stop_number} color isn't a valid hex color"

    return detail


def _gradient_stop_problem(stop_value: object, stop_index: int) -> str | None:
    """Return the first problem on one stop, or null."""

    if not isinstance(stop_value, dict):

        return GRADIENT_NEEDS_SECOND_COLOR_DETAIL

    offset_value: object = stop_value.get("offset")
    color_value: object = stop_value.get("color")

    if not _is_number(offset_value) or offset_value < 0 or offset_value > 1:

        return GRADIENT_OFFSET_DETAIL

    if not isinstance(color_value, str) or expand_hex_color(color_value) is None:

        return gradient_stop_color_detail(stop_index + 1)

    return None


def _normalize_gradient_stop(stop_value: object, stop_index: int) -> dict[str, object]:
    """Return one stop with ``offset`` and an expanded ``color``."""

    stop_problem: str | None = _gradient_stop_problem(stop_value, stop_index)

    if stop_problem is not None:
        raise ThemeBackgroundError(stop_problem)

    if not isinstance(stop_value, dict):
        raise ThemeBackgroundError(GRADIENT_NEEDS_SECOND_COLOR_DETAIL)

    stop_object: dict[object, object] = stop_value

    if set(stop_object) != {"offset", "color"}:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    color_value: object = stop_object["color"]
    expanded_color: str | None = expand_hex_color(color_value if isinstance(color_value, str) else None)

    if expanded_color is None:
        raise ThemeBackgroundError(gradient_stop_color_detail(stop_index + 1))

    normalized_stop: dict[str, object] = {
        "offset": stop_object["offset"],
        "color": expanded_color,
    }

    return normalized_stop


def _asset_ref_is_relative(asset_ref: str) -> bool:
    """Return True for a relative image path with an allowed suffix."""

    lowered_asset_ref: str = asset_ref.lower()
    suffix_is_allowed: bool = lowered_asset_ref.endswith(ASSET_REF_SUFFIXES)

    if not suffix_is_allowed:

        return False

    if ".." in asset_ref:

        return False

    if ":" in asset_ref or "\\" in asset_ref:

        return False

    if asset_ref.startswith("/"):

        return False

    return True


def _is_number(value: object) -> bool:
    """Return True for int or float, and False for bool."""

    if isinstance(value, bool):

        return False

    return isinstance(value, int | float)
