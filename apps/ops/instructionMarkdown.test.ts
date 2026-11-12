import assert from "node:assert/strict";

import { renderInstructionMarkdown } from "./src/pages/instructionMarkdown.ts";
import { INSTRUCTION_SAMPLE_TEMPLATE } from "./src/pages/instructionTemplate.ts";

assert.equal(
  renderInstructionMarkdown("<script>alert(1)</script>"),
  "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>",
);
assert.equal(renderInstructionMarkdown("# What this is"), "<h1>What this is</h1>");
assert.equal(renderInstructionMarkdown("## Voice"), "<h2>Voice</h2>");
assert.equal(renderInstructionMarkdown("### Smaller"), "<h3>Smaller</h3>");
assert.equal(renderInstructionMarkdown("#### Not a heading"), "<p>#### Not a heading</p>");
assert.equal(
  renderInstructionMarkdown("One idea.\n\nAnother."),
  "<p>One idea.</p><p>Another.</p>",
);
assert.equal(
  renderInstructionMarkdown("- The claim\n- A fact"),
  "<ul><li>The claim</li><li>A fact</li></ul>",
);
assert.equal(
  renderInstructionMarkdown("Use **strong** and *emphasis*."),
  "<p>Use <strong>strong</strong> and <em>emphasis</em>.</p>",
);
assert.equal(renderInstructionMarkdown("Tom & Jerry"), "<p>Tom &amp; Jerry</p>");

const sampleHtml: string = renderInstructionMarkdown(INSTRUCTION_SAMPLE_TEMPLATE);
assert.match(sampleHtml, /<h1>What this carousel is for<\/h1>/);
assert.match(sampleHtml, /<h2>Voice<\/h2>/);
assert.match(sampleHtml, /<h2>Include<\/h2>/);
assert.match(sampleHtml, /<h2>Leave out<\/h2>/);
assert.match(sampleHtml, /<li>The claim this carousel makes<\/li>/);
assert.match(sampleHtml, /<li>Anything this carousel should not say<\/li>/);
assert.equal(sampleHtml.includes("<script"), false);
