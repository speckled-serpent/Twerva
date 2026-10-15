"""Add a required name on every theme element.

Revision ID: theme_element_names
Revises: campaign_theme_source
Create Date: 2026-10-15

Existing text rows take the label their Spotmu text source already
showed (Title, Interest heading, Overview bullets, Canonical URL).
Existing image rows take Image plus the band and sort order. The
column is nullable only long enough to backfill, then NOT NULL.
A blank name is rejected by ``ck_theme_elements_name``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.theme_element import THEME_ELEMENT_NAME_CHECK_SQL


revision: str = "theme_element_names"
down_revision: str | None = "campaign_theme_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THEME_ELEMENT_NAME_BACKFILL_SQL: str = """
UPDATE theme_elements
SET name = CASE
    WHEN content_kind = 'text'::theme_element_content_kind
         AND text_source = 'title'::theme_element_text_source
        THEN 'Title'
    WHEN content_kind = 'text'::theme_element_content_kind
         AND text_source = 'interest_heading'::theme_element_text_source
        THEN 'Interest heading'
    WHEN content_kind = 'text'::theme_element_content_kind
         AND text_source = 'overview_bullets'::theme_element_text_source
        THEN 'Overview bullets'
    WHEN content_kind = 'text'::theme_element_content_kind
         AND text_source = 'canonical_url'::theme_element_text_source
        THEN 'Canonical URL'
    WHEN content_kind = 'text'::theme_element_content_kind
        THEN 'Text (' || initcap(band::text) || ', ' || sort_order::text || ')'
    ELSE 'Image (' || initcap(band::text) || ', ' || sort_order::text || ')'
END
"""


def upgrade() -> None:

    op.add_column("theme_elements", sa.Column("name", sa.Text(), nullable=True))
    op.execute(sa.text(THEME_ELEMENT_NAME_BACKFILL_SQL))
    op.alter_column("theme_elements", "name", nullable=False)
    op.create_check_constraint(
        "ck_theme_elements_name",
        "theme_elements",
        THEME_ELEMENT_NAME_CHECK_SQL,
    )


def downgrade() -> None:

    op.drop_constraint(
        "ck_theme_elements_name",
        "theme_elements",
        type_="check",
    )
    op.drop_column("theme_elements", "name")
