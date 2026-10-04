# Task 1.10d-i — Layout math

*2026-10-04*

Leaf **1.10d-i** only. Measurement, overlap, samples, and the ops
editor stay undone. Letter 1.10d is this one leaf.

## Done

- `place_theme_elements` in `apps/server/app/themes/layout.py` places
  elements that already have a content height.
- The content area is the 1080×1080 frame inset by `page_margin` on
  every edge. Each element uses that left edge and that width.
- Element height is content height plus `element_margin` above and
  below. `element_gap` sits only between rectangles in the same band.
- Top stacks downward from the top page margin. Bottom stacks upward
  from the bottom page margin, first element lowest. Middle is one
  block centered in the content area; an odd leftover pixel goes below
  the block.
- An empty band adds no rectangles. Zero elements returns the content
  area and no rectangles. Bands do not push each other.

## Trade-offs

- The function takes frame width and height so the inset is computed
  from the call, and carousel callers pass 1080×1080.
- It sorts within each band by `sort_order`. It does not clamp a block
  that is taller than the content area, and it does not report overlap.

## Next

- **1.10e** measure text and images.

## Scripts

- `apps/server/app/themes/layout.py`
- `apps/server/tests/test_theme_layout.py` (single top, two top with
  gap only between them, two bottom stacking upward, three middle
  centered as a group, one-band theme, zero elements)
