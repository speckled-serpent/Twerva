# Task 1.10e-iii — Measure images on disk

*2026-10-04*

Leaf **1.10e-iii**. Text wrap is **1.10e-ii** in the same module.
Overlap, samples, and the ops editor stay undone.

## Done

- An image's content width is the frame's content width. Content
  height keeps the file's aspect ratio. `place_theme_elements` then
  adds element margin and places the band.
- PNG and JPEG sizes come from Pillow. SVG sizes come from the stdlib
  XML parser: `width` and `height` when both parse, otherwise
  `viewBox`. No SVG library.
- `image_asset_ref` is resolved under `ARTIFACT_STORAGE_DIR`. A path
  that escapes the store is rejected.
- A missing or unreadable file is a `MeasureProblem` for that element
  and adds no rectangle. The size is not guessed.

## Trade-offs

- Scaled height rounds to the nearest pixel. The tests use ratios that
  divide evenly.
- A failed image is omitted from the layout so it does not reserve space.

## Next

- **1.10f** overlap.

## Scripts

- `apps/server/app/themes/measure.py`
- `apps/server/tests/test_theme_measure.py` (200×50 PNG and JPEG at
  content width 1000 are 250px tall, a 4×2 SVG viewBox is 500px, a
  missing file returns `missing_asset` and no rectangle)
