"""Move carousels that fail the album rule onto Content.

Revision ID: carousel_editor_step_content
Revises: carousel_steps
Create Date: 2026-10-18

``carousel_steps`` left every carousel, including Default, on Slides
(``editor_step`` 3). The album rule fails when the skeleton has a
picture background or an image element and ``album_id`` is null. Those
rows move to Content (``editor_step`` 2). An attached album passes even
when it has no images. A color or gradient skeleton with no image
element passes with a null album. Research is not read. Default stays
on Slides.

Downgrade puts those same rows back on Slides, which is where
``carousel_steps`` left them. It does not change a carousel the album
rule already passed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "carousel_editor_step_content"
down_revision: str | None = "carousel_steps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EDITOR_STEP_CONTENT: int = 2
EDITOR_STEP_SLIDES: int = 3

# The album rule fails when a picture is required and no album is set.
# Picture means a picture background or any image element.
ALBUM_RULE_FAILS_SQL: str = """
album_id IS NULL
AND (
    EXISTS (
        SELECT 1
        FROM skeletons AS skeleton
        WHERE skeleton.id = carousels.skeleton_id
          AND skeleton.background_kind = 'picture'::background_kind
    )
    OR EXISTS (
        SELECT 1
        FROM skeleton_elements AS element
        WHERE element.skeleton_id = carousels.skeleton_id
          AND element.content_kind = 'image'::skeleton_element_content_kind
    )
)
"""


def upgrade() -> None:
    """Set Content where the album rule fails. Leave every other row."""

    op.execute(
        sa.text(
            f"""
            UPDATE carousels
            SET editor_step = :editor_step
            WHERE {ALBUM_RULE_FAILS_SQL}
            """
        ).bindparams(editor_step=EDITOR_STEP_CONTENT),
    )


def downgrade() -> None:
    """Put the rows this upgrade moved back on Slides.

    Only a carousel that still fails the album rule and is on Content
    is returned to 3. A carousel the rule already passed keeps its step.
    """

    op.execute(
        sa.text(
            f"""
            UPDATE carousels
            SET editor_step = :slides_step
            WHERE editor_step = :content_step
              AND {ALBUM_RULE_FAILS_SQL}
            """
        ).bindparams(
            slides_step=EDITOR_STEP_SLIDES,
            content_step=EDITOR_STEP_CONTENT,
        ),
    )
