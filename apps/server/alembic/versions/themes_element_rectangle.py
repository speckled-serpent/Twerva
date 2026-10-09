"""Add rectangle opacity and corner radius on theme elements.

Revision ID: themes_element_rectangle
Revises: themes_drop_texture
Create Date: 2026-10-09

``rectangle_opacity`` is 0 through 100 and defaults to 100 (solid).
``rectangle_radius`` is pixels, 0 through 10000, and defaults to 0
(square corners). The renderer still clamps the radius to half the
shorter side of the placed box. A null ``rectangle_color`` stays clear.
Existing rows receive the defaults.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "themes_element_rectangle"
down_revision: str | None = "themes_drop_texture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.add_column(
        "theme_elements",
        sa.Column(
            "rectangle_opacity",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
    )
    op.add_column(
        "theme_elements",
        sa.Column(
            "rectangle_radius",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_theme_elements_rectangle_style",
        "theme_elements",
        "rectangle_opacity >= 0 AND rectangle_opacity <= 100"
        " AND rectangle_radius >= 0 AND rectangle_radius <= 10000",
    )


def downgrade() -> None:

    op.drop_constraint(
        "ck_theme_elements_rectangle_style",
        "theme_elements",
        type_="check",
    )
    op.drop_column("theme_elements", "rectangle_radius")
    op.drop_column("theme_elements", "rectangle_opacity")
