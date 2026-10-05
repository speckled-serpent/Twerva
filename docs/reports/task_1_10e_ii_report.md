# Task 1.10e-ii — Measure text and reflow

*2026-10-04*

Leaf **1.10e-ii** only. Image files are **1.10e-iii** in the same
module. Overlap, samples, and the ops editor stay undone.

## Done

- `measure_theme_elements` in `apps/server/app/themes/measure.py`
  turns resolved text into a content height and calls
  `place_theme_elements`.
- Text wraps inside the content width: element width minus
  `element_margin` on the left and right.
- Family, size, bold, and weight (a bold or semibold cut when that
  file exists) change the measurement. A variable face can take a
  `wght` axis when it has one.
- Underline, strikethrough, and alignment do not change width or height.
- Empty text is one line of the face. A missing family uses the
  carousel fallback: DejaVu, then Liberation, then Pillow's default.
- After wrap, top reflows downward, bottom reflows upward from the
  lowest element, and middle recenters the whole block.

## Trade-offs

- Line height is the face's ascent plus descent. No extra leading is
  added, so decoration cannot change the box.
- A word wider than the content width stays on its own line.

## Next

- **1.10e-iii** is in this same change: image content height.
- **1.10f** overlap is not started.

## Scripts

- `apps/server/app/themes/measure.py`
- `apps/server/tests/test_theme_measure.py` (long string moves only the
  later top sibling, underline and strikethrough leave the layout
  unchanged, middle recenters, bottom grows upward)
