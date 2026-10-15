"""In-source preview fills the theme from the unit and writes no file."""

import base64
import io
import os
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from PIL import Image
from sqlalchemy.orm import Session

from app.api.v1.schemas import SourceCreateRequest, UnitElementTextWrite, UnitPreviewRequest
from app.api.v1.source_preview import preview_unit_on_theme
from app.api.v1.source_writes import create_content_source
from app.models.enums import (
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
)
from app.models.theme import DEFAULT_BACKGROUND_COLOR
from app.models.theme_element import ThemeElement
from app.sources.unit_theme import UnitThemeFill
from app.themes.layout import THEME_FRAME_HEIGHT_PIXELS, THEME_FRAME_WIDTH_PIXELS
from app.themes.samples import render_theme_sample
from tests.test_source_writes import _MemorySourceSession


CREATED_AT: datetime = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


class UnitThemePreviewTests(unittest.TestCase):
    """The unit frame is a PNG. The preview route stores nothing."""

    def test_unit_fill_changes_the_png_and_ignores_the_source_item(self) -> None:
        """Two text values draw different frames. No source item is required."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.theme.background_color = DEFAULT_BACKGROUND_COLOR
        text_element: ThemeElement = _text_element(session)
        session.theme.elements = [text_element]
        storage: Path = Path(tempfile.mkdtemp(prefix="twerva-unit-preview-"))
        first_fill: UnitThemeFill = UnitThemeFill(
            text_by_element_id={text_element.id: "Harbor"},
            unit_image_relative_path=None,
        )
        second_fill: UnitThemeFill = UnitThemeFill(
            text_by_element_id={text_element.id: "Desert"},
            unit_image_relative_path=None,
        )

        first_render = render_theme_sample(session.theme, None, storage, first_fill)
        second_render = render_theme_sample(session.theme, None, storage, second_fill)
        first_image: Image.Image = Image.open(io.BytesIO(first_render.png_bytes))

        self.assertFalse(first_render.blocked)
        self.assertEqual(first_image.size, (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS))
        self.assertNotEqual(first_render.png_bytes, second_render.png_bytes)
        self.assertEqual(list(storage.iterdir()), [])

    def test_preview_route_returns_png_bytes_and_writes_no_file(self) -> None:
        """POST preview streams a frame and leaves the storage directory empty."""

        session: _MemorySourceSession = _MemorySourceSession()
        session.theme.background_color = DEFAULT_BACKGROUND_COLOR
        text_element: ThemeElement = _text_element(session)
        session.theme.elements = [text_element]
        created = create_content_source(
            SourceCreateRequest(name="Harbor shelf", theme_id=session.theme.id),
            session,
            None,
        )
        storage: Path = Path(tempfile.mkdtemp(prefix="twerva-unit-preview-"))
        preview_request: UnitPreviewRequest = UnitPreviewRequest(
            texts=[
                UnitElementTextWrite(
                    theme_element_id=text_element.id,
                    value="Fog on the water",
                ),
            ],
            unit_id=None,
        )

        with patch("app.api.v1.source_preview.get_settings") as settings:
            settings.return_value.artifact_storage_dir = str(storage)
            response = preview_unit_on_theme(
                created.id,
                preview_request,
                cast(Session, session),
                None,
            )

        image_bytes: bytes = base64.b64decode(response.image_png_base64)
        image: Image.Image = Image.open(io.BytesIO(image_bytes))

        self.assertFalse(response.blocked)
        self.assertTrue(image_bytes.startswith(b"\x89PNG"))
        self.assertEqual(image.size, (THEME_FRAME_WIDTH_PIXELS, THEME_FRAME_HEIGHT_PIXELS))
        self.assertEqual(list(storage.iterdir()), [])
        self.assertEqual(len(list(created.units)), 0)


def _text_element(session: _MemorySourceSession) -> ThemeElement:
    """One title element on the memory theme."""

    text_element: ThemeElement = ThemeElement(
        id=uuid.uuid4(),
        theme_id=session.theme.id,
        band=ThemeElementBand.TOP,
        sort_order=0,
        content_kind=ThemeElementContentKind.TEXT,
        name="Title",
        rectangle_color=None,
        rectangle_opacity=100,
        rectangle_radius=0,
        text_source=ThemeElementTextSource.TITLE,
        font_family="DejaVu Sans",
        font_size=64,
        font_color="#112233",
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        font_weight=None,
        alignment=ThemeElementAlignment.LEFT,
        image_asset_ref=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    return text_element
