"""Convert texture backgrounds to picture and drop the enum value.

Revision ID: themes_drop_texture
Revises: theme_elements
Create Date: 2026-10-09

Texture is a picture of a texture. Existing rows keep ``background_asset_ref``
and become ``picture``, so the same file still fills the frame. The Postgres
enum then loses ``texture``. Downgrade puts the value back and leaves those
rows as picture, because the conversion does not record which pictures used
to be textures.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text


revision: str = "themes_drop_texture"
down_revision: str | None = "theme_elements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.execute(text("ALTER TABLE themes ALTER COLUMN background_kind DROP DEFAULT"))
    op.execute(
        text(
            "ALTER TABLE themes ALTER COLUMN background_kind "
            "TYPE text USING background_kind::text"
        ),
    )
    op.execute(
        text(
            "UPDATE themes SET background_kind = 'picture' "
            "WHERE background_kind = 'texture'"
        ),
    )
    op.execute(text("DROP TYPE background_kind"))
    op.execute(
        text(
            "CREATE TYPE background_kind AS ENUM "
            "('picture', 'color', 'gradient')"
        ),
    )
    op.execute(
        text(
            "ALTER TABLE themes ALTER COLUMN background_kind "
            "TYPE background_kind USING background_kind::background_kind"
        ),
    )
    op.execute(
        text(
            "ALTER TABLE themes ALTER COLUMN background_kind "
            "SET DEFAULT 'color'::background_kind"
        ),
    )
    op.execute(
        text("ALTER TABLE themes ALTER COLUMN background_kind SET NOT NULL"),
    )


def downgrade() -> None:

    op.execute(text("ALTER TYPE background_kind ADD VALUE 'texture'"))
