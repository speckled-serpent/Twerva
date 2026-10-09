"""Font files shipped with the theme package.

The dropdown, measurer, and preview all resolve these files from the
package directory. A name that is not in the catalog is left for the
system font scan and then the DejaVu fallback. This module does not
draw text.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_FONT_FAMILY_NAME: str = "Source Sans 3"
FALLBACK_FONT_FAMILY_NAME: str = "DejaVu Sans"
FONT_LICENSE_NAME: str = "SIL Open Font License 1.1"


@dataclass(frozen=True)
class BundledFontFamily:
    """One family the operator can pick. Files live under ``family_id``."""

    family_id: str
    name: str
    category: str
    roman_file: str
    italic_file: str | None
    bold_file: str | None
    bold_italic_file: str | None
    variable: bool
    source_url: str


BUNDLED_FONT_FAMILIES: tuple[BundledFontFamily, ...] = (
    BundledFontFamily(
        family_id="source-sans-3",
        name="Source Sans 3",
        category="sans",
        roman_file="SourceSans3[wght].ttf",
        italic_file="SourceSans3-Italic[wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/sourcesans3",
    ),
    BundledFontFamily(
        family_id="nunito",
        name="Nunito",
        category="sans",
        roman_file="Nunito[wght].ttf",
        italic_file="Nunito-Italic[wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/nunito",
    ),
    BundledFontFamily(
        family_id="dm-sans",
        name="DM Sans",
        category="sans",
        roman_file="DMSans[opsz,wght].ttf",
        italic_file="DMSans-Italic[opsz,wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/dmsans",
    ),
    BundledFontFamily(
        family_id="libre-baskerville",
        name="Libre Baskerville",
        category="serif",
        roman_file="LibreBaskerville[wght].ttf",
        italic_file="LibreBaskerville-Italic[wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/librebaskerville",
    ),
    BundledFontFamily(
        family_id="lora",
        name="Lora",
        category="serif",
        roman_file="Lora[wght].ttf",
        italic_file="Lora-Italic[wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/lora",
    ),
    BundledFontFamily(
        family_id="playfair-display",
        name="Playfair Display",
        category="display",
        roman_file="PlayfairDisplay[wght].ttf",
        italic_file="PlayfairDisplay-Italic[wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/playfairdisplay",
    ),
    BundledFontFamily(
        family_id="oswald",
        name="Oswald",
        category="display",
        roman_file="Oswald[wght].ttf",
        italic_file=None,
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/oswald",
    ),
    BundledFontFamily(
        family_id="source-code-pro",
        name="Source Code Pro",
        category="mono",
        roman_file="SourceCodePro[wght].ttf",
        italic_file="SourceCodePro-Italic[wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/sourcecodepro",
    ),
    BundledFontFamily(
        family_id="jetbrains-mono",
        name="JetBrains Mono",
        category="mono",
        roman_file="JetBrainsMono[wght].ttf",
        italic_file="JetBrainsMono-Italic[wght].ttf",
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/jetbrainsmono",
    ),
    BundledFontFamily(
        family_id="caveat",
        name="Caveat",
        category="handwritten",
        roman_file="Caveat[wght].ttf",
        italic_file=None,
        bold_file=None,
        bold_italic_file=None,
        variable=True,
        source_url="https://github.com/google/fonts/tree/main/ofl/caveat",
    ),
    BundledFontFamily(
        family_id="comic-neue",
        name="Comic Neue",
        category="handwritten",
        roman_file="ComicNeue-Regular.ttf",
        italic_file="ComicNeue-Italic.ttf",
        bold_file="ComicNeue-Bold.ttf",
        bold_italic_file="ComicNeue-BoldItalic.ttf",
        variable=False,
        source_url="https://github.com/google/fonts/tree/main/ofl/comicneue",
    ),
    BundledFontFamily(
        family_id="pacifico",
        name="Pacifico",
        category="handwritten",
        roman_file="Pacifico-Regular.ttf",
        italic_file=None,
        bold_file=None,
        bold_italic_file=None,
        variable=False,
        source_url="https://github.com/google/fonts/tree/main/ofl/pacifico",
    ),
)


def bundled_font_directory() -> Path:
    """Return the package directory that holds the font files."""

    font_directory: Path = Path(__file__).resolve().parent / "bundled_fonts"

    return font_directory


def list_bundled_font_families() -> tuple[BundledFontFamily, ...]:
    """Return the families the dropdown offers, in catalog order."""

    return BUNDLED_FONT_FAMILIES


def find_bundled_font_family(font_family: str) -> BundledFontFamily | None:
    """Return the catalog entry for this name, or null when it is unknown."""

    family_key: str = _normalize_family_name(font_family)

    if family_key == "":

        return None

    for family in BUNDLED_FONT_FAMILIES:
        candidate_key: str = _normalize_family_name(family.name)

        if candidate_key == family_key:

            return family

    return None


def bundled_font_path(
    font_family: str,
    italic: bool,
    prefer_bold: bool,
) -> Path | None:
    """Return the package file for this family and style.

    Args:
        font_family: Requested family name.
        italic: Prefer the italic file when the catalog has one.
        prefer_bold: Prefer a static bold file. Variable fonts ignore this
            and set ``wght`` after the file is opened.

    Returns:
        A file inside the package, or null when the family is not bundled
        or the chosen file is missing.
    """

    family: BundledFontFamily | None = find_bundled_font_family(font_family)

    if family is None:

        return None

    filename: str = _style_filename(family, italic, prefer_bold)
    font_path: Path = bundled_font_directory() / family.family_id / filename

    if not font_path.is_file():

        return None

    return font_path


def _style_filename(
    family: BundledFontFamily,
    italic: bool,
    prefer_bold: bool,
) -> str:
    """Pick a filename. Missing italic or bold stays on this family's roman."""

    if family.variable:

        if italic and family.italic_file is not None:

            return family.italic_file

        return family.roman_file

    if prefer_bold and italic and family.bold_italic_file is not None:

        return family.bold_italic_file

    if prefer_bold and family.bold_file is not None:

        return family.bold_file

    if italic and family.italic_file is not None:

        return family.italic_file

    return family.roman_file


def _normalize_family_name(font_name: str) -> str:
    """Lowercase letters and digits, matching the system font index."""

    normalized_name: str = "".join(
        character.lower()
        for character in font_name
        if character.isalnum()
    )

    return normalized_name
