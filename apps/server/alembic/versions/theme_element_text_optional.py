"""Allow a text element to omit text_source.

Revision ID: theme_element_text_optional
Revises: theme_element_names
Create Date: 2026-10-15

Unit text is stored by theme element id and labeled by the element
name. ``text_source`` stays for Spotmu source-item preview when a row
already has one. Image rows still forbid it. Existing text rows keep
their source. Downgrade restores the check that required one.
"""

from collections.abc import Sequence

from alembic import op

from app.models.theme_element import THEME_ELEMENT_CONTENT_CHECK_SQL


revision: str = "theme_element_text_optional"
down_revision: str | None = "theme_element_names"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTENT_CHECK_NAME: str = "ck_theme_elements_content"

THEME_ELEMENT_CONTENT_CHECK_REQUIRING_TEXT_SOURCE_SQL: str = (
    "("
    "("
    "content_kind = 'text'::theme_element_content_kind"
    " AND text_source IS NOT NULL"
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
    "))"
    ")"
)


def upgrade() -> None:

    op.drop_constraint(CONTENT_CHECK_NAME, "theme_elements", type_="check")
    op.create_check_constraint(
        CONTENT_CHECK_NAME,
        "theme_elements",
        THEME_ELEMENT_CONTENT_CHECK_SQL,
    )


def downgrade() -> None:

    op.drop_constraint(CONTENT_CHECK_NAME, "theme_elements", type_="check")
    op.create_check_constraint(
        CONTENT_CHECK_NAME,
        "theme_elements",
        THEME_ELEMENT_CONTENT_CHECK_REQUIRING_TEXT_SOURCE_SQL,
    )
