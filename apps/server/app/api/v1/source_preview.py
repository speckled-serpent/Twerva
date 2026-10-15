"""Render one unit on its source theme. No artifact row is written."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.lookups import (
    fetch_content_source_by_id_or_raise,
    fetch_theme_by_id_or_raise,
)
from app.api.v1.schemas import ThemePreviewResponse, UnitPreviewRequest
from app.api.v1.source_writes import _fetch_unit_or_raise, _parsed_texts
from app.api.v1.theme_samples import _preview_response
from app.auth.dependencies import require_authenticated_ops_operator
from app.db import get_our_database_session
from app.models.content_source import ContentSource, Unit, UnitImage
from app.models.ops_user import OpsUser
from app.models.theme import Theme
from app.settings import get_settings
from app.sources.unit_theme import UnitThemeFill, theme_requires_image
from app.themes.samples import ThemeSampleRender, render_theme_sample


def register_source_preview_routes(sources_router: APIRouter) -> None:
    """Attach the in-source preview route.

    Args:
        sources_router: Router mounted at ``/sources``.
    """

    sources_router.add_api_route(
        "/{source_id}/units/preview",
        preview_unit_on_theme,
        methods=["POST"],
        response_model=ThemePreviewResponse,
        status_code=status.HTTP_200_OK,
    )


def preview_unit_on_theme(
    source_id: uuid.UUID,
    preview_request: UnitPreviewRequest,
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_authenticated_ops_operator),
) -> ThemePreviewResponse:
    """Draw the source theme with this unit's text and image.

    Readers may call this. The PNG is inline. No unit, artifact, post
    job, or preview file is written.
    """

    _ = current_ops_operator
    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )
    found_theme: Theme = fetch_theme_by_id_or_raise(
        found_source.theme_id,
        our_database_session,
    )
    stored_texts: list[tuple[uuid.UUID, str]] = _parsed_texts(
        found_theme,
        preview_request.texts,
    )
    image_path: str | None = _saved_image_path(
        source_id,
        preview_request.unit_id,
        our_database_session,
        theme_requires_image(found_theme),
    )
    unit_fill: UnitThemeFill = UnitThemeFill(
        text_by_element_id={
            element_id: value for element_id, value in stored_texts
        },
        unit_image_relative_path=image_path,
    )
    artifact_storage_directory: Path = Path(get_settings().artifact_storage_dir)
    rendered_sample: ThemeSampleRender = render_theme_sample(
        found_theme,
        None,
        artifact_storage_directory,
        unit_fill,
    )
    preview_response: ThemePreviewResponse = _preview_response(rendered_sample)

    return preview_response


def _saved_image_path(
    source_id: uuid.UUID,
    unit_id: uuid.UUID | None,
    our_database_session: Session,
    theme_needs_image: bool,
) -> str | None:
    """Return the unit's stored image path when the theme uses one."""

    if not theme_needs_image or unit_id is None:

        return None

    found_unit: Unit = _fetch_unit_or_raise(source_id, unit_id, our_database_session)
    images: list[UnitImage] = list(found_unit.images)

    if len(images) == 0:

        return None

    image_path: str = images[0].relative_path

    return image_path
