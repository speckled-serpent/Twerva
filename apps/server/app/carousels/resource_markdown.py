"""Render a resource Markdown file as HTML. Raw HTML is escaped first.

Links are emitted only for http and https. A ``javascript:`` URL stays
text. This is the only HTML a resource view inserts.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable


_CODE_PATTERN: re.Pattern[str] = re.compile(r"`([^`\n]+)`")
_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_BOLD_PATTERN: re.Pattern[str] = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC_PATTERN: re.Pattern[str] = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def render_markdown_document(markdown_text: str) -> str:
    """Return HTML for one Markdown document. The input is escaped first.

    Args:
        markdown_text: The stored file, decoded as UTF-8.

    Returns:
        HTML that contains only tags this function inserts.
    """

    normalized_text: str = markdown_text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = normalized_text.split("\n")
    html_parts: list[str] = []
    index: int = 0

    while index < len(lines):
        line: str = lines[index]

        if line.startswith("```"):
            code_lines, index = _read_fence(lines, index + 1)
            escaped_code: str = html.escape("\n".join(code_lines), quote=True)
            html_parts.append(f"<pre><code>{escaped_code}</code></pre>")

            continue

        if line.strip() == "":
            index += 1

            continue

        heading_level: int | None = _heading_level(line)

        if heading_level is not None:
            heading_text: str = line[heading_level + 1:]
            html_parts.append(
                f"<h{heading_level}>{_inline(html.escape(heading_text, quote=True))}</h{heading_level}>",
            )
            index += 1

            continue

        if _is_list_item(line):
            list_lines, index = _read_while(lines, index, _is_list_item)
            html_parts.append(_render_list(list_lines))

            continue

        paragraph_lines, index = _read_paragraph(lines, index)
        paragraph_text: str = " ".join(paragraph_line.strip() for paragraph_line in paragraph_lines)
        html_parts.append(f"<p>{_inline(html.escape(paragraph_text, quote=True))}</p>")

    rendered_html: str = "".join(html_parts)

    return rendered_html


def _read_fence(lines: list[str], start_index: int) -> tuple[list[str], int]:
    """Return the lines inside a fence and the index after the closing fence."""

    code_lines: list[str] = []
    index: int = start_index

    while index < len(lines) and not lines[index].startswith("```"):
        code_lines.append(lines[index])
        index += 1

    if index < len(lines):
        index += 1

    return code_lines, index


def _heading_level(line: str) -> int | None:
    """Return 1–6 when the line is an ATX heading, else null."""

    level: int = 0

    while level < len(line) and line[level] == "#" and level < 6:
        level += 1

    if level == 0 or level >= len(line) or line[level] != " ":

        return None

    return level


def _is_list_item(line: str) -> bool:
    """True for a ``- ``, ``* ``, or ``1. `` item."""

    if line.startswith("- ") or line.startswith("* "):

        return True

    return _ordered_marker_length(line) is not None


def _ordered_marker_length(line: str) -> int | None:
    """Return the length of a ``12. `` prefix, or null."""

    digits: int = 0

    while digits < len(line) and line[digits].isdigit():
        digits += 1

    if digits == 0 or digits + 1 >= len(line):

        return None

    if line[digits:digits + 2] != ". ":

        return None

    return digits + 2


def _read_while(
    lines: list[str],
    start_index: int,
    predicate: Callable[[str], bool],
) -> tuple[list[str], int]:
    """Collect lines while ``predicate`` is true."""

    collected: list[str] = []
    index: int = start_index

    while index < len(lines) and predicate(lines[index]):
        collected.append(lines[index])
        index += 1

    return collected, index


def _read_paragraph(lines: list[str], start_index: int) -> tuple[list[str], int]:
    """Collect a paragraph until a blank line, heading, list, or fence."""

    collected: list[str] = []
    index: int = start_index

    while index < len(lines):
        line: str = lines[index]

        if line.strip() == "" or line.startswith("```") or _heading_level(line) is not None:
            break

        if _is_list_item(line) and len(collected) > 0:
            break

        collected.append(line)
        index += 1

    return collected, index


def _render_list(list_lines: list[str]) -> str:
    """Return a ul or ol for a run of items."""

    ordered: bool = _ordered_marker_length(list_lines[0]) is not None
    item_html: list[str] = []

    for list_line in list_lines:
        marker_length: int = 2

        if ordered:
            ordered_length: int | None = _ordered_marker_length(list_line)
            marker_length = 2 if ordered_length is None else ordered_length

        item_text: str = list_line[marker_length:]
        item_html.append(f"<li>{_inline(html.escape(item_text, quote=True))}</li>")

    tag: str = "ol" if ordered else "ul"
    list_html: str = f"<{tag}>{''.join(item_html)}</{tag}>"

    return list_html


def _inline(escaped_text: str) -> str:
    """Format code, links, and emphasis in text that is already escaped."""

    pieces: list[str] = []
    cursor: int = 0

    for code_match in _CODE_PATTERN.finditer(escaped_text):
        pieces.append(_emphasis_and_links(escaped_text[cursor:code_match.start()]))
        pieces.append(f"<code>{code_match.group(1)}</code>")
        cursor = code_match.end()

    pieces.append(_emphasis_and_links(escaped_text[cursor:]))
    inlined_html: str = "".join(pieces)

    return inlined_html


def _emphasis_and_links(escaped_text: str) -> str:
    """Apply links, then bold, then italic."""

    linked_text: str = _LINK_PATTERN.sub(_replace_link, escaped_text)
    bold_text: str = _BOLD_PATTERN.sub(r"<strong>\1</strong>", linked_text)
    italic_text: str = _ITALIC_PATTERN.sub(r"<em>\1</em>", bold_text)

    return italic_text


def _replace_link(match: re.Match[str]) -> str:
    """Emit an anchor only for an http or https URL."""

    label: str = match.group(1)
    url: str = match.group(2)

    if url.startswith("http://") or url.startswith("https://"):
        return f'<a href="{url}" rel="noopener noreferrer">{label}</a>'

    return match.group(0)
