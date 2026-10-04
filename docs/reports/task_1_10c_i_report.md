# Task 1.10c-i — Duplicate a theme

*2026-10-04*

Leaf **1.10c-i** only. Layout, measurement, samples, and the ops
button stay undone. Letter 1.10c is this one leaf.

## Done

- `POST /api/v1/themes/{id}/duplicate` creates a new row.
- Status is `draft`. Name is `Copy of {name}`. Slug uses the existing
  slug helper. `template_key` is null.
- Spacing, background, and every element are copied. Element ids are
  new. Band, order, and content match the source.
- The source row keeps its status, ids, and `updated_at`.
- Same admin write gate as theme create. Readers get 403.

## Trade-offs

- The gradient object is deep-copied so a later edit of the Draft does
  not change the source JSON.
- `created_by` on the copy is the operator who duplicated it.

## Next

- **1.10d** layout math.

## Scripts

- `apps/server/app/api/v1/themes.py`
- `apps/server/tests/test_themes.py` (Live gradient theme, two elements,
  source unchanged, copy is Draft, element ids differ)
