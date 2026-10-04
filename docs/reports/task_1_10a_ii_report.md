# Task 1.10a-ii — Theme spacing

*2026-10-04*

Leaf **1.10a-ii** only. Background, elements, layout math, drawing, and
the ops editor stay undone.

## Done

- Integer columns `page_margin`, `element_gap`, and `element_margin` on
  `themes`. One value each, applied on every edge. Defaults **96 / 0 / 0**.
  Not null.
- Alembic `themes_spacing` (parent `themes_status`) backfills every
  existing row, including Spotmu Paper v1 and Spotmu Bold v1, to those
  defaults.
- The same partial `PATCH /api/v1/themes/{id}` accepts any of the three.
  A negative is HTTP 400 and does not write. `ThemeReadResponse`
  includes them.
- Name-only `POST /api/v1/themes` ignores a spacing body and stores
  96 / 0 / 0. Same write gate as before. No spacing editor in ops.

## Trade-offs

- Zero is allowed. The database does not add a check constraint; the
  API returns 400.
- Create does not take spacing. Operators change it with PATCH.
- No layout math. The columns are stored values only.

## Next

- **1.10a-iii** background kind and payload, including the Live check.

## Scripts

- `apps/server/alembic/versions/themes_spacing.py`
- `apps/server/tests/test_themes.py` (non-default triple, GET, `-1` is
  400, name-only create reads 96 / 0 / 0)
