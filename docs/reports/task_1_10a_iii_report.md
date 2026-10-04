# Task 1.10a-iii — Theme background

*2026-10-04*

Leaf **1.10a-iii** only. Elements, rendering, and upload stay undone.
With **1.10a-i** and **1.10a-ii**, letter 1.10a is complete.

## Done

- Columns on `themes`: `background_kind` (`picture`, `color`, `gradient`,
  `texture`), nullable `background_color`, nullable `background_gradient`
  JSONB, nullable `background_asset_ref`.
- Default kind `color`, color `#F6F1E8`, gradient null, asset ref null.
  Alembic `themes_background` backfills existing rows, including Spotmu
  Paper v1 and Spotmu Bold v1.
- Gradient shape is locked on `ThemeGradient`: `angle_deg` 0 through 360,
  at least two stops, each `offset` 0 through 1 and a `#` plus six hex
  digits color.
- Asset ref is a relative path with no `..` and no scheme, suffix
  `.svg`, `.png`, `.jpg`, or `.jpeg`.
- The same partial PATCH writes only fields that are present. Draft may
  save a kind with that payload empty. Live, whether this patch sets it
  or the row is already Live, requires the payload for the kind.
- Name-only create ignores a background body and stores the paper color.

## Trade-offs

- Other payload columns are left in place when the kind changes. Live
  checks only the active kind.
- Invalid shapes are HTTP 400 from the handler. Unknown enum values stay
  schema 422.
- No drawing and no file upload.

## Next

- **1.10b** element rows.

## Scripts

- `apps/server/alembic/versions/themes_background.py`
- `apps/server/app/themes/background.py`
- `apps/server/tests/test_themes.py` (each kind round-trip, Live blank
  color is 400, Draft picture with a null ref saves)
