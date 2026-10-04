# Task 1.10b-i — Theme elements table

*2026-10-04*

Leaf **1.10b-i** only. Element HTTP, layout, wrap, ops, and upload stay
undone.

## Done

- Table `theme_elements` and model `app/models/theme_element.py`.
- `theme_id` references `themes` ON DELETE CASCADE. Unique
  (`theme_id`, `band`, `sort_order`).
- Enums: band `top` | `middle` | `bottom`; content kind `text` |
  `image`; text source `title`, `interest_heading`, `overview_bullets`,
  `canonical_url`; alignment `left` | `center` | `right`.
- Text columns, nullable `rectangle_color` (null means clear), nullable
  `image_asset_ref`, timestamps. No `x`, `y`, or `width`.
- Check: text requires source, family, positive size, color, and
  alignment. Booleans default false. `font_weight` is null or 1–1000.
  Image requires a relative asset ref (same path rules as
  `background_asset_ref`) and forbids `text_source`.
- Alembic `theme_elements` follows `themes_background`.

## Trade-offs

- The check SQL lives on the model and the migration imports it, so a
  clean upgrade and the ORM describe the same rule.
- A text row may still store a valid `image_asset_ref`. Image is the
  kind that requires one. Text does not have to clear it.
- `font_color` and `rectangle_color` are text. This leaf does not lock
  them to hex.

## Next

- **1.10b-ii** element HTTP.

## Scripts

- `apps/server/alembic/versions/theme_elements.py`
- `apps/server/app/models/theme_element.py`
- `apps/server/tests/test_models.py` (column map and content check)
- Clean database: `alembic upgrade head` through `theme_elements`
