"""CLI: fetch one Spotmu interest by slug and upsert it (1.3c-iii).

Run from ``apps/server`` with ``DATABASE_URL`` set:

    python -m app.ingest.spotmu_interest ai-agents
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from app.ingest.spotmu import (
    SpotmuInterestFetch,
    fetch_spotmu_interest_by_slug,
    resolve_spotmu_api_base_url,
)
from app.ingest.upsert import (
    UpsertSpotmuInterestResult,
    upsert_spotmu_interest_source_item,
)


def main(argv: list[str] | None = None) -> int:
    """Fetch one slug from Spotmu and upsert Brand ``spotmu`` / SourceItem.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success).
    """

    argument_parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Fetch one public Spotmu interest by slug and upsert it into "
            "source_items under Brand spotmu."
        ),
    )
    argument_parser.add_argument(
        "slug",
        help="Spotmu interest slug (for example ai-agents).",
    )
    argument_parser.add_argument(
        "--base-url",
        default=None,
        help="Override SPOTMU_API_BASE_URL (default https://spotmu.com).",
    )
    parsed_arguments: argparse.Namespace = argument_parser.parse_args(argv)
    interest_slug: str = parsed_arguments.slug
    api_base_url: str | None = parsed_arguments.base_url
    resolved_api_base_url: str = resolve_spotmu_api_base_url(api_base_url)
    fetched_interest: SpotmuInterestFetch = fetch_spotmu_interest_by_slug(
        interest_slug,
        api_base_url=resolved_api_base_url,
    )

    from app.db import SessionLocal

    our_database_session: Session = SessionLocal()

    try:
        upsert_result: UpsertSpotmuInterestResult = (
            upsert_spotmu_interest_source_item(
                fetched_interest,
                our_database_session,
            )
        )
        our_database_session.commit()
        our_database_session.refresh(upsert_result.source_item)
        our_database_session.refresh(upsert_result.brand)
    finally:
        our_database_session.close()

    source_item_verb: str = "created" if upsert_result.created else "updated"
    print(
        f"Brand slug=spotmu id={upsert_result.brand.id}",
    )
    print(
        f"SourceItem slug={fetched_interest.slug} "
        f"id={upsert_result.source_item.id} ({source_item_verb})",
    )
    print(f"canonical_url={fetched_interest.canonical_url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
