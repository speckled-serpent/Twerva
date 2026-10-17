"""Validate album and slide writes, and see which image paths are in use.

Phase 2 does not accept new image bytes. A path is in use when a skeleton
background, a skeleton image element, or an artifact slide stores it.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artifact import Artifact
from app.models.enums import SlideImageLicense
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement


SLUG_FALLBACK: str = "album"
NON_SLUG_CHARACTER_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")
REPEATED_HYPHEN_PATTERN: re.Pattern[str] = re.compile(r"-{2,}")

EMPTY_SLIDE_DETAIL: str = "A slide needs an image, free text, or a labeled field."
BLANK_NAME_DETAIL: str = "Name is required."
ONE_IMAGE_DETAIL: str = "A slide holds one image."
BLANK_FIELD_DETAIL: str = "A field needs a label and a value."
BLANK_IMAGE_SOURCE_DETAIL: str = "Image source is required."
LICENSE_NOTE_DETAIL: str = "A licensed image needs a license note."
IMAGE_IN_USE_DETAIL: str = "This image is still used by a skeleton or an artifact."
SLIDE_IN_USE_DETAIL: str = "This slide is still used by a skeleton or an artifact."
ALBUM_IN_USE_DETAIL: str = "This album is still used by a skeleton or an artifact."


def slugify_carousel_name(
    carousel_name: str,
    fallback_slug: str = SLUG_FALLBACK,
) -> str:
    """Turn a name into a lowercase hyphenated slug.

    Args:
        carousel_name: Operator-facing name.
        fallback_slug: Slug used when the name has no letters or digits.

    Returns:
        A slug. Falls back to ``fallback_slug`` when the name has no
        letters or digits.
    """

    stripped_name: str = carousel_name.strip()
    normalized_name: str = unicodedata.normalize("NFKD", stripped_name)
    ascii_name: str = normalized_name.encode("ascii", "ignore").decode("ascii")
    lowered_name: str = ascii_name.lower()
    hyphenated_name: str = NON_SLUG_CHARACTER_PATTERN.sub("-", lowered_name)
    collapsed_name: str = REPEATED_HYPHEN_PATTERN.sub("-", hyphenated_name)
    source_slug: str = collapsed_name.strip("-")

    if source_slug == "":

        return fallback_slug

    return source_slug


def allocate_unique_source_slug(requested_slug: str, taken_slugs: set[str]) -> str:
    """Return ``requested_slug``, or ``requested-slug-2`` when that slug is taken.

    Args:
        requested_slug: Slug derived from the album name.
        taken_slugs: Existing ``carousels.slug`` values.

    Returns:
        A slug that is not in ``taken_slugs``.
    """

    if requested_slug not in taken_slugs:

        return requested_slug

    suffix_number: int = 2

    while True:
        candidate_slug: str = f"{requested_slug}-{suffix_number}"

        if candidate_slug not in taken_slugs:

            return candidate_slug

        suffix_number += 1


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """Drop blanks and duplicates. Keep the first spelling of each tag.

    Args:
        raw_tags: Tags from the request, in order.

    Returns:
        Cleaned tags.
    """

    cleaned_tags: list[str] = []
    seen_tags: set[str] = set()

    for raw_tag in raw_tags:
        stripped_tag: str = raw_tag.strip()

        if stripped_tag == "" or stripped_tag in seen_tags:
            continue

        seen_tags.add(stripped_tag)
        cleaned_tags.append(stripped_tag)

    return cleaned_tags


def normalize_field_writes(
    field_writes: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Strip field labels and values. A half-filled row is invalid.

    Args:
        field_writes: ``(label, value)`` pairs from the request.

    Returns:
        Stripped pairs. A row that is blank on both sides is dropped.

    Raises:
        ValueError: One side of a row is blank and the other is not.
    """

    cleaned_fields: list[tuple[str, str]] = []

    for raw_label, raw_value in field_writes:
        label: str = raw_label.strip()
        value: str = raw_value.strip()

        if label == "" and value == "":
            continue

        if label == "" or value == "":
            raise ValueError(BLANK_FIELD_DETAIL)

        cleaned_fields.append((label, value))

    return cleaned_fields


def slide_has_content(
    free_text: str | None,
    field_count: int,
    image_count: int,
) -> bool:
    """Return true when a slide has an image, free text, or a field.

    Args:
        free_text: Body after stripping, or null.
        field_count: Number of labeled fields that will be stored.
        image_count: Number of images that will remain on the slide.

    Returns:
        Whether the slide is allowed to be saved.
    """

    if image_count > 0:

        return True

    if free_text is not None and free_text.strip() != "":

        return True

    if field_count > 0:

        return True

    return False


def normalize_image_metadata(
    image_license: SlideImageLicense,
    source: str,
    license_note: str,
    alt_text: str | None,
) -> tuple[str, str, str | None]:
    """Return source, license note, and alt. Invalid license writes nothing.

    Args:
        image_license: Allowlisted license.
        source: Provenance. A URL or a short note.
        license_note: Required when the license is ``licensed``.
        alt_text: Optional description. Blank becomes null.

    Returns:
        Stripped source, note, and alt.

    Raises:
        ValueError: Source is blank, or ``licensed`` has no note.
    """

    image_source: str = source.strip()

    if image_source == "":
        raise ValueError(BLANK_IMAGE_SOURCE_DETAIL)

    cleaned_note: str = license_note.strip()

    if image_license == SlideImageLicense.LICENSED and cleaned_note == "":
        raise ValueError(LICENSE_NOTE_DETAIL)

    if image_license != SlideImageLicense.LICENSED:
        cleaned_note = ""

    cleaned_alt: str | None = None

    if alt_text is not None:
        stripped_alt: str = alt_text.strip()
        cleaned_alt = None if stripped_alt == "" else stripped_alt

    return image_source, cleaned_note, cleaned_alt


def normalize_free_text(free_text: str | None) -> str | None:
    """Store blank free text as null.

    Args:
        free_text: Request body, or null.

    Returns:
        Stripped text, or null when it is empty.
    """

    if free_text is None:

        return None

    stripped_text: str = free_text.strip()

    if stripped_text == "":

        return None

    return stripped_text


def collect_used_paths(
    candidate_paths: set[str],
    skeleton_background_refs: list[str | None],
    element_image_refs: list[str | None],
    artifact_slide_rows: list[object],
) -> set[str]:
    """Return candidate paths that a skeleton or artifact still stores.

    Args:
        candidate_paths: Image ``relative_path`` values being removed.
        skeleton_background_refs: ``skeletons.background_asset_ref`` values.
        element_image_refs: ``skeleton_elements.image_asset_ref`` values.
        artifact_slide_rows: ``artifacts.slides`` JSON values.

    Returns:
        The subset of ``candidate_paths`` that is still referenced.
    """

    used_paths: set[str] = set()

    for stored_path in skeleton_background_refs:
        if stored_path in candidate_paths:
            used_paths.add(stored_path)

    for stored_path in element_image_refs:
        if stored_path in candidate_paths:
            used_paths.add(stored_path)

    for slide_row in artifact_slide_rows:
        used_paths.update(_artifact_slide_paths(slide_row, candidate_paths))

    return used_paths


def stored_paths_in_use(
    our_database_session: Session,
    candidate_paths: set[str],
) -> set[str]:
    """Query skeletons and artifacts for the given image paths.

    Args:
        our_database_session: Open SQLAlchemy session.
        candidate_paths: Paths that a delete would remove.

    Returns:
        Paths that are still stored on a skeleton or an artifact.
    """

    if len(candidate_paths) == 0:

        return set()

    background_refs: list[str | None] = list(
        our_database_session.scalars(
            select(Skeleton.background_asset_ref).where(
                Skeleton.background_asset_ref.in_(candidate_paths),
            ),
        ).all(),
    )
    element_refs: list[str | None] = list(
        our_database_session.scalars(
            select(SkeletonElement.image_asset_ref).where(
                SkeletonElement.image_asset_ref.in_(candidate_paths),
            ),
        ).all(),
    )
    artifact_slide_rows: list[object] = list(
        our_database_session.scalars(select(Artifact.slides)).all(),
    )

    return collect_used_paths(
        candidate_paths,
        background_refs,
        element_refs,
        artifact_slide_rows,
    )


def in_use_detail(summary: str, used_paths: set[str]) -> str:
    """Join a delete block message with the paths that blocked it.

    Args:
        summary: Sentence naming the album, slide, or image.
        used_paths: Paths still stored elsewhere.

    Returns:
        Detail text for HTTP 409.
    """

    ordered_paths: list[str] = sorted(used_paths)
    path_list: str = ", ".join(ordered_paths)

    return f"{summary} Still used: {path_list}."


def new_row_id() -> uuid.UUID:
    """Return an id for a row created in this process."""

    row_id: uuid.UUID = uuid.uuid4()

    return row_id


def _artifact_slide_paths(slide_row: object, candidate_paths: set[str]) -> set[str]:
    """Return candidate paths named by one artifact's slides JSON."""

    found_paths: set[str] = set()

    if not isinstance(slide_row, list):

        return found_paths

    for slide in slide_row:

        if not isinstance(slide, dict):
            continue

        asset_ref: object = slide.get("asset_ref")

        if isinstance(asset_ref, str) and asset_ref in candidate_paths:
            found_paths.add(asset_ref)

    return found_paths
