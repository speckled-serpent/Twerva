# Sources v2 phase 4 — Resources

*2026-10-14*

Leaf **S4** only. The theme picker stays on the packaged Default list.

## Done

- Alembic `sources_resource_files` after `sources_default_album`.
  Table `resource_files`, one row per resource, keyed by `source_id`.
- `POST /api/v1/sources/resource` uploads one `.md` or `.txt` (2 MB)
  with a required provenance note. The bytes are stored unchanged at
  `resources/<source_id>/body.md` or `body.txt` under
  `ARTIFACT_STORAGE_DIR`.
- `PUT /api/v1/sources/{id}/resource` replaces the file. `PATCH` edits
  the name and the provenance note. `DELETE` removes the resource.
  `GET …/resource` streams the original bytes. `?download=1` asks the
  browser to save them.
- A PDF, a non-UTF-8 file, a file over 2 MB, or a blank note is 400
  and writes nothing.
- Markdown is rendered to HTML only after the text is escaped. A
  `javascript:` link stays text. The Sources page has Albums and
  Resources tabs. Readers can open the text and cannot upload.

## Trade-offs

- Album create stays JSON on `POST /api/v1/sources`. A resource needs
  the file, so create is `POST /api/v1/sources/resource`.
- The rendered HTML is computed when the resource is read. It is not
  stored. The download is the original upload.

## Badger

Migration id: `sources_resource_files`. From `apps/server`, run
`alembic upgrade head`, then restart `twerva-api`. No new env var.
The API creates `resources/` inside the existing `ARTIFACT_STORAGE_DIR`
(`/opt/twerva/artifacts` unless overridden). The service user must be
able to create directories and files there. `python-multipart` is
already in `requirements.txt`. Do not publish the directory.

## Next

- **S5** theme pickers.

## Scripts

- `apps/server/alembic/versions/sources_resource_files.py`
- `apps/server/app/sources/resource_store.py`
- `apps/server/app/sources/resource_files.py`
- `apps/server/app/sources/resource_markdown.py`
- `apps/server/app/api/v1/source_resources.py`
- `apps/server/tests/test_source_resources.py`
- `apps/ops/src/pages/ResourceViews.tsx`
