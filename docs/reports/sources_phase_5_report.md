# Sources v2 phase 5 — Theme pickers

*2026-10-14*

Leaf **S5** only. No migration.

## Done

- Picture backgrounds and image elements list albums from Sources, then
  units that have an image, then those images as thumbnails. Text-only
  units stay off the picker. A caption is the unit's free text, or its
  first field, and is not copied onto the theme.
- Choosing a thumbnail stores that image's `relative_path`. Shuffle
  stores a different path from the same album once. A later sample uses
  the stored path.
- A path that belongs to no unit stays "Saved image".
- `theme-defaults/` still resolves from the package. An `albums/…` path
  resolves under `ARTIFACT_STORAGE_DIR` for preview and theme samples.
- Delete protection already matches `background_asset_ref`,
  `image_asset_ref`, and artifact slide `asset_ref`. An uploaded album
  path on a theme is in use the same way as a packaged path.
- Readers see the list. The control has no upload.

## Trade-offs

- `POST /api/v1/generate/carousel` stays on the text template. Binding a
  Live theme into that route is a later slice.
- `GET /api/v1/themes/default-images` still returns the packaged Default
  catalog. The theme editor no longer uses it.

## Badger

No Alembic revision and no new env var. Restart `twerva-api` and the
ops console after sync. Uploaded images are already under
`ARTIFACT_STORAGE_DIR`. Packaged defaults stay in the app tree.

## Next

Sources v2 is done. The next open leaf on the task sheet is **1.10i-i**.

## Scripts

- `apps/ops/src/pages/themeAssets.ts`
- `apps/ops/src/pages/ThemeAssetAlbumField.tsx`
- `apps/ops/themeAssets.test.ts`
- `apps/server/tests/test_theme_default_images.py`
