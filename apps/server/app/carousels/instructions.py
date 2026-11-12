"""Join a carousel's instruction documents into one draft prompt.

Phase 6 should use this same join for the instructions button.
"""

from __future__ import annotations


def instruction_prompt_text(bodies: list[str]) -> str:
    """Join instruction bodies that already are in position order.

    A body that strips to empty is dropped. The rest are joined with a
    blank line. No documents, or only blank bodies, is an empty string.
    That empty string is what both guidance columns being ``""`` does
    today when it is passed as inspiration.

    Args:
        bodies: Document bodies, already in position order.

    Returns:
        The inspiration string for the slide draft. Rules stay empty
        at the call site.
    """

    kept_bodies: list[str] = [
        body for body in bodies if body.strip() != ""
    ]
    prompt_text: str = "\n\n".join(kept_bodies)

    return prompt_text
