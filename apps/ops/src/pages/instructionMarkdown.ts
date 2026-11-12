/**
 * Render the instruction marks used by the sample template.
 *
 * HTML is escaped. ATX headings (`#`, `##`, `###`), paragraphs, unordered
 * lists, and `**strong**` / `*emphasis*` are rendered. Other marks stay text.
 *
 * @param source - Markdown or plain text
 * @returns HTML safe to insert after that escaping
 */
export function renderInstructionMarkdown(source: string): string {

  const lines: string[] = source.split("\n");
  const blocks: string[] = [];
  let index: number = 0;

  while (index < lines.length) {
    const line: string = lines[index] ?? "";

    if (line.trim() === "") {
      index += 1;
      continue;
    }

    const heading: HeadingMatch | null = headingMatch(line);

    if (heading !== null) {
      blocks.push(
        `<h${heading.level}>${renderInline(heading.text)}</h${heading.level}>`,
      );
      index += 1;
      continue;
    }

    if (line.startsWith("- ")) {
      const items: string[] = [];

      while (index < lines.length && (lines[index] ?? "").startsWith("- ")) {
        items.push(`<li>${renderInline((lines[index] ?? "").slice(2))}</li>`);
        index += 1;
      }

      blocks.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    const paragraphLines: string[] = [];

    while (index < lines.length && isParagraphLine(lines[index] ?? "")) {
      paragraphLines.push(renderInline(lines[index] ?? ""));
      index += 1;
    }

    blocks.push(`<p>${paragraphLines.join("<br>")}</p>`);
  }

  return blocks.join("");
}

interface HeadingMatch {
  level: number;
  text: string;
}

function headingMatch(line: string): HeadingMatch | null {

  const matched: RegExpMatchArray | null = /^(#{1,3})\s+(\S.*)$/.exec(line);

  if (matched === null) {
    return null;
  }

  const marks: string = matched[1] ?? "";
  const text: string = matched[2] ?? "";
  const heading: HeadingMatch = {
    level: marks.length,
    text,
  };

  return heading;
}

function isParagraphLine(line: string): boolean {

  if (line.trim() === "") {
    return false;
  }

  if (line.startsWith("- ")) {
    return false;
  }

  if (headingMatch(line) !== null) {
    return false;
  }

  return true;
}

function renderInline(text: string): string {

  const escaped: string = escapeHtml(text);
  const withStrong: string = escaped.replace(
    /\*\*(.+?)\*\*/g,
    "<strong>$1</strong>",
  );
  const withEmphasis: string = withStrong.replace(
    /\*(.+?)\*/g,
    "<em>$1</em>",
  );

  return withEmphasis;
}

function escapeHtml(text: string): string {

  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
