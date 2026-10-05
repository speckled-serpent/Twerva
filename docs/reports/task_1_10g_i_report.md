# Task 1.10g-i — Generate samples

*2026-10-05*

Leaf **1.10g-i** only. The ops editor stays undone.
Letter 1.10g is this one leaf.

## Done

- `POST /api/v1/themes/{id}/samples` takes `{source_item_id}` and renders one frame. Overview bullets stay one text block. Slide roles from `carousel_template_v1` are not read.
- The source item must be `source_type=spotmu_interest`. Anything else is 400.
- The frame is resolved, measured, placed, and overlap-checked. Pillow writes `{ARTIFACT_STORAGE_DIR}/theme-previews/{theme_id}/{preview_id}.png`. `GET /api/v1/themes/{theme_id}/samples/{preview_id}/image` streams it for a signed-in operator.
- The background fills the frame: solid color, a linear gradient (0° toward the top, 90° toward the right, no radial), or a picture or texture scaled to cover with no tiling. Each element rectangle is drawn next (skipped when `rectangle_color` is null), then its content.
- Overlap still writes the PNG. The response sets `blocked` true, `block_reason` `overlap`, and the overlap payload.
- A missing picture, texture, or image file sets `blocked` true and `block_reason` `missing_asset`, and does not invent a fill. `block_reason` is otherwise null, `measure_error`, with `detail`.
- Draft and Live both render. Theme status is unchanged. No artifact row and no post job row are inserted.

## Trade-offs

- Reason priority is missing asset, then measure error, then overlap. Overlap pairs are still returned when another reason wins.
- An SVG image element is measured and its rectangle is drawn. The vectors are not rasterized, because there is no SVG library. A readable SVG is not a measure error. An SVG background cannot be painted, so that frame is `measure_error` and stays transparent.
- Picture and texture share one cover scale.

## Next

- **1.10h** ops editor.

## Scripts

- `apps/server/app/themes/samples.py`
- `apps/server/app/api/v1/theme_samples.py`
- `apps/server/app/themes/measure.py` (public face, wrap, and width helpers used by the renderer)
- `apps/server/tests/test_theme_samples.py` (preview file and no artifact or post job; colliding layout returns `blocked` true and `block_reason` `overlap`)
