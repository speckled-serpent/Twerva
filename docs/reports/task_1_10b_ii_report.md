# Task 1.10b-ii — Theme element API

*2026-10-04*

Leaf **1.10b-ii** only. Duplicate, layout, measurement, and the ops
editor stay undone.

## Done

- `GET /api/v1/themes/{id}` includes `elements` ordered by band
  (`top`, `middle`, `bottom`) then `sort_order`.
- `POST /api/v1/themes/{theme_id}/elements`,
  `PATCH .../elements/{element_id}`, and `DELETE` on that path.
- Same admin write gate as theme create. Readers get 403.
- `sort_order` is 0-based within the band. The server compacts it after
  create, move, and delete.
- Unknown `text_source` values, `x` / `y` / `width`, and image refs that
  are not a relative svg, png, or jpeg path are rejected.
- A clear text element leaves `rectangle_color` null.

## Trade-offs

- Create and patch return the element. The theme GET is the ordered
  reload.
- Unknown sources and coordinate fields fail schema validation (422).
  A bad image path is HTTP 400.
- Compaction writes temporary negative sort orders, flushes, then writes
  0-based indexes so the unique key does not collide mid-update.

## Next

- **1.10c** duplicate.

## Scripts

- `apps/server/app/api/v1/theme_elements.py`
- `apps/server/app/themes/elements.py`
- `apps/server/tests/test_themes.py` (clear text, image, order, band
  move, rejected source)
