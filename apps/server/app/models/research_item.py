"""One research document: a title, a slug, and a body of text.

A research item does not hold several documents. The body is Markdown
or plain text stored in the row. There is no file upload. A carousel
does not point at this row until the Content step.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


RESEARCH_BODY_MAX_CHARACTERS: int = 1_000_000
RESEARCH_SLUG_FALLBACK: str = "research"
RESEARCH_TITLE_CHECK_SQL: str = "btrim(title) <> '' AND btrim(slug) <> ''"
RESEARCH_BODY_CHECK_SQL: str = (
    f"char_length(body) <= {RESEARCH_BODY_MAX_CHARACTERS}"
)


def count_research_words(body: str) -> int:
    """Return how many whitespace-separated words are in a body.

    Args:
        body: The stored document, including Markdown marks.

    Returns:
        The word count. An empty body is zero.
    """

    words: list[str] = body.split()

    return len(words)


class ResearchItem(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in ``research_items``. One document."""

    __tablename__ = "research_items"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_research_items_slug"),
        CheckConstraint(RESEARCH_TITLE_CHECK_SQL, name="title"),
        CheckConstraint(RESEARCH_BODY_CHECK_SQL, name="body"),
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
