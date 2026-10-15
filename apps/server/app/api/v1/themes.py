"""Theme create/list/get/patch/duplicate. Samples render one preview frame."""

from __future__ import annotations

import copy
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_theme_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    ThemeCreateRequest,
    ThemeDefaultImagesResponse,
    ThemeElementCreateRequest,
    ThemeElementReadResponse,
    ThemeFontFamiliesResponse,
    ThemeFontFamilyResponse,
    ThemeImageAlbumResponse,
    ThemePatchRequest,
    ThemeReadResponse,
)
from app.auth.dependencies import require_authenticated_ops_operator
from app.db import get_our_database_session
from app.generate.templates import CAROUSEL_TEMPLATES_BY_ID
from app.models import (
    AdvertisementType,
    BackgroundKind,
    OpsUser,
    ContentSource,
    Theme,
    ThemeElement,
    ThemeStatus,
)
from app.models.base import Base
from app.models.theme import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
)
from app.themes.background import (
    ResolvedThemeBackground,
    ThemeBackgroundError,
    resolve_patched_background,
)
from app.themes.bundled_fonts import (
    FALLBACK_FONT_FAMILY_NAME,
    list_bundled_font_families,
)
from app.themes.default_images import list_theme_image_albums
from app.themes.elements import (
    ResolvedThemeElement,
    ordered_theme_elements,
    rectangle_opacity_value,
    rectangle_radius_value,
)
from app.themes.slug import allocate_unique_theme_slug, slugify_theme_name


THEME_NAME_REQUIRED_DETAIL: str = "Theme name is required."
THEME_STATUS_REQUIRED_DETAIL: str = "Theme status is required."
UNKNOWN_TEMPLATE_KEY_DETAIL: str = "Unknown carousel template."
DUPLICATE_THEME_NAME_PREFIX: str = "Copy of "
THEME_DELETE_CONFLICT_DETAIL: str = "Theme could not be deleted (conflict)."
THEME_DELETE_REFERENCED_DETAIL: str = (
    "Theme is still referenced and was not deleted."
)
_CREATE_FRAME_FIELDS: tuple[str, ...] = (
    "status",
    "page_margin",
    "element_gap",
    "element_margin",
    "background_kind",
    "background_color",
    "background_gradient",
    "background_asset_ref",
)

themes_router: APIRouter = APIRouter(prefix="/themes", tags=["themes"])


@themes_router.post(
    "",
    response_model=ThemeReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_theme(
    theme_create_request: ThemeCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> ThemeReadResponse:
    """Persist a carousel theme and its elements in one write.

    Omitted frame fields keep the defaults. A validation error commits
    nothing. Does not render or bind a campaign.
    """

    if theme_create_request.advertisement_type != AdvertisementType.CAROUSEL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only carousel themes are implemented.",
        )

    stripped_name: str = theme_create_request.name.strip()

    if stripped_name == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=THEME_NAME_REQUIRED_DETAIL,
        )

    template_key: str | None = _normalize_template_key(
        theme_create_request.template_key,
    )
    requested_slug: str = slugify_theme_name(stripped_name)
    taken_slugs: set[str] = _load_taken_theme_slugs(our_database_session)
    theme_slug: str = allocate_unique_theme_slug(requested_slug, taken_slugs)
    created_by: uuid.UUID | None = (
        None if current_ops_operator is None else current_ops_operator.id
    )
    created_theme: Theme = Theme(
        name=stripped_name,
        slug=theme_slug,
        advertisement_type=theme_create_request.advertisement_type,
        template_key=template_key,
        status=ThemeStatus.DRAFT,
        page_margin=DEFAULT_PAGE_MARGIN,
        element_gap=DEFAULT_ELEMENT_GAP,
        element_margin=DEFAULT_ELEMENT_MARGIN,
        background_kind=BackgroundKind.COLOR,
        background_color=DEFAULT_BACKGROUND_COLOR,
        background_gradient=None,
        background_asset_ref=None,
        created_by=created_by,
    )
    from app.api.v1.theme_elements import prepare_new_theme_elements

    prepared_elements = prepare_new_theme_elements(theme_create_request.elements)
    frame_patch: ThemePatchRequest | None = _frame_patch_for_create(theme_create_request)

    if frame_patch is not None:
        _apply_theme_patch(created_theme, frame_patch)

    our_database_session.add(created_theme)
    _attach_create_elements(
        created_theme,
        prepared_elements,
        our_database_session,
    )
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Theme slug or template already exists.",
    )
    our_database_session.refresh(created_theme)

    for created_element in list(created_theme.elements):
        our_database_session.refresh(created_element)

    theme_read_response: ThemeReadResponse = serialize_theme(created_theme)

    return theme_read_response


@themes_router.get("", response_model=list[ThemeReadResponse])
def list_themes(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[ThemeReadResponse]:
    """Return every Theme, newest first."""

    theme_selection = select(Theme).order_by(
        Theme.created_at.desc(),
        Theme.name.asc(),
    )
    theme_scalars = our_database_session.scalars(theme_selection)
    themes: list[Theme] = list(theme_scalars.all())
    theme_read_responses: list[ThemeReadResponse] = [
        serialize_theme(theme) for theme in themes
    ]

    return theme_read_responses


@themes_router.get("/default-images", response_model=ThemeDefaultImagesResponse)
def list_theme_default_images() -> ThemeDefaultImagesResponse:
    """Return bundled image albums. Readers may call this, same as preview.

    Registered before ``/{theme_id}`` so ``default-images`` is not parsed
    as a theme id.
    """

    album_responses: list[ThemeImageAlbumResponse] = [
        ThemeImageAlbumResponse(
            album_id=album.album_id,
            name=album.name,
            asset_refs=list(album.asset_refs),
        )
        for album in list_theme_image_albums()
    ]
    images_response: ThemeDefaultImagesResponse = ThemeDefaultImagesResponse(
        albums=album_responses,
    )

    return images_response


@themes_router.get("/font-families", response_model=ThemeFontFamiliesResponse)
def list_theme_font_families() -> ThemeFontFamiliesResponse:
    """Return bundled font families. Readers may call this, same as preview.

    Registered before ``/{theme_id}`` so ``font-families`` is not parsed
    as a theme id.
    """

    family_responses: list[ThemeFontFamilyResponse] = [
        ThemeFontFamilyResponse(
            family_id=family.family_id,
            name=family.name,
            category=family.category,
        )
        for family in list_bundled_font_families()
    ]
    fonts_response: ThemeFontFamiliesResponse = ThemeFontFamiliesResponse(
        families=family_responses,
        fallback_name=FALLBACK_FONT_FAMILY_NAME,
    )

    return fonts_response


@themes_router.get("/{theme_id}", response_model=ThemeReadResponse)
def get_theme_by_id(
    theme_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ThemeReadResponse:
    """Return one Theme by primary key."""

    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    theme_read_response: ThemeReadResponse = serialize_theme(found_theme)

    return theme_read_response


@themes_router.delete(
    "/{theme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_theme_by_id(
    theme_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> None:
    """Delete one theme and its elements.

    ``theme_elements`` uses ``ON DELETE CASCADE``. A source that stores
    this theme blocks the delete. Any other table that references
    ``themes`` blocks it too. Preview files on disk are not rows and are
    left in place. ``template_key`` is a column on this row, not a
    foreign key from campaigns or artifacts.
    """

    _ = current_ops_operator
    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    reference_blockers: list[str] = theme_delete_reference_blockers(
        our_database_session,
        found_theme.id,
    )

    if len(reference_blockers) > 0:
        blocker_names: str = ", ".join(reference_blockers)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{THEME_DELETE_REFERENCED_DETAIL} Referenced by {blocker_names}.",
        )

    our_database_session.delete(found_theme)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=THEME_DELETE_CONFLICT_DETAIL,
    )


@themes_router.patch("/{theme_id}", response_model=ThemeReadResponse)
def patch_theme_by_id(
    theme_id: uuid.UUID,
    theme_patch_request: ThemePatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> ThemeReadResponse:
    """Patch fields that are present. Status may move draft ↔ live."""

    _ = current_ops_operator
    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    _apply_theme_patch(found_theme, theme_patch_request)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Theme could not be updated (conflict).",
    )
    our_database_session.refresh(found_theme)
    theme_read_response: ThemeReadResponse = serialize_theme(found_theme)

    return theme_read_response


@themes_router.post(
    "/{theme_id}/duplicate",
    response_model=ThemeReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_theme_by_id(
    theme_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> ThemeReadResponse:
    """Copy one theme into a new Draft. The source row stays as it was."""

    source_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    copied_name: str = f"{DUPLICATE_THEME_NAME_PREFIX}{source_theme.name}"
    requested_slug: str = slugify_theme_name(copied_name)
    taken_slugs: set[str] = _load_taken_theme_slugs(our_database_session)
    copied_slug: str = allocate_unique_theme_slug(requested_slug, taken_slugs)
    created_by: uuid.UUID | None = (
        None if current_ops_operator is None else current_ops_operator.id
    )
    copied_gradient: dict[str, object] | None = copy.deepcopy(
        source_theme.background_gradient,
    )
    copied_theme: Theme = Theme(
        name=copied_name,
        slug=copied_slug,
        advertisement_type=source_theme.advertisement_type,
        template_key=None,
        status=ThemeStatus.DRAFT,
        page_margin=source_theme.page_margin,
        element_gap=source_theme.element_gap,
        element_margin=source_theme.element_margin,
        background_kind=source_theme.background_kind,
        background_color=source_theme.background_color,
        background_gradient=copied_gradient,
        background_asset_ref=source_theme.background_asset_ref,
        created_by=created_by,
    )
    our_database_session.add(copied_theme)
    our_database_session.flush()

    for source_element in ordered_theme_elements(source_theme.elements):
        copied_element: ThemeElement = _copy_theme_element(
            copied_theme.id,
            source_element,
        )
        copied_theme.elements.append(copied_element)
        our_database_session.add(copied_element)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Theme slug or template already exists.",
    )
    our_database_session.refresh(copied_theme)

    for copied_element in copied_theme.elements:
        our_database_session.refresh(copied_element)

    theme_read_response: ThemeReadResponse = serialize_theme(copied_theme)

    return theme_read_response


def serialize_theme(theme: Theme) -> ThemeReadResponse:
    """Map a Theme row to the read schema.

    Args:
        theme: Loaded theme.

    Returns:
        API response including slug, status, spacing, and template key.
    """

    theme_read_response: ThemeReadResponse = ThemeReadResponse(
        id=theme.id,
        name=theme.name,
        slug=theme.slug,
        advertisement_type=theme.advertisement_type,
        template_key=theme.template_key,
        status=theme.status,
        page_margin=theme.page_margin,
        element_gap=theme.element_gap,
        element_margin=theme.element_margin,
        background_kind=theme.background_kind,
        background_color=theme.background_color,
        background_gradient=theme.background_gradient,
        background_asset_ref=theme.background_asset_ref,
        elements=_serialized_theme_elements(theme),
        created_at=theme.created_at,
        updated_at=theme.updated_at,
        created_by=theme.created_by,
    )

    return theme_read_response


def _serialized_theme_elements(theme: Theme) -> list[ThemeElementReadResponse]:
    """Return elements ordered by band, then sort_order."""

    from app.api.v1.theme_elements import serialize_theme_element

    element_read_responses: list[ThemeElementReadResponse] = [
        serialize_theme_element(element)
        for element in ordered_theme_elements(theme.elements)
    ]

    return element_read_responses


def theme_spacing_required_detail(field_name: str) -> str:
    """Return the 400 detail for an explicit null spacing field."""

    required_detail: str = f"{field_name} is required."

    return required_detail


def theme_spacing_negative_detail(field_name: str) -> str:
    """Return the 400 detail for a negative spacing value."""

    negative_detail: str = f"{field_name} must be zero or greater."

    return negative_detail


def theme_delete_reference_blockers(
    our_database_session: Session,
    theme_id: uuid.UUID,
) -> list[str]:
    """Return tables that still make deleting this theme unsafe.

    ``theme_elements`` cascade with the theme. ``sources`` block only
    when a row stores this theme. Any other foreign key to ``themes``
    blocks the delete, because that table is not counted row by row.

    Returns:
        Sorted table names that would make a silent delete unsafe.
    """

    blocker_names: list[str] = unexpected_theme_reference_tables()
    source_count: int = _source_count_for_theme(our_database_session, theme_id)

    if source_count > 0:
        blocker_names.append("sources")

    unique_blockers: list[str] = sorted(set(blocker_names))

    return unique_blockers


def unexpected_theme_reference_tables() -> list[str]:
    """Return tables other than elements and sources that point at themes.

    Returns:
        Sorted table names. An empty list means only the known references.
    """

    blocker_names: list[str] = []

    for table in Base.metadata.tables.values():

        for foreign_key in table.foreign_keys:

            if foreign_key.column.table.name != "themes":
                continue

            if table.name in {"theme_elements", "sources"}:
                continue

            blocker_names.append(table.name)

    unique_blockers: list[str] = sorted(set(blocker_names))

    return unique_blockers


def _source_count_for_theme(
    our_database_session: Session,
    theme_id: uuid.UUID,
) -> int:
    """Count sources that store this theme."""

    counted: int | None = our_database_session.scalar(
        select(func.count())
        .select_from(ContentSource)
        .where(ContentSource.theme_id == theme_id),
    )

    if counted is None:
        return 0

    source_count: int = int(counted)

    return source_count


def _frame_patch_for_create(
    theme_create_request: ThemeCreateRequest,
) -> ThemePatchRequest | None:
    """Return a patch for the frame fields the create body included."""

    assigned_fields: set[str] = theme_create_request.model_fields_set
    frame_values: dict[str, object] = {}

    for field_name in _CREATE_FRAME_FIELDS:

        if field_name not in assigned_fields:
            continue

        frame_values[field_name] = getattr(theme_create_request, field_name)

    if len(frame_values) == 0:

        return None

    frame_patch: ThemePatchRequest = ThemePatchRequest.model_validate(frame_values)

    return frame_patch


def _attach_create_elements(
    created_theme: Theme,
    prepared_elements: list[tuple[ThemeElementCreateRequest, ResolvedThemeElement]],
    our_database_session: Session,
) -> None:
    """Append create-body elements. A slug clash on flush is HTTP 409."""

    from app.api.v1.theme_elements import attach_prepared_theme_elements

    if len(prepared_elements) == 0:

        return

    try:
        attach_prepared_theme_elements(
            created_theme,
            prepared_elements,
            our_database_session,
        )
    except IntegrityError as integrity_error:
        our_database_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Theme slug or template already exists.",
        ) from integrity_error


def _apply_theme_patch(theme: Theme, theme_patch_request: ThemePatchRequest) -> None:
    """Write only the patch fields the client sent.

    Args:
        theme: Loaded theme row.
        theme_patch_request: Partial body. Absent fields are left alone.

    Raises:
        HTTPException: 400 when a present status or spacing value is null,
            or when a spacing value is negative.
    """

    assigned_fields: set[str] = theme_patch_request.model_fields_set
    status_to_store: ThemeStatus | None = _status_to_store(
        theme_patch_request.status,
        "status" in assigned_fields,
    )
    page_margin_to_store: int | None = _spacing_to_store(
        "page_margin",
        theme_patch_request.page_margin,
        "page_margin" in assigned_fields,
    )
    element_gap_to_store: int | None = _spacing_to_store(
        "element_gap",
        theme_patch_request.element_gap,
        "element_gap" in assigned_fields,
    )
    element_margin_to_store: int | None = _spacing_to_store(
        "element_margin",
        theme_patch_request.element_margin,
        "element_margin" in assigned_fields,
    )
    resulting_status: ThemeStatus = theme.status

    if status_to_store is not None:
        resulting_status = status_to_store

    resolved_background: ResolvedThemeBackground = _resolved_background(
        theme,
        theme_patch_request,
        assigned_fields,
        resulting_status,
    )

    if status_to_store is not None:
        theme.status = status_to_store

    if page_margin_to_store is not None:
        theme.page_margin = page_margin_to_store

    if element_gap_to_store is not None:
        theme.element_gap = element_gap_to_store

    if element_margin_to_store is not None:
        theme.element_margin = element_margin_to_store

    if "background_kind" in assigned_fields:
        theme.background_kind = resolved_background.background_kind

    if "background_color" in assigned_fields:
        theme.background_color = resolved_background.background_color

    if "background_gradient" in assigned_fields:
        theme.background_gradient = resolved_background.background_gradient

    if "background_asset_ref" in assigned_fields:
        theme.background_asset_ref = resolved_background.background_asset_ref


def _resolved_background(
    theme: Theme,
    theme_patch_request: ThemePatchRequest,
    assigned_fields: set[str],
    resulting_status: ThemeStatus,
) -> ResolvedThemeBackground:
    """Resolve background fields and reject a Live row with an empty payload.

    Args:
        theme: Loaded theme row.
        theme_patch_request: Partial body.
        assigned_fields: Fields the client included.
        resulting_status: Status after this same patch.

    Returns:
        Kind and payloads, including fields the client left alone.

    Raises:
        HTTPException: 400 when a background value is invalid or Live is
            missing the payload for its kind.
    """

    try:
        resolved_background: ResolvedThemeBackground = resolve_patched_background(
            theme.background_kind,
            theme.background_color,
            theme.background_gradient,
            theme.background_asset_ref,
            "background_kind" in assigned_fields,
            theme_patch_request.background_kind,
            "background_color" in assigned_fields,
            theme_patch_request.background_color,
            "background_gradient" in assigned_fields,
            theme_patch_request.background_gradient,
            "background_asset_ref" in assigned_fields,
            theme_patch_request.background_asset_ref,
            resulting_status,
        )
    except ThemeBackgroundError as background_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=background_error.detail,
        ) from background_error

    return resolved_background


def _status_to_store(
    patched_status: ThemeStatus | None,
    status_is_set: bool,
) -> ThemeStatus | None:
    """Return a status to write, or None when the client omitted it.

    Args:
        patched_status: Status from the body, or None when omitted or null.
        status_is_set: True when the client included ``status``.

    Returns:
        The status to store, or None when the field was omitted.

    Raises:
        HTTPException: 400 when ``status`` is present and null.
    """

    if not status_is_set:

        return None

    if patched_status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=THEME_STATUS_REQUIRED_DETAIL,
        )

    return patched_status


def _spacing_to_store(
    field_name: str,
    spacing_value: int | None,
    spacing_is_set: bool,
) -> int | None:
    """Return a spacing integer to write, or None when the client omitted it.

    Args:
        field_name: API field name used in the 400 detail.
        spacing_value: Integer from the body, or None when omitted or null.
        spacing_is_set: True when the client included this field.

    Returns:
        The integer to store, including zero, or None when omitted.

    Raises:
        HTTPException: 400 when the field is null or negative.
    """

    if not spacing_is_set:

        return None

    if spacing_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=theme_spacing_required_detail(field_name),
        )

    if spacing_value < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=theme_spacing_negative_detail(field_name),
        )

    return spacing_value


def _normalize_template_key(template_key: str | None) -> str | None:
    """Return a known carousel template id, or None when omitted.

    Args:
        template_key: Optional generator id from the create body.

    Returns:
        Stripped template id, or None when blank.

    Raises:
        HTTPException: 400 when the id is not in the carousel registry.
    """

    if template_key is None:

        return None

    stripped_template_key: str = template_key.strip()

    if stripped_template_key == "":

        return None

    if stripped_template_key not in CAROUSEL_TEMPLATES_BY_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{UNKNOWN_TEMPLATE_KEY_DETAIL} {stripped_template_key}.",
        )

    return stripped_template_key


def _copy_theme_element(
    theme_id: uuid.UUID,
    source_element: ThemeElement,
) -> ThemeElement:
    """Return a new element with the same band, order, and content.

    Args:
        theme_id: Primary key of the new Draft theme.
        source_element: Element on the theme being copied.

    Returns:
        An element with a new id. The source row is not modified.
    """

    copied_element: ThemeElement = ThemeElement(
        theme_id=theme_id,
        band=source_element.band,
        sort_order=source_element.sort_order,
        content_kind=source_element.content_kind,
        rectangle_color=source_element.rectangle_color,
        rectangle_opacity=rectangle_opacity_value(source_element.rectangle_opacity),
        rectangle_radius=rectangle_radius_value(source_element.rectangle_radius),
        text_source=source_element.text_source,
        font_family=source_element.font_family,
        font_size=source_element.font_size,
        font_color=source_element.font_color,
        bold=source_element.bold,
        italic=source_element.italic,
        underline=source_element.underline,
        strikethrough=source_element.strikethrough,
        font_weight=source_element.font_weight,
        alignment=source_element.alignment,
        image_asset_ref=source_element.image_asset_ref,
    )

    return copied_element


def _load_taken_theme_slugs(our_database_session: Session) -> set[str]:
    """Return every existing theme slug."""

    slug_selection = select(Theme.slug)
    slug_scalars = our_database_session.scalars(slug_selection)
    taken_slugs: set[str] = set(slug_scalars.all())

    return taken_slugs


from app.api.v1.theme_elements import register_theme_element_routes
from app.api.v1.theme_samples import register_theme_sample_routes


register_theme_element_routes(themes_router)
register_theme_sample_routes(themes_router)
