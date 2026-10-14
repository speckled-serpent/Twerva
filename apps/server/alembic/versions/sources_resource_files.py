"""Add the one file stored on a resource source.

Revision ID: sources_resource_files
Revises: sources_default_album
Create Date: 2026-10-14

Table ``resource_files``. One row per resource, keyed by ``source_id``.
The path is ``resources/<source_id>/body.md`` or ``body.txt``. Does not
rewrite albums, units, or themes.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

import sqlalchemy as sa

from app.models.content_source import (
    RESOURCE_FILE_BYTE_SIZE_CHECK_SQL,
    RESOURCE_FILE_FILENAME_CHECK_SQL,
    RESOURCE_FILE_PATH_CHECK_SQL,
    RESOURCE_FILE_PROVENANCE_CHECK_SQL,
)


revision: str = "sources_resource_files"
down_revision: str | None = "sources_default_album"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PRIMARY_KEY: postgresql.UUID = postgresql.UUID(as_uuid=True)
RESOURCE_FILE_MEDIA_TYPE_ENUM: postgresql.ENUM = postgresql.ENUM(
    "markdown",
    "plain",
    name="resource_file_media_type",
    create_type=False,
)


def upgrade() -> None:

    op.execute(
        sa.text(
            "CREATE TYPE resource_file_media_type AS ENUM ('markdown', 'plain')"
        ),
    )
    op.create_table(
        "resource_files",
        sa.Column("source_id", UUID_PRIMARY_KEY, nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("media_type", RESOURCE_FILE_MEDIA_TYPE_ENUM, nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_resource_files_source_id_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_id", name="pk_resource_files"),
        sa.UniqueConstraint(
            "relative_path",
            name="uq_resource_files_relative_path",
        ),
        sa.CheckConstraint(
            RESOURCE_FILE_PROVENANCE_CHECK_SQL,
            name="ck_resource_files_provenance",
        ),
        sa.CheckConstraint(
            RESOURCE_FILE_FILENAME_CHECK_SQL,
            name="ck_resource_files_original_filename",
        ),
        sa.CheckConstraint(
            RESOURCE_FILE_BYTE_SIZE_CHECK_SQL,
            name="ck_resource_files_byte_size",
        ),
        sa.CheckConstraint(RESOURCE_FILE_PATH_CHECK_SQL, name="ck_resource_files_path"),
    )


def downgrade() -> None:

    op.drop_table("resource_files")
    op.execute(sa.text("DROP TYPE resource_file_media_type"))
