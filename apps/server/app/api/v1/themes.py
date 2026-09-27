"""Theme create/list/get. Carousel only; no render or campaign binding."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.lookups import fetch_theme_by_id_or_raise
from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import ThemeCreateRequest, ThemeReadResponse
from app.auth.dependencies import require_authenticated_ops_operator
from app.db import get_our_database_session
from app.generate.templates import CAROUSEL_TEMPLATES_BY_ID
from app.models import AdvertisementType, OpsUser, Theme
from app.themes.slug import allocate_unique_theme_slug, slugify_theme_name


THEME_NAME_REQUIRED_DETAIL: str = "Theme name is required."
UNKNOWN_TEMPLATE_KEY_DETAIL: str = "Unknown carousel template."

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
    """Persist a carousel theme. Does not render or bind a campaign."""

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
        created_by=created_by,
    )
    our_database_session.add(created_theme)
    commit_database_session_or_raise_conflict(
        our_database_session,
        conflict_detail="Theme slug or template already exists.",
    )
    our_database_session.refresh(created_theme)
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


@themes_router.get("/{theme_id}", response_model=ThemeReadResponse)
def get_theme_by_id(
    theme_id: uuid.UUID,
    our_database_session: Session = Depends(get_our_database_session),
) -> ThemeReadResponse:
    """Return one Theme by primary key."""

    found_theme: Theme = fetch_theme_by_id_or_raise(theme_id, our_database_session)
    theme_read_response: ThemeReadResponse = serialize_theme(found_theme)

    return theme_read_response


def serialize_theme(theme: Theme) -> ThemeReadResponse:
    """Map a Theme row to the read schema.

    Args:
        theme: Loaded theme.

    Returns:
        API response including slug and optional template key.
    """

    theme_read_response: ThemeReadResponse = ThemeReadResponse(
        id=theme.id,
        name=theme.name,
        slug=theme.slug,
        advertisement_type=theme.advertisement_type,
        template_key=theme.template_key,
        created_at=theme.created_at,
        updated_at=theme.updated_at,
        created_by=theme.created_by,
    )

    return theme_read_response


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


def _load_taken_theme_slugs(our_database_session: Session) -> set[str]:
    """Return every existing theme slug."""

    slug_selection = select(Theme.slug)
    slug_scalars = our_database_session.scalars(slug_selection)
    taken_slugs: set[str] = set(slug_scalars.all())

    return taken_slugs
