# Sources v2 phase 1 — Model and Default

*2026-10-14*

Leaf **S1** only. Ops pages, upload, URL import, thumbnails, resources,
the theme picker, and write or delete routes stay undone.

## Done

- Alembic `sources_default_album` (parent `themes_element_rectangle`).
  Tables `sources`, `units`, `unit_fields`, and `unit_images`. Native
  enums for kind, media type, license, and intake. `units.tags` is a
  text array. `themes_element_rectangle` is unchanged.
- Upgrade seeds album Default, slug `default`, as six image-only units.
  Each `relative_path` stays `theme-defaults/<filename>`. License is
  `cc0` or `public_domain` and `source` is the URL in
  `default_images/LICENSES.md`. Bytes stay in the package.
- `GET /api/v1/sources?kind=album` and `GET /api/v1/sources/{id}`.
  Readers may GET through the existing ops gate. No write routes.
- A clean Postgres database upgrades to `sources_default_album`,
  downgrades, and upgrades again. Seeded theme rows keep a null
  `background_asset_ref`.

## Trade-offs

- The theme editor still uses the hard-coded Default catalog. The new
  rows are readable through the API and do not replace that picker.
- `resource` is on the kind enum so phase 4 does not rewrite it. No
  `resource_files` table yet.
- An empty unit is not rejected in the database. Phase 2 rejects it
  on write.

## Next

- **S2** album and unit management in ops, including the write API.

## Scripts

- `apps/server/alembic/versions/sources_default_album.py`
- `apps/server/app/models/content_source.py`
- `apps/server/app/sources/default_album.py`
- `apps/server/app/api/v1/sources.py`
- `apps/server/tests/test_sources.py`

## Tests

`python -m unittest discover -s tests` from `apps/server`: 352 tests,
OK, 16 skipped. A local Postgres 16 upgrade of a clean database
reached `sources_default_album` and returned the six paths and licenses.
