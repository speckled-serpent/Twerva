"""Store one text value per theme text element on the unit.

Revision ID: unit_element_texts
Revises: sources_theme_bound
Create Date: 2026-10-15

``unit_element_texts`` replaces ``units.free_text``, ``units.tags``, and
``unit_fields``. Existing free text, then labeled field values, are
copied onto the source theme's text elements in frame order. Extra
pieces and tags have no element to land on and are dropped. Downgrade
puts the first stored value back into ``free_text`` and leaves fields
and tags empty.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

import sqlalchemy as sa

from app.models.content_source import (
    UNIT_FIELD_TEXT_CHECK_SQL,
    UNIT_POSITION_CHECK_SQL,
)


revision: str = "unit_element_texts"
down_revision: str | None = "sources_theme_bound"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
_BAND_RANK: dict[str, int] = {"top": 0, "middle": 1, "bottom": 2}


def upgrade() -> None:

    _create_unit_element_texts_table()
    database_connection: Connection = op.get_bind()
    _copy_existing_text(database_connection)
    op.drop_table("unit_fields")
    op.drop_column("units", "tags")
    op.drop_column("units", "free_text")


def downgrade() -> None:

    op.add_column("units", sa.Column("free_text", sa.Text(), nullable=True))
    op.add_column(
        "units",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    _recreate_unit_fields_table()
    database_connection: Connection = op.get_bind()
    _restore_first_text(database_connection)
    op.drop_table("unit_element_texts")


def _create_unit_element_texts_table() -> None:
    """One row per unit and theme text element."""

    op.create_table(
        "unit_element_texts",
        sa.Column("id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("unit_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("theme_element_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name="fk_unit_element_texts_unit_id_units",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["theme_element_id"],
            ["theme_elements.id"],
            name="fk_unit_element_texts_theme_element_id_theme_elements",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_unit_element_texts"),
        sa.UniqueConstraint(
            "unit_id",
            "theme_element_id",
            name="uq_unit_element_texts_unit_id_theme_element_id",
        ),
    )
    op.create_index(
        "ix_unit_element_texts_unit_id",
        "unit_element_texts",
        ["unit_id"],
    )
    op.create_index(
        "ix_unit_element_texts_theme_element_id",
        "unit_element_texts",
        ["theme_element_id"],
    )


def _recreate_unit_fields_table() -> None:
    """Restore an empty ``unit_fields`` table for the previous revision."""

    op.create_table(
        "unit_fields",
        sa.Column("id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("unit_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name="fk_unit_fields_unit_id_units",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_unit_fields"),
        sa.UniqueConstraint(
            "unit_id",
            "position",
            name="uq_unit_fields_unit_id_position",
        ),
        sa.CheckConstraint(UNIT_POSITION_CHECK_SQL, name="ck_unit_fields_position"),
        sa.CheckConstraint(UNIT_FIELD_TEXT_CHECK_SQL, name="ck_unit_fields_text"),
    )
    op.create_index("ix_unit_fields_unit_id", "unit_fields", ["unit_id"])


def _copy_existing_text(database_connection: Connection) -> None:
    """Place free text, then field values, on the theme's text elements."""

    unit_rows = database_connection.execute(
        sa.text(
            """
            SELECT u.id::text, u.free_text, s.theme_id::text
            FROM units AS u
            JOIN sources AS s ON s.id = u.source_id
            """
        ),
    ).fetchall()

    for unit_row in unit_rows:
        unit_id: str = str(unit_row[0])
        free_text: str | None = None if unit_row[1] is None else str(unit_row[1])
        theme_id: str = str(unit_row[2])
        pieces: list[str] = _text_pieces(database_connection, unit_id, free_text)
        element_ids: list[str] = _text_element_ids(database_connection, theme_id)

        for index, element_id in enumerate(element_ids):

            if index >= len(pieces):
                break

            database_connection.execute(
                sa.text(
                    """
                    INSERT INTO unit_element_texts (
                        id, unit_id, theme_element_id, value
                    )
                    VALUES (
                        gen_random_uuid(),
                        CAST(:unit_id AS uuid),
                        CAST(:theme_element_id AS uuid),
                        :value
                    )
                    """
                ),
                {
                    "unit_id": unit_id,
                    "theme_element_id": element_id,
                    "value": pieces[index],
                },
            )


def _restore_first_text(database_connection: Connection) -> None:
    """Put the first frame-order value back on ``units.free_text``."""

    unit_rows = database_connection.execute(
        sa.text(
            """
            SELECT u.id::text, s.theme_id::text
            FROM units AS u
            JOIN sources AS s ON s.id = u.source_id
            """
        ),
    ).fetchall()

    for unit_row in unit_rows:
        unit_id: str = str(unit_row[0])
        theme_id: str = str(unit_row[1])
        element_ids: list[str] = _text_element_ids(database_connection, theme_id)
        restored_value: str | None = None

        for element_id in element_ids:
            stored_row = database_connection.execute(
                sa.text(
                    """
                    SELECT value
                    FROM unit_element_texts
                    WHERE unit_id = CAST(:unit_id AS uuid)
                      AND theme_element_id = CAST(:theme_element_id AS uuid)
                    """
                ),
                {"unit_id": unit_id, "theme_element_id": element_id},
            ).fetchone()

            if stored_row is None:
                continue

            restored_value = str(stored_row[0])

            break

        if restored_value is None:
            continue

        database_connection.execute(
            sa.text(
                """
                UPDATE units
                SET free_text = :free_text
                WHERE id = CAST(:unit_id AS uuid)
                """
            ),
            {"unit_id": unit_id, "free_text": restored_value},
        )


def _text_pieces(
    database_connection: Connection,
    unit_id: str,
    free_text: str | None,
) -> list[str]:
    """Free text first, then labeled values. Blank free text is skipped."""

    pieces: list[str] = []

    if free_text is not None and free_text.strip() != "":
        pieces.append(free_text.strip())

    field_rows = database_connection.execute(
        sa.text(
            """
            SELECT value
            FROM unit_fields
            WHERE unit_id = CAST(:unit_id AS uuid)
            ORDER BY position, id
            """
        ),
        {"unit_id": unit_id},
    ).fetchall()

    for field_row in field_rows:
        pieces.append(str(field_row[0]))

    return pieces


def _text_element_ids(database_connection: Connection, theme_id: str) -> list[str]:
    """Text element ids in band order, then sort order."""

    element_rows = database_connection.execute(
        sa.text(
            """
            SELECT id::text, band::text, sort_order
            FROM theme_elements
            WHERE theme_id = CAST(:theme_id AS uuid)
              AND content_kind = 'text'
            """
        ),
        {"theme_id": theme_id},
    ).fetchall()
    ordered_rows: list[tuple[str, str, int]] = [
        (str(element_row[0]), str(element_row[1]), int(element_row[2]))
        for element_row in element_rows
    ]
    ordered_rows.sort(key=lambda row: (_BAND_RANK.get(row[1], 9), row[2], row[0]))
    element_ids: list[str] = [row[0] for row in ordered_rows]

    return element_ids
