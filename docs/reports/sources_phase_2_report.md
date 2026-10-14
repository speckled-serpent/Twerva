# Sources v2 phase 2 — Albums and units in ops

*2026-10-14*

Leaf **S2** only. No migration. Upload, URL import, thumbnails, the
Resources tab, and the theme picker stay undone.

## Done

- Write API on the existing sources router. Readers may GET. Admins
  may create and rename albums, create and edit units (free text,
  tags, labeled fields), and edit license, source, alt, and note on
  an image that already exists.
- An empty unit, a half-filled field, a blank image source, and
  `licensed` with no note are 400 and write nothing. A license outside
  the allowlist is rejected by the request model.
- Delete of an image, unit, or album is 409 while a theme background,
  a theme image element, or an artifact slide stores that path. The
  in-use check runs before the empty-unit check, so a Default image
  a theme stores returns 409 and the row stays.
- `GET …/images/{image_id}/file` streams an existing file.
  `theme-defaults/` is read from the package resolver. No new bytes.
- Ops Sources page: album list, album view with a units grid, and a
  unit editor. The grid uses the file route for a packaged JPEG.
  Admin writes. Reader reads. No upload or URL import control.

## Trade-offs

- An unknown license is HTTP 422 from request validation, the same
  way other enums in this API fail. Blank source and a missing
  license note are 400 from the handler, before the row changes.
- Slug is chosen at create and stays put when the album is renamed.
  A second album with the same name gets a `-2` slug.
- `resource` is still on the kind enum. Creating one is 400 until
  phase 4.
- The theme editor still uses the hard-coded Default catalog.

## Next

- **S3** image intake: disk storage, multipart upload, URL import,
  and thumbnails.

## Scripts

- `apps/server/app/sources/editing.py`
- `apps/server/app/api/v1/source_writes.py`
- `apps/server/app/api/v1/sources.py`
- `apps/server/app/api/v1/schemas.py`
- `apps/server/tests/test_source_writes.py`
- `apps/ops/src/pages/SourcesPage.tsx`
