"""Bundled theme fonts resolve from the package, then fall back."""

import os
import unittest
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from PIL import ImageFont

from app.themes.bundled_fonts import (
    BUNDLED_FONT_FAMILIES,
    DEFAULT_FONT_FAMILY_NAME,
    FALLBACK_FONT_FAMILY_NAME,
    BundledFontFamily,
    bundled_font_directory,
    bundled_font_path,
    find_bundled_font_family,
    list_bundled_font_families,
)
from app.themes.elements import (
    ThemeElementError,
    resolve_theme_element,
)
from app.themes.measure import load_theme_face
from app.models.enums import (
    ThemeElementAlignment,
    ThemeElementContentKind,
    ThemeElementTextSource,
)


class BundledFontTests(unittest.TestCase):
    """The catalog, licenses, and face loader agree on the packaged files."""

    def test_catalog_files_are_packaged_under_the_ofl(self) -> None:
        """Each family has its files and an OFL license next to them."""

        families: tuple[BundledFontFamily, ...] = list_bundled_font_families()
        font_directory: Path = bundled_font_directory()
        categories: set[str] = set()

        self.assertGreaterEqual(len(families), 8)
        self.assertLessEqual(len(families), 15)
        self.assertEqual(families, BUNDLED_FONT_FAMILIES)
        self.assertTrue((font_directory / "LICENSES.md").is_file())

        for family in families:
            family_directory: Path = font_directory / family.family_id
            license_path: Path = family_directory / "OFL.txt"
            license_text: str = license_path.read_text(encoding="utf-8")
            categories.add(family.category)

            self.assertTrue(license_path.is_file(), family.family_id)
            self.assertIn("SIL Open Font License", license_text)
            self.assertIn(family.name, (font_directory / "LICENSES.md").read_text(encoding="utf-8"))
            self.assertTrue((family_directory / family.roman_file).is_file())

            if family.italic_file is not None:
                self.assertTrue((family_directory / family.italic_file).is_file())

            if family.bold_file is not None:
                self.assertTrue((family_directory / family.bold_file).is_file())

            if family.bold_italic_file is not None:
                self.assertTrue((family_directory / family.bold_italic_file).is_file())

        self.assertEqual(categories, {"sans", "serif", "display", "mono", "handwritten"})
        self.assertIsNotNone(find_bundled_font_family(DEFAULT_FONT_FAMILY_NAME))
        self.assertIsNone(find_bundled_font_family(FALLBACK_FONT_FAMILY_NAME))

    def test_bundled_family_loads_from_the_package(self) -> None:
        """A catalog family does not use a system font of the same name."""

        regular_face: ImageFont.ImageFont = load_theme_face(
            "Source Sans 3",
            48,
            False,
            False,
            None,
        )
        italic_face: ImageFont.ImageFont = load_theme_face(
            "Source Sans 3",
            48,
            False,
            True,
            None,
        )
        bold_face: ImageFont.ImageFont = load_theme_face(
            "Source Sans 3",
            64,
            True,
            False,
            None,
        )
        regular_width_face: ImageFont.ImageFont = load_theme_face(
            "Source Sans 3",
            64,
            False,
            False,
            None,
        )
        comic_bold_italic: ImageFont.ImageFont = load_theme_face(
            "Comic Neue",
            48,
            True,
            True,
            None,
        )
        pacifico_face: ImageFont.ImageFont = load_theme_face(
            "Pacifico",
            48,
            True,
            True,
            None,
        )

        self.assertIsInstance(regular_face, ImageFont.FreeTypeFont)
        self.assertIsInstance(italic_face, ImageFont.FreeTypeFont)
        self.assertIsInstance(bold_face, ImageFont.FreeTypeFont)
        self.assertIsInstance(regular_width_face, ImageFont.FreeTypeFont)
        self.assertIsInstance(comic_bold_italic, ImageFont.FreeTypeFont)
        self.assertIsInstance(pacifico_face, ImageFont.FreeTypeFont)
        regular_path: str = str(regular_face.path)
        italic_path: str = str(italic_face.path)
        comic_path: str = str(comic_bold_italic.path)
        pacifico_path: str = str(pacifico_face.path)

        self.assertIn("bundled_fonts", regular_path)
        self.assertIn("SourceSans3", Path(regular_path).name)
        self.assertIn("Italic", Path(italic_path).name)
        self.assertIn("BoldItalic", Path(comic_path).name)
        self.assertIn("Pacifico-Regular", Path(pacifico_path).name)
        self.assertNotEqual(
            bold_face.getbbox("M")[2],
            regular_width_face.getbbox("M")[2],
        )
        self.assertEqual(
            bundled_font_path("Oswald", True, False),
            bundled_font_directory() / "oswald" / "Oswald[wght].ttf",
        )

    def test_unknown_family_falls_back_without_raising(self) -> None:
        """An old theme name still loads a face. It is not a bundled file."""

        fallback_face: ImageFont.ImageFont = load_theme_face(
            "No Such Preview Face",
            32,
            False,
            False,
            None,
        )

        self.assertIsNotNone(fallback_face)

        if isinstance(fallback_face, ImageFont.FreeTypeFont):
            fallback_path: str = str(fallback_face.path)

            self.assertNotIn("bundled_fonts", fallback_path)

    def test_rectangle_opacity_and_radius_are_bounded(self) -> None:
        """Opacity and radius reject values outside the stored range."""

        resolved_element = resolve_theme_element(
            ThemeElementContentKind.TEXT,
            "#00FF00",
            ThemeElementTextSource.TITLE,
            "Source Sans 3",
            32,
            "#112233",
            False,
            False,
            False,
            False,
            None,
            ThemeElementAlignment.LEFT,
            None,
        )

        self.assertEqual(resolved_element.rectangle_opacity, 100)
        self.assertEqual(resolved_element.rectangle_radius, 0)

        with self.assertRaises(ThemeElementError) as opacity_error:
            resolve_theme_element(
                ThemeElementContentKind.TEXT,
                "#00FF00",
                ThemeElementTextSource.TITLE,
                "Source Sans 3",
                32,
                "#112233",
                False,
                False,
                False,
                False,
                None,
                ThemeElementAlignment.LEFT,
                None,
                101,
                0,
            )

        with self.assertRaises(ThemeElementError) as radius_error:
            resolve_theme_element(
                ThemeElementContentKind.TEXT,
                "#00FF00",
                ThemeElementTextSource.TITLE,
                "Source Sans 3",
                32,
                "#112233",
                False,
                False,
                False,
                False,
                None,
                ThemeElementAlignment.LEFT,
                None,
                100,
                -1,
            )

        self.assertEqual(
            opacity_error.exception.detail,
            "rectangle_opacity must be an integer from 0 through 100.",
        )
        self.assertEqual(
            radius_error.exception.detail,
            "rectangle_radius must be an integer from 0 through 10000.",
        )


if __name__ == "__main__":
    unittest.main()
