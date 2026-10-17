"""Default album seed, read API, and unchanged theme-defaults rendering."""

import os
import tempfile
import unittest
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from PIL import Image

from app.api.v1.schemas import CarouselReadResponse, SkeletonPreviewRequest
from app.carousels.slide_skeleton import CarouselStepState
from app.api.v1.carousels import (
    carousels_list_statement,
    get_carousel,
    list_carousels,
    carousels_router,
)
from app.models.album import AlbumImage
from app.models.carousel import Carousel, Slide
from app.models.enums import (
    AdvertisementType,
    SkeletonStatus,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
)
from app.models.skeleton import Skeleton
from app.carousels.default_carousel import (
    DEFAULT_ALBUM_SLUG,
    DEFAULT_ALBUM_SKELETON_ID,
    default_album_carousel_id,
    default_library_album_id,
    default_slide_seeds,
)
from app.skeletons.default_images import (
    DEFAULT_ALBUM_NAME,
    DEFAULT_IMAGE_FILENAMES,
    SKELETON_DEFAULTS_PREFIX,
    default_image_directory,
)
from app.models import BackgroundKind
from tests.test_skeleton_preview import _decoded_image, _preview


LICENSES_PATH: Path = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "skeletons"
    / "default_images"
    / "LICENSES.md"
)


class DefaultAlbumSeedTests(unittest.TestCase):
    """The six packaged photos become image-only slides with CC0 or PD."""

    def test_seed_matches_licenses_and_packaged_files(self) -> None:
        """Each slide keeps theme-defaults/ and the license file's source URL."""

        seeds = default_slide_seeds()
        seeds_by_filename = {seed.filename: seed for seed in seeds}
        licenses_text: str = LICENSES_PATH.read_text(encoding="utf-8")
        sections: list[str] = licenses_text.split("\n## ")

        self.assertEqual(len(seeds), len(DEFAULT_IMAGE_FILENAMES))
        self.assertEqual(
            [seed.filename for seed in seeds],
            list(DEFAULT_IMAGE_FILENAMES),
        )

        for section in sections[1:]:
            filename: str = section.split("\n", 1)[0].strip()
            source_line: str = next(
                line for line in section.splitlines() if line.startswith("- Source: ")
            )
            source_url: str = source_line.removeprefix("- Source: ").strip()
            seed = seeds_by_filename[filename]
            image_path: Path = default_image_directory() / filename

            self.assertEqual(seed.source_url, source_url)
            self.assertEqual(seed.relative_path, f"{SKELETON_DEFAULTS_PREFIX}{filename}")
            self.assertEqual(seed.byte_size, image_path.stat().st_size)
            self.assertEqual(seed.width, 1080)
            self.assertEqual(seed.height, 1920)
            self.assertIn(
                seed.image_license,
                {SlideImageLicense.CC0, SlideImageLicense.PUBLIC_DOMAIN},
            )

            if "License: CC0" in section:
                self.assertEqual(seed.image_license, SlideImageLicense.CC0)
            else:
                self.assertIn("License: Public domain", section)
                self.assertEqual(seed.image_license, SlideImageLicense.PUBLIC_DOMAIN)

    def test_seed_ids_are_stable(self) -> None:
        """Re-reading the catalog does not mint new ids."""

        first_carousel_id: uuid.UUID = default_album_carousel_id()
        second_carousel_id: uuid.UUID = default_album_carousel_id()
        first_seeds = default_slide_seeds()
        second_seeds = default_slide_seeds()

        self.assertEqual(first_carousel_id, second_carousel_id)
        self.assertEqual(
            [seed.slide_id for seed in first_seeds],
            [seed.slide_id for seed in second_seeds],
        )
        self.assertEqual(len({seed.slide_id for seed in first_seeds}), 6)
        self.assertEqual(len({seed.image_id for seed in first_seeds}), 6)


class CarouselReadApiTests(unittest.TestCase):
    """GET list and GET one carousel. Writes live beside these reads."""

    def test_get_default_returns_six_licensed_image_only_slides(self) -> None:
        """Detail includes each path, license, and no skeleton text."""

        carousel: Carousel = _default_source_from_catalog()
        skeleton: Skeleton = _paper_skeleton()
        fake_session: MagicMock = MagicMock()
        fake_session.get.side_effect = _session_get(carousel, skeleton)

        response: CarouselReadResponse = get_carousel(carousel.id, fake_session)
        licenses: set[SlideImageLicense] = set()

        self.assertEqual(response.slug, DEFAULT_ALBUM_SLUG)
        self.assertEqual(response.name, DEFAULT_ALBUM_NAME)
        self.assertEqual(response.skeleton_id, DEFAULT_ALBUM_SKELETON_ID)
        self.assertEqual(response.album_id, default_library_album_id())
        self.assertEqual(response.generation_number, 1)
        self.assertEqual(response.editor_step, 3)
        self.assertEqual(response.research, [])
        self.assertEqual(response.steps.basic, CarouselStepState.DONE)
        self.assertEqual(response.steps.instructions, CarouselStepState.LOCKED)
        self.assertEqual(response.steps.content, CarouselStepState.DONE)
        self.assertEqual(response.steps.slides, CarouselStepState.DONE)
        self.assertEqual(response.steps.final, CarouselStepState.LOCKED)
        self.assertEqual(len(response.slides), 6)

        for slide, filename in zip(response.slides, DEFAULT_IMAGE_FILENAMES, strict=True):
            self.assertEqual(slide.name, default_slide_seeds()[slide.position].name)
            self.assertEqual(slide.texts, [])
            self.assertEqual(len(slide.images), 1)
            image = slide.images[0]
            licenses.add(image.license)

            self.assertEqual(image.relative_path, f"{SKELETON_DEFAULTS_PREFIX}{filename}")
            self.assertEqual(image.media_type, SlideImageMediaType.JPEG)
            self.assertEqual(image.intake, SlideImageIntake.UPLOAD)
            self.assertEqual(image.license_note, "")
            self.assertTrue(image.source.startswith("https://commons.wikimedia.org/"))
            self.assertIsNone(image.thumbnail_path)

        self.assertEqual(
            licenses,
            {SlideImageLicense.CC0, SlideImageLicense.PUBLIC_DOMAIN},
        )

    def test_list_kind_album_returns_the_default_count(self) -> None:
        """The list has no kind filter, and the list item counts slides."""

        carousel: Carousel = _default_source_from_catalog()
        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = [carousel]

        list_items = list_carousels(fake_session)
        statement = fake_session.scalars.call_args.args[0]

        self.assertEqual(len(list_items), 1)
        self.assertEqual(list_items[0].slug, DEFAULT_ALBUM_SLUG)
        self.assertEqual(list_items[0].skeleton_id, DEFAULT_ALBUM_SKELETON_ID)
        self.assertEqual(list_items[0].album_id, default_library_album_id())
        self.assertEqual(list_items[0].generation_number, 1)
        self.assertEqual(list_items[0].editor_step, 3)
        self.assertEqual(list_items[0].slide_count, 6)
        self.assertFalse(hasattr(list_items[0], "steps"))
        self.assertFalse(hasattr(list_items[0], "research"))
        self.assertIsNone(statement.whereclause)
        self.assertIsNone(carousels_list_statement().whereclause)

    def test_missing_source_is_not_found(self) -> None:
        """An unknown id is HTTP 404 and does not write."""

        fake_session: MagicMock = MagicMock()
        fake_session.get.return_value = None
        missing_id: uuid.UUID = uuid.uuid4()

        with self.assertRaises(HTTPException) as raised_http:
            get_carousel(missing_id, fake_session)

        self.assertEqual(raised_http.exception.status_code, 404)
        fake_session.add.assert_not_called()
        fake_session.commit.assert_not_called()

    def test_source_routes_cover_reads_and_album_writes(self) -> None:
        """List and detail stay readable. Album and slide writes are registered."""

        methods_by_path: dict[str, set[str]] = {}

        for route in carousels_router.routes:
            path: str = getattr(route, "path", "")
            methods: set[str] = set(getattr(route, "methods", set()) or set())
            methods_by_path.setdefault(path, set()).update(methods)

        self.assertTrue({"GET", "POST"}.issubset(methods_by_path["/carousels"]))
        self.assertTrue(
            {"GET", "PATCH", "DELETE"}.issubset(methods_by_path["/carousels/{carousel_id}"]),
        )
        self.assertEqual(
            methods_by_path["/carousels/{carousel_id}/step"],
            {"PATCH"},
        )
        self.assertEqual(
            methods_by_path["/carousels/{carousel_id}/album"],
            {"PUT", "POST", "DELETE"},
        )
        self.assertIn("POST", methods_by_path["/carousels/{carousel_id}/slides"])
        self.assertTrue(
            {"PATCH", "DELETE"}.issubset(
                methods_by_path["/carousels/{carousel_id}/slides/{slide_id}"],
            ),
        )
        image_path: str = (
            "/carousels/{carousel_id}/slides/{slide_id}/images/{image_id}"
        )
        self.assertTrue(
            {"PATCH", "DELETE"}.issubset(methods_by_path[image_path]),
        )
        self.assertIn("GET", methods_by_path[f"{image_path}/file"])
        self.assertIn("GET", methods_by_path[f"{image_path}/thumbnail"])
        self.assertNotIn("POST", methods_by_path[image_path])
        self.assertIn(
            "POST",
            methods_by_path["/carousels/{carousel_id}/slides/{slide_id}/images"],
        )
        self.assertIn(
            "POST",
            methods_by_path["/carousels/{carousel_id}/slides/{slide_id}/images/import"],
        )
        self.assertNotIn("/carousels/resource", methods_by_path)
        self.assertNotIn("/carousels/{carousel_id}/resource", methods_by_path)

    def test_list_echoes_stored_generation_and_editor_step(self) -> None:
        """The list returns the stored numbers. It does not derive them."""

        carousel: Carousel = _default_source_from_catalog()
        carousel.generation_number = 4
        carousel.editor_step = 0
        fake_session: MagicMock = MagicMock()
        fake_session.scalars.return_value.all.return_value = [carousel]

        list_items = list_carousels(fake_session)

        self.assertEqual(list_items[0].generation_number, 4)
        self.assertEqual(list_items[0].editor_step, 0)


class SkeletonDefaultsRenderingUnchangedTests(unittest.TestCase):
    """A stored theme-defaults path still renders. The request path stays put."""

    def test_catalog_path_still_renders_and_is_not_rewritten(self) -> None:
        """Preview uses the seeded path and leaves that path on the request."""

        stored_ref: str = default_slide_seeds()[0].relative_path

        with tempfile.TemporaryDirectory() as storage_directory:
            storage: Path = Path(storage_directory)
            preview_request: SkeletonPreviewRequest = SkeletonPreviewRequest(
                background_kind=BackgroundKind.PICTURE,
                background_asset_ref=stored_ref,
            )

            response = _preview(preview_request, storage)
            rendered: Image.Image = _decoded_image(response)

            self.assertEqual(preview_request.background_asset_ref, stored_ref)
            self.assertFalse(response.blocked)
            self.assertEqual(rendered.size, (1080, 1920))


def _default_source_from_catalog() -> Carousel:
    """Build the seeded album in memory, the way a migrated row would look."""

    now: datetime = datetime.now(timezone.utc)
    carousel: Carousel = Carousel(
        id=default_album_carousel_id(),
        skeleton_id=DEFAULT_ALBUM_SKELETON_ID,
        name=DEFAULT_ALBUM_NAME,
        slug=DEFAULT_ALBUM_SLUG,
        album_id=default_library_album_id(),
        generation_number=1,
        editor_step=3,
        created_at=now,
        updated_at=now,
    )
    slides: list[Slide] = []

    for seed in default_slide_seeds():
        slide: Slide = Slide(
            id=seed.slide_id,
            carousel_id=carousel.id,
            position=seed.position,
            name=seed.name,
            created_at=now,
            updated_at=now,
        )
        image: AlbumImage = AlbumImage(
            id=seed.image_id,
            album_id=default_library_album_id(),
            position=seed.position,
            relative_path=seed.relative_path,
            media_type=SlideImageMediaType.JPEG,
            byte_size=seed.byte_size,
            width=seed.width,
            height=seed.height,
            alt_text=None,
            license=seed.image_license,
            source=seed.source_url,
            license_note="",
            intake=SlideImageIntake.UPLOAD,
            thumbnail_path=None,
            created_at=now,
            updated_at=now,
        )
        slide.album_image = image
        slide.element_texts = []
        slide.exclusions = []
        slides.append(slide)

    carousel.slides = slides
    carousel.research_links = []

    return carousel


def _paper_skeleton() -> Skeleton:
    """Spotmu Paper v1 as seeded: a color background and no image element."""

    skeleton: Skeleton = Skeleton(
        id=DEFAULT_ALBUM_SKELETON_ID,
        name="Spotmu Paper v1",
        slug="spotmu-paper-v1",
        advertisement_type=AdvertisementType.CAROUSEL,
        template_key="spotmu_paper_v1",
        status=SkeletonStatus.DRAFT,
        background_kind=BackgroundKind.COLOR,
    )
    skeleton.elements = []

    return skeleton


def _session_get(
    carousel: Carousel,
    skeleton: Skeleton,
) -> Callable[[type[object], uuid.UUID], object | None]:
    """Return a ``session.get`` stand-in for one carousel and its skeleton."""

    def get_row(model: type[object], row_id: uuid.UUID) -> object | None:
        if model is Carousel and row_id == carousel.id:
            return carousel

        if model is Skeleton and row_id == skeleton.id:
            return skeleton

        return None

    return get_row


if __name__ == "__main__":
    unittest.main()
