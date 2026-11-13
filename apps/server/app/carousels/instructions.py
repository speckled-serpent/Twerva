"""Join a carousel's instruction documents into one draft prompt.

``collection_prompt_text`` uses this same join for the instructions section.
"""

from __future__ import annotations


def instruction_prompt_text(bodies: list[str]) -> str:
    """Join instruction bodies that already are in position order.

    A body that strips to empty is dropped. The rest are joined with a
    blank line. No documents, or only blank bodies, is an empty string.

    Args:
        bodies: Document bodies, already in position order.

    Returns:
        The inspiration string for the slide draft. The rules argument
        at the call site stays empty.
    """

    kept_bodies: list[str] = [
        body for body in bodies if body.strip() != ""
    ]
    prompt_text: str = "\n\n".join(kept_bodies)

    return prompt_text
