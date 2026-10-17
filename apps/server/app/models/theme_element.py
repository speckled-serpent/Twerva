"""Frozen check SQL for Alembic revisions that still import this path.

The live table is ``skeleton_elements``. These strings keep the
``theme_element_content_kind`` casts so historical revisions replay
against the type that exists at that point in the chain. This module
does not register an ORM table.
"""

THEME_ELEMENT_NAME_CHECK_SQL: str = "btrim(name) <> ''"

IMAGE_ASSET_REF_IS_RELATIVE_SQL: str = (
    "btrim(image_asset_ref) = image_asset_ref"
    " AND image_asset_ref <> ''"
    " AND strpos(image_asset_ref, '..') = 0"
    " AND strpos(image_asset_ref, ':') = 0"
    " AND strpos(image_asset_ref, chr(92)) = 0"
    " AND left(image_asset_ref, 1) <> '/'"
    " AND ("
    "lower(right(image_asset_ref, 4)) IN ('.svg', '.png', '.jpg')"
    " OR lower(right(image_asset_ref, 5)) = '.jpeg'"
    ")"
)

THEME_ELEMENT_CONTENT_CHECK_SQL: str = (
    "("
    "("
    "content_kind = 'text'::theme_element_content_kind"
    " AND font_family IS NOT NULL"
    " AND btrim(font_family) <> ''"
    " AND font_size > 0"
    " AND font_color IS NOT NULL"
    " AND btrim(font_color) <> ''"
    " AND alignment IS NOT NULL"
    ")"
    " OR "
    "("
    "content_kind = 'image'::theme_element_content_kind"
    " AND text_source IS NULL"
    " AND image_asset_ref IS NOT NULL"
    ")"
    ")"
    " AND (font_weight IS NULL OR (font_weight >= 1 AND font_weight <= 1000))"
    " AND (font_size IS NULL OR font_size > 0)"
    " AND (image_asset_ref IS NULL OR ("
    f"{IMAGE_ASSET_REF_IS_RELATIVE_SQL}"
    "))"
)
