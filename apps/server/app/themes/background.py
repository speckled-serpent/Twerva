"""Validate one theme background. Does not draw or upload files."""

from __future__ import annotations

import re

from app.models.enums import BackgroundKind, ThemeStatus


HEX_COLOR_PATTERN: re.Pattern[str] = re.compile(r"^#[0-9A-Fa-f]{6}$")
ASSET_REF_SUFFIXES: tuple[str, ...] = (".svg", ".png", ".jpg", ".jpeg")

BACKGROUND_KIND_REQUIRED_DETAIL: str = "background_kind is required."
BACKGROUND_COLOR_DETAIL: str = "background_color must be # plus six hex digits."
BACKGROUND_GRADIENT_DETAIL: str = (
    "background_gradient must match "
    '{"angle_deg": <0-360>, "stops": [{"offset": <0-1>, "color": "#rrggbb"}, ...]} '
    "with at least two stops."
)
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

    if HEX_COLOR_PATTERN.fullmatch(stripped_color) is None:
        raise ThemeBackgroundError(BACKGROUND_COLOR_DETAIL)

    return stripped_color


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

    if not isinstance(gradient_value, dict):
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    gradient_object: dict[object, object] = gradient_value

    if set(gradient_object) != {"angle_deg", "stops"}:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    angle_deg: object = gradient_object["angle_deg"]
    stops_value: object = gradient_object["stops"]

    if not _is_number(angle_deg):
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    if isinstance(angle_deg, bool) or angle_deg < 0 or angle_deg > 360:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    if not isinstance(stops_value, list) or len(stops_value) < 2:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    normalized_stops: list[dict[str, object]] = [
        _normalize_gradient_stop(stop_value) for stop_value in stops_value
    ]
    normalized_gradient: dict[str, object] = {
        "angle_deg": angle_deg,
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


def _normalize_gradient_stop(stop_value: object) -> dict[str, object]:
    """Return one stop with ``offset`` and ``color`` only."""

    if not isinstance(stop_value, dict):
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    stop_object: dict[object, object] = stop_value

    if set(stop_object) != {"offset", "color"}:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    offset_value: object = stop_object["offset"]
    color_value: object = stop_object["color"]

    if not _is_number(offset_value) or offset_value < 0 or offset_value > 1:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    if not isinstance(color_value, str):
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    if HEX_COLOR_PATTERN.fullmatch(color_value) is None:
        raise ThemeBackgroundError(BACKGROUND_GRADIENT_DETAIL)

    normalized_stop: dict[str, object] = {
        "offset": offset_value,
        "color": color_value,
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
