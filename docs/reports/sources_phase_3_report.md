# Sources v2 phase 3 — Image intake

*2026-10-14*

Leaf **S3** only. No migration. Resources and the theme picker stay
undone.

## Done

- Local `save`, `open`, and `delete` for album images under
  `ARTIFACT_STORAGE_DIR` at
  `albums/<source_id>/<unit_id>/<image_id>.<ext>`. Thumbnails are
  `…/<image_id>-thumb.jpg`. `theme-defaults/` stays in the package.
  `delete` does not touch it.
- `POST /api/v1/sources/{id}/units/{unit_id}/images` accepts one or
  more files plus license, source, optional alt, and a license note.
  `POST …/images/import` downloads one http(s) URL once. SVG, PNG, or
  JPEG, 8 MB. Raster images get a JPEG thumbnail, longest edge 480.
  SVG has no thumbnail.
- A missing license, a blank source, `licensed` with no note, a bad
  type, or a file over 8 MB is rejected before any row or file is
  written. Provenance is `unit_images.source`. A URL import sets
  `intake` to `url` and records that source; the editor defaults the
  source to the URL.
- The unit editor can upload and import. The grid uses the thumbnail
  when `thumbnail_path` is set. The theme picker is still the
  hard-coded Default list.
- `python-multipart` is in `requirements.txt` so FastAPI can read the
  upload form.

## Trade-offs

- No new column for a download URL separate from provenance. The
  source field holds the provenance, and a URL import prefills it
  with the URL.
- Link-local, unspecified, and multicast addresses are refused.
  Other http(s) URLs, including loopback, are fetched. Import is
  admin-only. Redirects are not followed.
- An unknown license on the JSON import is HTTP 422, matching the
  other enums. A missing note is 400.

## Badger

No migration. No new directory and no new env var. The API user must
be able to create folders inside the existing `ARTIFACT_STORAGE_DIR`
(`/opt/twerva/artifacts` unless overridden). The process creates
`albums/` itself. Outbound http(s) is required for URL import. After
sync, `pip install -r requirements.txt` so `python-multipart` is in
the venv, then restart `twerva-api`. Disk grows by each original plus
a JPEG thumbnail.

## Next

- **S4** resources: Markdown and TXT upload.

## Scripts

- `apps/server/app/sources/image_store.py`
- `apps/server/app/sources/image_intake.py`
- `apps/server/app/api/v1/source_intake.py`
- `apps/server/requirements.txt`
- `apps/server/tests/test_source_intake.py`
- `apps/ops/src/pages/SourcesPage.tsx`
