"""CLI: generate a carousel draft from a SourceItem id (1.4e-ii).

Run from ``apps/server`` with ``DATABASE_URL`` set:

    python -m app.generate.carousel_cli <source_item_id>
    python -m app.generate.carousel_cli <source_item_id> --cluster-id <uuid>
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.generate.errors import CarouselGenerateError


def main(argv: list[str] | None = None) -> int:
    """Render and persist one carousel Artifact from a SourceItem.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success).
    """

    argument_parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Generate a draft carousel Artifact from an existing SourceItem. "
            "Each run inserts a new row (history kept)."
        ),
    )
    argument_parser.add_argument(
        "source_item_id",
        help="SourceItem UUID to generate from.",
    )
    argument_parser.add_argument(
        "--cluster-id",
        default=None,
        help="Optional Cluster UUID to stamp on the Artifact.",
    )
    argument_parser.add_argument(
        "--storage-dir",
        default=None,
        help="Override ARTIFACT_STORAGE_DIR (local PNG root).",
    )
    argument_parser.add_argument(
        "--template-id",
        default=None,
        help="Restricted Spotmu template (default spotmu_paper_v1).",
    )
    parsed_arguments: argparse.Namespace = argument_parser.parse_args(argv)
    source_item_identifier: uuid.UUID = _parse_uuid_argument(
        parsed_arguments.source_item_id,
        "source_item_id",
    )
    cluster_identifier: uuid.UUID | None = None

    if parsed_arguments.cluster_id is not None:
        cluster_identifier = _parse_uuid_argument(
            parsed_arguments.cluster_id,
            "cluster_id",
        )

    storage_directory: Path | None = None

    if parsed_arguments.storage_dir is not None:
        storage_directory = Path(parsed_arguments.storage_dir)

    from app.db import SessionLocal
    from app.generate.service import generate_carousel_artifact_draft

    our_database_session: Session = SessionLocal()

    try:
        created_artifact = generate_carousel_artifact_draft(
            source_item_identifier,
            our_database_session,
            cluster_id=cluster_identifier,
            artifact_storage_directory=storage_directory,
            template_id=parsed_arguments.template_id,
        )
        our_database_session.commit()
        our_database_session.refresh(created_artifact)
    except CarouselGenerateError as generate_error:
        our_database_session.rollback()
        print(str(generate_error), file=sys.stderr)

        return 1
    finally:
        our_database_session.close()

    slide_count: int = 0

    if created_artifact.slides is not None:
        slide_count = len(created_artifact.slides)

    print(f"Artifact id={created_artifact.id} status={created_artifact.status.value}")
    print(f"format={created_artifact.format} slides={slide_count}")
    print(f"cta_url={created_artifact.cta_url}")
    print(f"caption={created_artifact.caption}")

    return 0


def _parse_uuid_argument(raw_value: str, argument_name: str) -> uuid.UUID:
    """Parse a CLI UUID or exit with a clear error."""

    try:
        parsed_uuid: uuid.UUID = uuid.UUID(raw_value)
    except ValueError as value_error:
        raise SystemExit(f"Invalid {argument_name}: {raw_value}") from value_error

    return parsed_uuid


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
