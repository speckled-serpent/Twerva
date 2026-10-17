"""Carousel plan/render against a tmp directory (1.4c-iii). No database."""

from __future__ import annotations

import io
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from app.generate.carousel import (
    CANVAS_HEIGHT_PIXELS,
    CANVAS_WIDTH_PIXELS,
    SAFE_INSET_PIXELS,
    SLIDE_ROLE_BULLET,
    SLIDE_ROLE_COVER,
    SLIDE_ROLE_CTA,
    SLIDE_ROLE_HEADING,
    CarouselSourceFields,
    PlannedSlide,
    plan_carousel_slides,
    render_carousel_from_source_fields,
    render_carousel_slide_png_bytes,
    resolve_carousel_cta_url,
)
from app.generate.templates import resolve_carousel_template
from app.skeletons.layout import SKELETON_FRAME_HEIGHT_PIXELS, SKELETON_FRAME_WIDTH_PIXELS


PNG_MAGIC: bytes = b"\x89PNG"


class CarouselRenderTests(unittest.TestCase):
    """Fake carousel payload yields on-disk PNGs and a non-empty caption."""

    def test_canvas_is_the_skeleton_frame(self) -> None:
        """Shipping slides use the shared 1080×1920 frame, not a square."""

        self.assertEqual(CANVAS_WIDTH_PIXELS, SKELETON_FRAME_WIDTH_PIXELS)
        self.assertEqual(CANVAS_HEIGHT_PIXELS, SKELETON_FRAME_HEIGHT_PIXELS)
        self.assertEqual((CANVAS_WIDTH_PIXELS, CANVAS_HEIGHT_PIXELS), (1080, 1920))

    def test_cover_copy_sits_in_the_open_field(self) -> None:
        """A short cover title is optically centered between header and footer."""

        png_bytes: bytes = render_carousel_slide_png_bytes(
            PlannedSlide(role=SLIDE_ROLE_COVER, text="Harbor light"),
            0,
            1,
            resolve_carousel_template(None),
        )
        canvas_image: Image.Image = Image.open(io.BytesIO(png_bytes))
        rgb_image: Image.Image = canvas_image.convert("RGB")
        paper: tuple[int, int, int] = (0xF6, 0xF1, 0xE8)
        ink_rows: list[int] = []
        header_limit: int = 280
        footer_limit: int = CANVAS_HEIGHT_PIXELS - 220

        for pixel_y in range(header_limit, footer_limit):
            for pixel_x in range(160, CANVAS_WIDTH_PIXELS - 160):
                if rgb_image.getpixel((pixel_x, pixel_y)) != paper:
                    ink_rows.append(pixel_y)

                    break

        self.assertGreater(len(ink_rows), 0)
        copy_middle: int = (ink_rows[0] + ink_rows[-1]) // 2

        self.assertGreater(ink_rows[0], CANVAS_HEIGHT_PIXELS // 3)
        self.assertLess(ink_rows[-1], CANVAS_HEIGHT_PIXELS - (CANVAS_HEIGHT_PIXELS // 3))
        self.assertLess(copy_middle, CANVAS_HEIGHT_PIXELS // 2)
        self.assertGreater(copy_middle, int(CANVAS_HEIGHT_PIXELS * 0.38))
        canvas_image.close()

    def test_long_url_stays_inside_the_inset(self) -> None:
        """A CTA URL breaks instead of running past the side inset."""

        png_bytes: bytes = render_carousel_slide_png_bytes(
            PlannedSlide(
                role=SLIDE_ROLE_CTA,
                text="Read more on Spotmu\nhttps://spotmu.com/interest/harbor-light",
            ),
            0,
            1,
            resolve_carousel_template(None),
        )
        canvas_image: Image.Image = Image.open(io.BytesIO(png_bytes))
        rgb_image: Image.Image = canvas_image.convert("RGB")
        paper: tuple[int, int, int] = (0xF6, 0xF1, 0xE8)
        left_limit: int = SAFE_INSET_PIXELS - 2
        right_limit: int = CANVAS_WIDTH_PIXELS - SAFE_INSET_PIXELS + 2
        overflow_pixels: int = 0

        for pixel_y in range(CANVAS_HEIGHT_PIXELS):
            for pixel_x in range(CANVAS_WIDTH_PIXELS):

                if rgb_image.getpixel((pixel_x, pixel_y)) == paper:
                    continue

                if pixel_x < left_limit or pixel_x > right_limit:
                    overflow_pixels += 1

        self.assertEqual(overflow_pixels, 0)
        canvas_image.close()

    def test_render_from_fake_source_writes_at_least_three_pngs_and_caption(self) -> None:
        """1.4c-iii: ≥3 PNGs + caption from a typical Spotmu-shaped payload."""

        source_fields: CarouselSourceFields = CarouselSourceFields(
            title="Example Spotmu interest",
            interest_heading="What this example lane is about",
            overview_bullets=[
                "A placeholder interest heading for Twerva persist proof.",
                "Three overview bullets stand in for a real Spotmu interest.",
                "Replace this row when 1.3 ingest lands.",
            ],
            canonical_url="https://spotmu.com/interest/example",
            external_key="example",
        )
        artifact_identifier: uuid.UUID = uuid.uuid4()

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            render_result = render_carousel_from_source_fields(
                source_fields,
                artifact_identifier,
                storage_directory,
            )
            png_paths: list[Path] = sorted(storage_directory.glob("*/*.png"))

            self.assertGreaterEqual(len(png_paths), 3)
            self.assertGreaterEqual(len(render_result.slides), 3)
            self.assertTrue(render_result.caption.strip())
            self.assertIn("#spotmu", render_result.caption)
            self.assertEqual(
                render_result.cta_url,
                "https://spotmu.com/interest/example",
            )

            for png_path in png_paths:
                png_bytes: bytes = png_path.read_bytes()

                self.assertTrue(png_bytes.startswith(PNG_MAGIC))
                canvas_image: Image.Image = Image.open(png_path)
                self.assertEqual(canvas_image.size, (CANVAS_WIDTH_PIXELS, CANVAS_HEIGHT_PIXELS))
                canvas_image.close()

            first_slide_roles: list[str] = [
                rendered_slide.role for rendered_slide in render_result.slides
            ]

            self.assertEqual(first_slide_roles[0], SLIDE_ROLE_COVER)
            self.assertEqual(first_slide_roles[1], SLIDE_ROLE_HEADING)
            self.assertEqual(first_slide_roles[-1], SLIDE_ROLE_CTA)
            self.assertIn(SLIDE_ROLE_BULLET, first_slide_roles)

            for rendered_slide in render_result.slides:
                self.assertTrue(rendered_slide.asset_ref)
                stored_path: Path = storage_directory / rendered_slide.asset_ref

                self.assertTrue(stored_path.is_file())

    def test_empty_bullets_still_produce_cover_heading_and_cta(self) -> None:
        """No usable bullets → three frames, still a caption."""

        source_fields: CarouselSourceFields = CarouselSourceFields(
            title="Empty-bullet interest",
            interest_heading="Still needs a heading slide",
            overview_bullets=["", "   "],
            canonical_url=None,
            external_key="empty-bullets",
        )
        artifact_identifier: uuid.UUID = uuid.uuid4()

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            render_result = render_carousel_from_source_fields(
                source_fields,
                artifact_identifier,
                storage_directory,
            )
            planned_roles: list[str] = [
                planned_slide.role for planned_slide in plan_carousel_slides(source_fields)
            ]
            png_paths: list[Path] = list(storage_directory.glob("*/*.png"))

            self.assertEqual(
                planned_roles,
                [SLIDE_ROLE_COVER, SLIDE_ROLE_HEADING, SLIDE_ROLE_CTA],
            )
            self.assertEqual(len(render_result.slides), 3)
            self.assertGreaterEqual(len(png_paths), 3)
            self.assertTrue(render_result.caption.strip())
            self.assertEqual(
                resolve_carousel_cta_url(source_fields),
                "https://spotmu.com/interest/empty-bullets",
            )

    def test_long_bullet_overflows_to_extra_slides(self) -> None:
        """A bullet past 160 characters becomes more than one bullet slide."""

        long_bullet: str = " ".join(["word"] * 80)
        source_fields: CarouselSourceFields = CarouselSourceFields(
            title="Overflow",
            interest_heading="Overflow heading",
            overview_bullets=[long_bullet],
            canonical_url="https://spotmu.com/interest/overflow",
            external_key="overflow",
        )
        planned_slides = plan_carousel_slides(source_fields)
        bullet_slides = [
            planned_slide
            for planned_slide in planned_slides
            if planned_slide.role == SLIDE_ROLE_BULLET
        ]

        self.assertGreaterEqual(len(bullet_slides), 2)
        self.assertLessEqual(len(bullet_slides[0].text), 160)


if __name__ == "__main__":
    unittest.main()
