"""In-carousel preview fills the skeleton from the slide and writes no file."""

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

from app.api.v1.schemas import CarouselCreateRequest, SlideElementTextWrite, SlidePreviewRequest
from app.api.v1.carousel_preview import preview_slide_on_skeleton
from app.api.v1.carousel_writes import create_carousel
from app.models.enums import (
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
)
from app.models.skeleton import DEFAULT_BACKGROUND_COLOR
from app.models.skeleton_element import SkeletonElement
from app.carousels.slide_skeleton import SlideSkeletonFill
from app.skeletons.layout import SKELETON_FRAME_HEIGHT_PIXELS, SKELETON_FRAME_WIDTH_PIXELS
from app.skeletons.samples import render_skeleton_sample
from tests.test_carousel_writes import _MemoryCarouselSession


CREATED_AT: datetime = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


class SlideSkeletonPreviewTests(unittest.TestCase):
    """The slide frame is a PNG. The preview route stores nothing."""

    def test_slide_fill_changes_the_png_and_ignores_the_source_item(self) -> None:
        """Two text values draw different frames. No source item is required."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_color = DEFAULT_BACKGROUND_COLOR
        text_element: SkeletonElement = _text_element(session)
        session.skeleton.elements = [text_element]
        storage: Path = Path(tempfile.mkdtemp(prefix="twerva-slide-preview-"))
        first_fill: SlideSkeletonFill = SlideSkeletonFill(
            text_by_element_id={text_element.id: "Harbor"},
            slide_image_relative_path=None,
        )
        second_fill: SlideSkeletonFill = SlideSkeletonFill(
            text_by_element_id={text_element.id: "Desert"},
            slide_image_relative_path=None,
        )

        first_render = render_skeleton_sample(session.skeleton, None, storage, first_fill)
        second_render = render_skeleton_sample(session.skeleton, None, storage, second_fill)
        first_image: Image.Image = Image.open(io.BytesIO(first_render.png_bytes))

        self.assertFalse(first_render.blocked)
        self.assertEqual(first_image.size, (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
        self.assertNotEqual(first_render.png_bytes, second_render.png_bytes)
        self.assertEqual(list(storage.iterdir()), [])

    def test_preview_route_returns_png_bytes_and_writes_no_file(self) -> None:
        """POST preview streams a frame and leaves the storage directory empty."""

        session: _MemoryCarouselSession = _MemoryCarouselSession()
        session.skeleton.background_color = DEFAULT_BACKGROUND_COLOR
        text_element: SkeletonElement = _text_element(session)
        session.skeleton.elements = [text_element]
        created = create_carousel(
            CarouselCreateRequest(name="Harbor shelf", skeleton_id=session.skeleton.id),
            session,
            None,
        )
        storage: Path = Path(tempfile.mkdtemp(prefix="twerva-slide-preview-"))
        preview_request: SlidePreviewRequest = SlidePreviewRequest(
            texts=[
                SlideElementTextWrite(
                    skeleton_element_id=text_element.id,
                    value="Fog on the water",
                ),
            ],
            slide_id=None,
        )

        with patch("app.api.v1.carousel_preview.get_settings") as settings:
            settings.return_value.artifact_storage_dir = str(storage)
            response = preview_slide_on_skeleton(
                created.id,
                preview_request,
                cast(Session, session),
                None,
            )

        image_bytes: bytes = base64.b64decode(response.image_png_base64)
        image: Image.Image = Image.open(io.BytesIO(image_bytes))

        self.assertFalse(response.blocked)
        self.assertTrue(image_bytes.startswith(b"\x89PNG"))
        self.assertEqual(image.size, (SKELETON_FRAME_WIDTH_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS))
        self.assertEqual(list(storage.iterdir()), [])
        self.assertEqual(len(list(created.slides)), 0)


def _text_element(session: _MemoryCarouselSession) -> SkeletonElement:
    """One title element on the memory skeleton."""

    text_element: SkeletonElement = SkeletonElement(
        id=uuid.uuid4(),
        skeleton_id=session.skeleton.id,
        band=SkeletonElementBand.TOP,
        sort_order=0,
        content_kind=SkeletonElementContentKind.TEXT,
        name="Title",
        rectangle_color=None,
        rectangle_opacity=100,
        rectangle_radius=0,
        text_source=SkeletonElementTextSource.TITLE,
        font_family="DejaVu Sans",
        font_size=64,
        font_color="#112233",
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        font_weight=None,
        alignment=SkeletonElementAlignment.LEFT,
        image_asset_ref=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    return text_element
