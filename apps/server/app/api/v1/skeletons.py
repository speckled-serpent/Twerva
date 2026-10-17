"""Skeleton create/list/get/patch/duplicate. Samples render one preview frame."""

from __future__ import annotations

import copy
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_skeleton_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import (
    SkeletonCreateRequest,
    SkeletonDefaultImagesResponse,
    SkeletonElementCreateRequest,
    SkeletonElementReadResponse,
    SkeletonFontFamiliesResponse,
    SkeletonFontFamilyResponse,
    SkeletonImageAlbumResponse,
    SkeletonPatchRequest,
    SkeletonReadResponse,
)
from app.auth.dependencies import require_authenticated_ops_operator
from app.db import get_our_database_session
from app.generate.templates import CAROUSEL_TEMPLATES_BY_ID
from app.models import (
    AdvertisementType,
    BackgroundKind,
    Campaign,
    OpsUser,
    Carousel,
    Skeleton,
    SkeletonElement,
    SkeletonStatus,
)
from app.models.base import Base
from app.models.skeleton import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
)
from app.skeletons.background import (
    ResolvedSkeletonBackground,
    SkeletonBackgroundError,
    resolve_patched_background,
)
from app.skeletons.bundled_fonts import (
    FALLBACK_FONT_FAMILY_NAME,
    list_bundled_font_families,
)
from app.skeletons.default_images import list_skeleton_image_albums
from app.skeletons.elements import (
    ResolvedSkeletonElement,
    ordered_skeleton_elements,
    rectangle_opacity_value,
    rectangle_radius_value,
)
from app.skeletons.slug import allocate_unique_skeleton_slug, slugify_skeleton_name


SKELETON_NAME_REQUIRED_DETAIL: str = "Skeleton name is required."
SKELETON_STATUS_REQUIRED_DETAIL: str = "Skeleton status is required."
UNKNOWN_TEMPLATE_KEY_DETAIL: str = "Unknown carousel template."
DUPLICATE_SKELETON_NAME_PREFIX: str = "Copy of "
SKELETON_DELETE_CONFLICT_DETAIL: str = "Skeleton could not be deleted (conflict)."
SKELETON_DELETE_REFERENCED_DETAIL: str = (
    "Skeleton is still referenced and was not deleted."
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

skeletons_router: APIRouter = APIRouter(prefix="/skeletons", tags=["skeletons"])


@skeletons_router.post(
    "",
    response_model=SkeletonReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_skeleton(
    skeleton_create_request: SkeletonCreateRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> SkeletonReadResponse:
    """Persist a carousel skeleton and its elements in one write.

    Omitted frame fields keep the defaults. A validation error commits
    nothing. Does not render or bind a campaign.
    """

    if skeleton_create_request.advertisement_type != AdvertisementType.CAROUSEL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only carousel skeletons are implemented.",
        )

    stripped_name: str = skeleton_create_request.name.strip()

    if stripped_name == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SKELETON_NAME_REQUIRED_DETAIL,
        )

    template_key: str | None = _normalize_template_key(
        skeleton_create_request.template_key,
    )
    requested_slug: str = slugify_skeleton_name(stripped_name)
    taken_slugs: set[str] = _load_taken_skeleton_slugs(our_database_session)
    skeleton_slug: str = allocate_unique_skeleton_slug(requested_slug, taken_slugs)
    created_by: uuid.UUID | None = (
        None if current_ops_operator is None else current_ops_operator.id
    )
    created_skeleton: Skeleton = Skeleton(
        name=stripped_name,
        slug=skeleton_slug,
        advertisement_type=skeleton_create_request.advertisement_type,
        template_key=template_key,
        status=SkeletonStatus.DRAFT,
        page_margin=DEFAULT_PAGE_MARGIN,
        element_gap=DEFAULT_ELEMENT_GAP,
        element_margin=DEFAULT_ELEMENT_MARGIN,
        background_kind=BackgroundKind.COLOR,
        background_color=DEFAULT_BACKGROUND_COLOR,
        background_gradient=None,
        background_asset_ref=None,
        created_by=created_by,
    )
    from app.api.v1.skeleton_elements import prepare_new_skeleton_elements

    prepared_elements = prepare_new_skeleton_elements(skeleton_create_request.elements)
    frame_patch: SkeletonPatchRequest | None = _frame_patch_for_create(skeleton_create_request)

    if frame_patch is not None:
        _apply_skeleton_patch(created_skeleton, frame_patch)

    our_database_session.add(created_skeleton)
    _attach_create_elements(
        created_skeleton,
        prepared_elements,
        our_database_session,
    )
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Skeleton slug or template already exists.",
    )
    our_database_session.refresh(created_skeleton)

    for created_element in list(created_skeleton.elements):
        our_database_session.refresh(created_element)

    skeleton_read_response: SkeletonReadResponse = serialize_skeleton(created_skeleton)

    return skeleton_read_response


@skeletons_router.get("", response_model=list[SkeletonReadResponse])
def list_skeletons(
    our_database_session: Session = Depends(get_our_database_session),
) -> list[SkeletonReadResponse]:
    """Return every Skeleton, newest first."""

    skeleton_selection = select(Skeleton).order_by(
        Skeleton.created_at.desc(),
        Skeleton.name.asc(),
    )
    skeleton_scalars = our_database_session.scalars(skeleton_selection)
    skeletons: list[Skeleton] = list(skeleton_scalars.all())
    skeleton_read_responses: list[SkeletonReadResponse] = [
        serialize_skeleton(skeleton) for skeleton in skeletons
    ]

    return skeleton_read_responses


@skeletons_router.get("/default-images", response_model=SkeletonDefaultImagesResponse)
def list_skeleton_default_images() -> SkeletonDefaultImagesResponse:
    """Return bundled image albums. Readers may call this, same as preview.

    Registered before ``/{skeleton_id}`` so ``default-images`` is not parsed
    as a skeleton id.
    """

    album_responses: list[SkeletonImageAlbumResponse] = [
        SkeletonImageAlbumResponse(
            album_id=album.album_id,
            name=album.name,
            asset_refs=list(album.asset_refs),
        )
        for album in list_skeleton_image_albums()
    ]
    images_response: SkeletonDefaultImagesResponse = SkeletonDefaultImagesResponse(
        albums=album_responses,
    )

    return images_response


@skeletons_router.get("/font-families", response_model=SkeletonFontFamiliesResponse)
def list_skeleton_font_families() -> SkeletonFontFamiliesResponse:
    """Return bundled font families. Readers may call this, same as preview.

    Registered before ``/{skeleton_id}`` so ``font-families`` is not parsed
    as a skeleton id.
    """

    family_responses: list[SkeletonFontFamilyResponse] = [
        SkeletonFontFamilyResponse(
            family_id=family.family_id,
            name=family.name,
            category=family.category,
        )
        for family in list_bundled_font_families()
    ]
    fonts_response: SkeletonFontFamiliesResponse = SkeletonFontFamiliesResponse(
        families=family_responses,
        fallback_name=FALLBACK_FONT_FAMILY_NAME,
    )

    return fonts_response


@skeletons_router.get("/{skeleton_id}", response_model=SkeletonReadResponse)
def get_skeleton_by_id(
    skeleton_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> SkeletonReadResponse:
    """Return one Skeleton by primary key."""

    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(skeleton_id, our_database_session)
    skeleton_read_response: SkeletonReadResponse = serialize_skeleton(found_skeleton)

    return skeleton_read_response


@skeletons_router.delete(
    "/{skeleton_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_skeleton_by_id(
    skeleton_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> None:
    """Delete one skeleton and its elements.

    ``skeleton_elements`` uses ``ON DELETE CASCADE``. A carousel that stores
    this skeleton blocks the delete. Any other table that references
    ``skeletons`` blocks it too. Preview files on disk are not rows and are
    left in place. ``template_key`` is a column on this row, not a
    foreign key from campaigns or artifacts.
    """

    _ = current_ops_operator
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(skeleton_id, our_database_session)
    reference_blockers: list[str] = skeleton_delete_reference_blockers(
        our_database_session,
        found_skeleton.id,
    )

    if len(reference_blockers) > 0:
        blocker_names: str = ", ".join(reference_blockers)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{SKELETON_DELETE_REFERENCED_DETAIL} Referenced by {blocker_names}.",
        )

    our_database_session.delete(found_skeleton)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail=SKELETON_DELETE_CONFLICT_DETAIL,
    )


@skeletons_router.patch("/{skeleton_id}", response_model=SkeletonReadResponse)
def patch_skeleton_by_id(
    skeleton_id: uuid.UUID,
    skeleton_patch_request: SkeletonPatchRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> SkeletonReadResponse:
    """Patch fields that are present. Status may move draft ↔ live."""

    _ = current_ops_operator
    found_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(skeleton_id, our_database_session)
    _apply_skeleton_patch(found_skeleton, skeleton_patch_request)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Skeleton could not be updated (conflict).",
    )
    our_database_session.refresh(found_skeleton)
    skeleton_read_response: SkeletonReadResponse = serialize_skeleton(found_skeleton)

    return skeleton_read_response


@skeletons_router.post(
    "/{skeleton_id}/duplicate",
    response_model=SkeletonReadResponse,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_skeleton_by_id(
    skeleton_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> SkeletonReadResponse:
    """Copy one skeleton into a new Draft. The carousel row stays as it was."""

    source_skeleton: Skeleton = fetch_skeleton_by_id_or_raise(skeleton_id, our_database_session)
    copied_name: str = f"{DUPLICATE_SKELETON_NAME_PREFIX}{source_skeleton.name}"
    requested_slug: str = slugify_skeleton_name(copied_name)
    taken_slugs: set[str] = _load_taken_skeleton_slugs(our_database_session)
    copied_slug: str = allocate_unique_skeleton_slug(requested_slug, taken_slugs)
    created_by: uuid.UUID | None = (
        None if current_ops_operator is None else current_ops_operator.id
    )
    copied_gradient: dict[str, object] | None = copy.deepcopy(
        source_skeleton.background_gradient,
    )
    copied_skeleton: Skeleton = Skeleton(
        name=copied_name,
        slug=copied_slug,
        advertisement_type=source_skeleton.advertisement_type,
        template_key=None,
        status=SkeletonStatus.DRAFT,
        page_margin=source_skeleton.page_margin,
        element_gap=source_skeleton.element_gap,
        element_margin=source_skeleton.element_margin,
        background_kind=source_skeleton.background_kind,
        background_color=source_skeleton.background_color,
        background_gradient=copied_gradient,
        background_asset_ref=source_skeleton.background_asset_ref,
        created_by=created_by,
    )
    our_database_session.add(copied_skeleton)
    our_database_session.flush()

    for source_element in ordered_skeleton_elements(source_skeleton.elements):
        copied_element: SkeletonElement = _copy_skeleton_element(
            copied_skeleton.id,
            source_element,
        )
        copied_skeleton.elements.append(copied_element)
        our_database_session.add(copied_element)

    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Skeleton slug or template already exists.",
    )
    our_database_session.refresh(copied_skeleton)

    for copied_element in copied_skeleton.elements:
        our_database_session.refresh(copied_element)

    skeleton_read_response: SkeletonReadResponse = serialize_skeleton(copied_skeleton)

    return skeleton_read_response


def serialize_skeleton(skeleton: Skeleton) -> SkeletonReadResponse:
    """Map a Skeleton row to the read schema.

    Args:
        skeleton: Loaded skeleton.

    Returns:
        API response including slug, status, spacing, and template key.
    """

    skeleton_read_response: SkeletonReadResponse = SkeletonReadResponse(
        id=skeleton.id,
        name=skeleton.name,
        slug=skeleton.slug,
        advertisement_type=skeleton.advertisement_type,
        template_key=skeleton.template_key,
        status=skeleton.status,
        page_margin=skeleton.page_margin,
        element_gap=skeleton.element_gap,
        element_margin=skeleton.element_margin,
        background_kind=skeleton.background_kind,
        background_color=skeleton.background_color,
        background_gradient=skeleton.background_gradient,
        background_asset_ref=skeleton.background_asset_ref,
        elements=_serialized_skeleton_elements(skeleton),
        created_at=skeleton.created_at,
        updated_at=skeleton.updated_at,
        created_by=skeleton.created_by,
    )

    return skeleton_read_response


def _serialized_skeleton_elements(skeleton: Skeleton) -> list[SkeletonElementReadResponse]:
    """Return elements ordered by band, then sort_order."""

    from app.api.v1.skeleton_elements import serialize_skeleton_element

    element_read_responses: list[SkeletonElementReadResponse] = [
        serialize_skeleton_element(element)
        for element in ordered_skeleton_elements(skeleton.elements)
    ]

    return element_read_responses


def skeleton_spacing_required_detail(field_name: str) -> str:
    """Return the 400 detail for an explicit null spacing field."""

    required_detail: str = f"{field_name} is required."

    return required_detail


def skeleton_spacing_negative_detail(field_name: str) -> str:
    """Return the 400 detail for a negative spacing value."""

    negative_detail: str = f"{field_name} must be zero or greater."

    return negative_detail


def skeleton_delete_reference_blockers(
    our_database_session: Session,
    skeleton_id: uuid.UUID,
) -> list[str]:
    """Return tables that still make deleting this skeleton unsafe.

    ``skeleton_elements`` cascade with the skeleton. ``carousels`` and
    ``campaigns`` block only when a row stores this skeleton. Any other
    foreign key to ``skeletons`` blocks the delete, because that table
    is not counted row by row.

    Returns:
        Sorted table names that would make a silent delete unsafe.
    """

    blocker_names: list[str] = unexpected_skeleton_reference_tables()
    source_count: int = _source_count_for_skeleton(our_database_session, skeleton_id)
    campaign_count: int = _campaign_count_for_skeleton(our_database_session, skeleton_id)

    if source_count > 0:
        blocker_names.append("carousels")

    if campaign_count > 0:
        blocker_names.append("campaigns")

    unique_blockers: list[str] = sorted(set(blocker_names))

    return unique_blockers


def unexpected_skeleton_reference_tables() -> list[str]:
    """Return tables other than elements and carousels that point at skeletons.

    Returns:
        Sorted table names. An empty list means only the known references.
    """

    blocker_names: list[str] = []

    for table in Base.metadata.tables.values():

        for foreign_key in table.foreign_keys:

            if foreign_key.column.table.name != "skeletons":
                continue

            if table.name in {"skeleton_elements", "carousels", "campaigns"}:
                continue

            blocker_names.append(table.name)

    unique_blockers: list[str] = sorted(set(blocker_names))

    return unique_blockers


def _source_count_for_skeleton(
    our_database_session: Session,
    skeleton_id: uuid.UUID,
) -> int:
    """Count carousels that store this skeleton."""

    counted: int | None = our_database_session.scalar(
        select(func.count())
        .select_from(Carousel)
        .where(Carousel.skeleton_id == skeleton_id),
    )

    if counted is None:
        return 0

    source_count: int = int(counted)

    return source_count


def _campaign_count_for_skeleton(
    our_database_session: Session,
    skeleton_id: uuid.UUID,
) -> int:
    """Count campaigns that store this skeleton."""

    counted: int | None = our_database_session.scalar(
        select(func.count())
        .select_from(Campaign)
        .where(Campaign.skeleton_id == skeleton_id),
    )

    if counted is None:
        return 0

    campaign_count: int = int(counted)

    return campaign_count


def _frame_patch_for_create(
    skeleton_create_request: SkeletonCreateRequest,
) -> SkeletonPatchRequest | None:
    """Return a patch for the frame fields the create body included."""

    assigned_fields: set[str] = skeleton_create_request.model_fields_set
    frame_values: dict[str, object] = {}

    for field_name in _CREATE_FRAME_FIELDS:

        if field_name not in assigned_fields:
            continue

        frame_values[field_name] = getattr(skeleton_create_request, field_name)

    if len(frame_values) == 0:

        return None

    frame_patch: SkeletonPatchRequest = SkeletonPatchRequest.model_validate(frame_values)

    return frame_patch


def _attach_create_elements(
    created_skeleton: Skeleton,
    prepared_elements: list[tuple[SkeletonElementCreateRequest, ResolvedSkeletonElement]],
    our_database_session: Session,
) -> None:
    """Append create-body elements. A slug clash on flush is HTTP 409."""

    from app.api.v1.skeleton_elements import attach_prepared_skeleton_elements

    if len(prepared_elements) == 0:

        return

    try:
        attach_prepared_skeleton_elements(
            created_skeleton,
            prepared_elements,
            our_database_session,
        )
    except IntegrityError as integrity_error:
        our_database_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Skeleton slug or template already exists.",
        ) from integrity_error


def _apply_skeleton_patch(skeleton: Skeleton, skeleton_patch_request: SkeletonPatchRequest) -> None:
    """Write only the patch fields the client sent.

    Args:
        skeleton: Loaded skeleton row.
        skeleton_patch_request: Partial body. Absent fields are left alone.

    Raises:
        HTTPException: 400 when a present status or spacing value is null,
            or when a spacing value is negative.
    """

    assigned_fields: set[str] = skeleton_patch_request.model_fields_set
    status_to_store: SkeletonStatus | None = _status_to_store(
        skeleton_patch_request.status,
        "status" in assigned_fields,
    )
    page_margin_to_store: int | None = _spacing_to_store(
        "page_margin",
        skeleton_patch_request.page_margin,
        "page_margin" in assigned_fields,
    )
    element_gap_to_store: int | None = _spacing_to_store(
        "element_gap",
        skeleton_patch_request.element_gap,
        "element_gap" in assigned_fields,
    )
    element_margin_to_store: int | None = _spacing_to_store(
        "element_margin",
        skeleton_patch_request.element_margin,
        "element_margin" in assigned_fields,
    )
    resulting_status: SkeletonStatus = skeleton.status

    if status_to_store is not None:
        resulting_status = status_to_store

    resolved_background: ResolvedSkeletonBackground = _resolved_background(
        skeleton,
        skeleton_patch_request,
        assigned_fields,
        resulting_status,
    )

    if status_to_store is not None:
        skeleton.status = status_to_store

    if page_margin_to_store is not None:
        skeleton.page_margin = page_margin_to_store

    if element_gap_to_store is not None:
        skeleton.element_gap = element_gap_to_store

    if element_margin_to_store is not None:
        skeleton.element_margin = element_margin_to_store

    if "background_kind" in assigned_fields:
        skeleton.background_kind = resolved_background.background_kind

    if "background_color" in assigned_fields:
        skeleton.background_color = resolved_background.background_color

    if "background_gradient" in assigned_fields:
        skeleton.background_gradient = resolved_background.background_gradient

    if "background_asset_ref" in assigned_fields:
        skeleton.background_asset_ref = resolved_background.background_asset_ref


def _resolved_background(
    skeleton: Skeleton,
    skeleton_patch_request: SkeletonPatchRequest,
    assigned_fields: set[str],
    resulting_status: SkeletonStatus,
) -> ResolvedSkeletonBackground:
    """Resolve background fields and reject a Live row with an empty payload.

    Args:
        skeleton: Loaded skeleton row.
        skeleton_patch_request: Partial body.
        assigned_fields: Fields the client included.
        resulting_status: Status after this same patch.

    Returns:
        Kind and payloads, including fields the client left alone.

    Raises:
        HTTPException: 400 when a background value is invalid or Live is
            missing the payload for its kind.
    """

    try:
        resolved_background: ResolvedSkeletonBackground = resolve_patched_background(
            skeleton.background_kind,
            skeleton.background_color,
            skeleton.background_gradient,
            skeleton.background_asset_ref,
            "background_kind" in assigned_fields,
            skeleton_patch_request.background_kind,
            "background_color" in assigned_fields,
            skeleton_patch_request.background_color,
            "background_gradient" in assigned_fields,
            skeleton_patch_request.background_gradient,
            "background_asset_ref" in assigned_fields,
            skeleton_patch_request.background_asset_ref,
            resulting_status,
        )
    except SkeletonBackgroundError as background_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=background_error.detail,
        ) from background_error

    return resolved_background


def _status_to_store(
    patched_status: SkeletonStatus | None,
    status_is_set: bool,
) -> SkeletonStatus | None:
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
            detail=SKELETON_STATUS_REQUIRED_DETAIL,
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
            detail=skeleton_spacing_required_detail(field_name),
        )

    if spacing_value < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=skeleton_spacing_negative_detail(field_name),
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


def _copy_skeleton_element(
    skeleton_id: uuid.UUID,
    source_element: SkeletonElement,
) -> SkeletonElement:
    """Return a new element with the same band, order, and content.

    Args:
        skeleton_id: Primary key of the new Draft skeleton.
        source_element: Element on the skeleton being copied.

    Returns:
        An element with a new id. The carousel row is not modified.
    """

    copied_element: SkeletonElement = SkeletonElement(
        skeleton_id=skeleton_id,
        band=source_element.band,
        sort_order=source_element.sort_order,
        content_kind=source_element.content_kind,
        name=source_element.name,
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


def _load_taken_skeleton_slugs(our_database_session: Session) -> set[str]:
    """Return every existing skeleton slug."""

    slug_selection = select(Skeleton.slug)
    slug_scalars = our_database_session.scalars(slug_selection)
    taken_slugs: set[str] = set(slug_scalars.all())

    return taken_slugs


from app.api.v1.skeleton_elements import register_skeleton_element_routes
from app.api.v1.skeleton_samples import register_skeleton_sample_routes


register_skeleton_element_routes(skeletons_router)
register_skeleton_sample_routes(skeletons_router)
