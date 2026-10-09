"""Theme element create, patch, and delete. No measurement or upload."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_theme_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    ThemeElementCreateRequest,
    ThemeElementPatchRequest,
    ThemeElementReadResponse,
)
from app.auth.dependencies import require_authenticated_ops_operator
from app.db import get_our_database_session
from app.models import OpsUser, Theme, ThemeElement
from app.models.enums import (
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
)
from app.themes.elements import (
    THEME_ELEMENT_BAND_REQUIRED_DETAIL,
    THEME_ELEMENT_SORT_ORDER_DETAIL,
    ResolvedThemeElement,
    ThemeElementError,
    assign_compact_sort_orders,
    assign_temporary_sort_orders,
    elements_in_band,
    insert_index,
    rectangle_opacity_value,
    rectangle_radius_value,
    resolve_theme_element,
)


THEME_ELEMENT_NOT_FOUND_DETAIL: str = "Theme element not found."
THEME_ELEMENT_SORT_ORDER_REQUIRED_DETAIL: str = "sort_order is required."


def register_theme_element_routes(themes_router: APIRouter) -> None:
    """Attach element routes to the theme router.

    Args:
        themes_router: Router mounted at ``/themes``.
    """

    themes_router.add_api_route(
        "/{theme_id}/elements",
        create_theme_element,
        methods=["POST"],
        response_model=ThemeElementReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    themes_router.add_api_route(
        "/{theme_id}/elements/{element_id}",
        patch_theme_element,
        methods=["PATCH"],
        response_model=ThemeElementReadResponse,
    )
    themes_router.add_api_route(
        "/{theme_id}/elements/{element_id}",
        delete_theme_element,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )


def create_theme_element(
    theme_id: uuid.UUID,
    theme_element_create_request: ThemeElementCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> ThemeElementReadResponse:
    """Add one full-width element and compact its band from 0."""

    _ = current_ops_operator
    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    _reject_negative_sort_order(theme_element_create_request.sort_order)
    resolved_element: ResolvedThemeElement = _resolve_or_raise(
        theme_element_create_request.content_kind,
        theme_element_create_request.rectangle_color,
        theme_element_create_request.text_source,
        theme_element_create_request.font_family,
        theme_element_create_request.font_size,
        theme_element_create_request.font_color,
        _created_flag(theme_element_create_request.bold),
        _created_flag(theme_element_create_request.italic),
        _created_flag(theme_element_create_request.underline),
        _created_flag(theme_element_create_request.strikethrough),
        theme_element_create_request.font_weight,
        theme_element_create_request.alignment,
        theme_element_create_request.image_asset_ref,
        theme_element_create_request.rectangle_opacity,
        theme_element_create_request.rectangle_radius,
    )
    created_element: ThemeElement = _new_theme_element(
        found_theme,
        theme_element_create_request.band,
        resolved_element,
    )
    found_theme.elements.append(created_element)
    our_database_session.add(created_element)
    _place_element(
        our_database_session,
        list(found_theme.elements),
        created_element,
        theme_element_create_request.band,
        theme_element_create_request.sort_order,
    )
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Theme element could not be saved (conflict).",
    )
    our_database_session.refresh(created_element)
    element_read_response: ThemeElementReadResponse = serialize_theme_element(
        created_element,
    )

    return element_read_response


def patch_theme_element(
    theme_id: uuid.UUID,
    element_id: uuid.UUID,
    theme_element_patch_request: ThemeElementPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> ThemeElementReadResponse:
    """Patch one element. Moving bands compacts both bands from 0."""

    _ = current_ops_operator
    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    found_element: ThemeElement = _fetch_theme_element_or_raise(
        found_theme,
        element_id,
        our_database_session,
    )
    assigned_fields: set[str] = theme_element_patch_request.model_fields_set
    _reject_patch_placement(theme_element_patch_request, assigned_fields)
    resolved_element: ResolvedThemeElement = _resolve_or_raise(
        _overlay(
            "content_kind",
            assigned_fields,
            theme_element_patch_request.content_kind,
            found_element.content_kind,
        ),
        _overlay(
            "rectangle_color",
            assigned_fields,
            theme_element_patch_request.rectangle_color,
            found_element.rectangle_color,
        ),
        _overlay(
            "text_source",
            assigned_fields,
            theme_element_patch_request.text_source,
            found_element.text_source,
        ),
        _overlay(
            "font_family",
            assigned_fields,
            theme_element_patch_request.font_family,
            found_element.font_family,
        ),
        _overlay(
            "font_size",
            assigned_fields,
            theme_element_patch_request.font_size,
            found_element.font_size,
        ),
        _overlay(
            "font_color",
            assigned_fields,
            theme_element_patch_request.font_color,
            found_element.font_color,
        ),
        _overlay(
            "bold",
            assigned_fields,
            theme_element_patch_request.bold,
            found_element.bold,
        ),
        _overlay(
            "italic",
            assigned_fields,
            theme_element_patch_request.italic,
            found_element.italic,
        ),
        _overlay(
            "underline",
            assigned_fields,
            theme_element_patch_request.underline,
            found_element.underline,
        ),
        _overlay(
            "strikethrough",
            assigned_fields,
            theme_element_patch_request.strikethrough,
            found_element.strikethrough,
        ),
        _overlay(
            "font_weight",
            assigned_fields,
            theme_element_patch_request.font_weight,
            found_element.font_weight,
        ),
        _overlay(
            "alignment",
            assigned_fields,
            theme_element_patch_request.alignment,
            found_element.alignment,
        ),
        _overlay(
            "image_asset_ref",
            assigned_fields,
            theme_element_patch_request.image_asset_ref,
            found_element.image_asset_ref,
        ),
        _overlay(
            "rectangle_opacity",
            assigned_fields,
            theme_element_patch_request.rectangle_opacity,
            found_element.rectangle_opacity,
        ),
        _overlay(
            "rectangle_radius",
            assigned_fields,
            theme_element_patch_request.rectangle_radius,
            found_element.rectangle_radius,
        ),
    )
    _apply_resolved_element(found_element, resolved_element)
    resulting_band: ThemeElementBand = found_element.band
    requested_sort_order: int | None = None
    placement_changes: bool = False

    if "band" in assigned_fields and theme_element_patch_request.band is not None:
        resulting_band = theme_element_patch_request.band
        placement_changes = True

    if "sort_order" in assigned_fields:
        requested_sort_order = theme_element_patch_request.sort_order
        placement_changes = True
    elif "band" in assigned_fields:
        requested_sort_order = None
        placement_changes = True

    if placement_changes:
        _place_element(
            our_database_session,
            list(found_theme.elements),
            found_element,
            resulting_band,
            requested_sort_order,
        )

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Theme element could not be updated (conflict).",
    )
    our_database_session.refresh(found_element)
    element_read_response: ThemeElementReadResponse = serialize_theme_element(
        found_element,
    )

    return element_read_response


def delete_theme_element(
    theme_id: uuid.UUID,
    element_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> None:
    """Delete one element and compact the band it left."""

    _ = current_ops_operator
    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    found_element: ThemeElement = _fetch_theme_element_or_raise(
        found_theme,
        element_id,
        our_database_session,
    )
    vacated_band: ThemeElementBand = found_element.band
    found_theme.elements.remove(found_element)
    our_database_session.delete(found_element)
    remaining_members: list[ThemeElement] = elements_in_band(
        found_theme.elements,
        vacated_band,
        None,
    )
    _store_band_order(our_database_session, remaining_members)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Theme element could not be deleted (conflict).",
    )


def prepare_new_theme_elements(
    element_requests: list[ThemeElementCreateRequest],
) -> list[tuple[ThemeElementCreateRequest, ResolvedThemeElement]]:
    """Validate create-body elements before the theme row is staged.

    Args:
        element_requests: Elements the client wants stored with the theme.

    Returns:
        Resolved elements in request order.

    Raises:
        HTTPException: 400 when an element breaks the text or image rules,
            or when ``sort_order`` is negative.
    """

    prepared_elements: list[tuple[ThemeElementCreateRequest, ResolvedThemeElement]] = []

    for element_request in element_requests:
        _reject_negative_sort_order(element_request.sort_order)
        resolved_element: ResolvedThemeElement = _resolve_or_raise(
            element_request.content_kind,
            element_request.rectangle_color,
            element_request.text_source,
            element_request.font_family,
            element_request.font_size,
            element_request.font_color,
            _created_flag(element_request.bold),
            _created_flag(element_request.italic),
            _created_flag(element_request.underline),
            _created_flag(element_request.strikethrough),
            element_request.font_weight,
            element_request.alignment,
            element_request.image_asset_ref,
            element_request.rectangle_opacity,
            element_request.rectangle_radius,
        )
        prepared_elements.append((element_request, resolved_element))

    return prepared_elements


def attach_prepared_theme_elements(
    theme: Theme,
    prepared_elements: list[tuple[ThemeElementCreateRequest, ResolvedThemeElement]],
    our_database_session: Session,
) -> None:
    """Append already validated elements. The caller commits.

    Args:
        theme: New theme row, already added to the session.
        prepared_elements: Output of ``prepare_new_theme_elements``.
        our_database_session: Open session. Flushed, not committed.
    """

    if len(prepared_elements) == 0:

        return

    our_database_session.flush()

    for element_request, resolved_element in prepared_elements:
        created_element: ThemeElement = _new_theme_element(
            theme,
            element_request.band,
            resolved_element,
        )
        theme.elements.append(created_element)
        our_database_session.add(created_element)
        _place_element(
            our_database_session,
            list(theme.elements),
            created_element,
            element_request.band,
            element_request.sort_order,
        )


def serialize_theme_element(element: ThemeElement) -> ThemeElementReadResponse:
    """Map a theme element row to the read schema.

    Args:
        element: Loaded element.

    Returns:
        API response without coordinates.
    """

    element_read_response: ThemeElementReadResponse = ThemeElementReadResponse(
        id=element.id,
        theme_id=element.theme_id,
        band=element.band,
        sort_order=element.sort_order,
        content_kind=element.content_kind,
        rectangle_color=element.rectangle_color,
        rectangle_opacity=rectangle_opacity_value(element.rectangle_opacity),
        rectangle_radius=rectangle_radius_value(element.rectangle_radius),
        text_source=element.text_source,
        font_family=element.font_family,
        font_size=element.font_size,
        font_color=element.font_color,
        bold=element.bold,
        italic=element.italic,
        underline=element.underline,
        strikethrough=element.strikethrough,
        font_weight=element.font_weight,
        alignment=element.alignment,
        image_asset_ref=element.image_asset_ref,
        created_at=element.created_at,
        updated_at=element.updated_at,
    )

    return element_read_response


def _new_theme_element(
    theme: Theme,
    band: ThemeElementBand,
    resolved_element: ResolvedThemeElement,
) -> ThemeElement:
    """Build an element row. Placement assigns the final sort_order."""

    created_element: ThemeElement = ThemeElement(
        theme_id=theme.id,
        band=band,
        sort_order=-1,
        content_kind=resolved_element.content_kind,
        rectangle_color=resolved_element.rectangle_color,
        rectangle_opacity=resolved_element.rectangle_opacity,
        rectangle_radius=resolved_element.rectangle_radius,
        text_source=resolved_element.text_source,
        font_family=resolved_element.font_family,
        font_size=resolved_element.font_size,
        font_color=resolved_element.font_color,
        bold=resolved_element.bold,
        italic=resolved_element.italic,
        underline=resolved_element.underline,
        strikethrough=resolved_element.strikethrough,
        font_weight=resolved_element.font_weight,
        alignment=resolved_element.alignment,
        image_asset_ref=resolved_element.image_asset_ref,
    )

    return created_element


def _apply_resolved_element(
    element: ThemeElement,
    resolved_element: ResolvedThemeElement,
) -> None:
    """Copy resolved content columns onto the row. Band is unchanged."""

    element.content_kind = resolved_element.content_kind
    element.rectangle_color = resolved_element.rectangle_color
    element.rectangle_opacity = resolved_element.rectangle_opacity
    element.rectangle_radius = resolved_element.rectangle_radius
    element.text_source = resolved_element.text_source
    element.font_family = resolved_element.font_family
    element.font_size = resolved_element.font_size
    element.font_color = resolved_element.font_color
    element.bold = resolved_element.bold
    element.italic = resolved_element.italic
    element.underline = resolved_element.underline
    element.strikethrough = resolved_element.strikethrough
    element.font_weight = resolved_element.font_weight
    element.alignment = resolved_element.alignment
    element.image_asset_ref = resolved_element.image_asset_ref


def _place_element(
    our_database_session: Session,
    elements: list[ThemeElement],
    element: ThemeElement,
    band: ThemeElementBand,
    requested_sort_order: int | None,
) -> None:
    """Insert ``element`` in ``band`` and renumber that band from 0."""

    previous_band: ThemeElementBand | None = None

    if element in elements and element.band != band:
        previous_band = element.band

    target_members: list[ThemeElement] = elements_in_band(elements, band, element)
    target_index: int = insert_index(requested_sort_order, len(target_members))
    element.band = band
    target_members.insert(target_index, element)
    _store_band_order(our_database_session, target_members)

    if previous_band is None:

        return

    previous_members: list[ThemeElement] = elements_in_band(
        elements,
        previous_band,
        element,
    )
    _store_band_order(our_database_session, previous_members)


def _store_band_order(
    our_database_session: Session,
    members: list[ThemeElement],
) -> None:
    """Write 0-based sort orders without colliding on the unique key."""

    if len(members) == 0:

        return

    assign_temporary_sort_orders(members)
    our_database_session.flush()
    assign_compact_sort_orders(members)


def _fetch_theme_element_or_raise(
    theme: Theme,
    element_id: uuid.UUID,
    our_database_session: Session,
) -> ThemeElement:
    """Return an element on this theme, or raise HTTP 404."""

    found_element: ThemeElement | None = our_database_session.get(
        ThemeElement,
        element_id,
    )

    if found_element is None or found_element.theme_id != theme.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{THEME_ELEMENT_NOT_FOUND_DETAIL} {element_id}",
        )

    return found_element


def _resolve_or_raise(
    content_kind: ThemeElementContentKind | None,
    rectangle_color: str | None,
    text_source: ThemeElementTextSource | None,
    font_family: str | None,
    font_size: int | None,
    font_color: str | None,
    bold: bool | None,
    italic: bool | None,
    underline: bool | None,
    strikethrough: bool | None,
    font_weight: int | None,
    alignment: ThemeElementAlignment | None,
    image_asset_ref: str | None,
    rectangle_opacity: int | None = None,
    rectangle_radius: int | None = None,
) -> ResolvedThemeElement:
    """Validate one element and map a rule failure to HTTP 400."""

    try:
        resolved_element: ResolvedThemeElement = resolve_theme_element(
            content_kind,
            rectangle_color,
            text_source,
            font_family,
            font_size,
            font_color,
            bold,
            italic,
            underline,
            strikethrough,
            font_weight,
            alignment,
            image_asset_ref,
            rectangle_opacity,
            rectangle_radius,
        )
    except ThemeElementError as element_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=element_error.detail,
        ) from element_error

    return resolved_element


def _reject_negative_sort_order(sort_order: int | None) -> None:
    """Reject a negative index. None means append."""

    if sort_order is None:

        return

    if sort_order < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=THEME_ELEMENT_SORT_ORDER_DETAIL,
        )


def _reject_patch_placement(
    theme_element_patch_request: ThemeElementPatchRequest,
    assigned_fields: set[str],
) -> None:
    """Reject an explicit null band or sort_order before any write."""

    if "band" in assigned_fields and theme_element_patch_request.band is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=THEME_ELEMENT_BAND_REQUIRED_DETAIL,
        )

    if (
        "sort_order" in assigned_fields
        and theme_element_patch_request.sort_order is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=THEME_ELEMENT_SORT_ORDER_REQUIRED_DETAIL,
        )

    _reject_negative_sort_order(theme_element_patch_request.sort_order)


def _created_flag(flag_value: bool | None) -> bool:
    """Default an omitted style flag to false."""

    if flag_value is None:

        return False

    return flag_value


def _overlay(
    field_name: str,
    assigned_fields: set[str],
    incoming_value: object,
    current_value: object,
) -> object:
    """Return the patch value when the client sent it, otherwise the stored one."""

    if field_name in assigned_fields:

        return incoming_value

    return current_value
