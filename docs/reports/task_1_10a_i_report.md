# Task 1.10a-i — Theme status

*2026-10-03*

Leaf **1.10a-i** only. Spacing, background, elements, the ops editor,
and Live inside `POST /api/v1/generate/carousel` stay undone.

## Done

- `ThemeStatus` (`draft`, `live`) as a native Postgres enum
  `theme_status`. `themes.status` is not null and defaults to `draft`.
- Alembic `themes_status` (parent `themes_create`) backfills every
  existing row, including Spotmu Paper v1 and Spotmu Bold v1, to
  `draft`. `themes_create` is unchanged.
- `ThemeReadResponse.status`. `PATCH /api/v1/themes/{id}` writes only
  fields present in the body. Status may move draft → live and live →
  draft. An explicit null status is HTTP 400. A missing theme is 404.
- `POST /api/v1/themes` ignores a `status` body (`extra=ignore`) and
  always stores `draft`.
- Same write gate as create: `require_authenticated_ops_operator` on
  the route, and the existing reader mutation check on `/api/v1`.
  Create Theme stays behind `useCanWriteOps`. No status editor.

## Trade-offs

- Both directions are allowed. There is no transition table.
- The ops console type includes `status`. The Themes screens do not
  edit it (that is 1.10h).
- Shipping generate still uses `carousel_template_v1`.

## Next

- **1.10a-ii** spacing columns on the same PATCH.
- **1.10a-iii** background columns and Live payload checks.

## Scripts

- `apps/server/alembic/versions/themes_status.py`
- `apps/server/tests/test_themes.py` (patch live, back to draft, GET,
  create-by-name stays draft)
