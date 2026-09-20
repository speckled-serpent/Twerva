# Task — Carousel preview + Spotmu template iteration

*2026-09-20*

Operators could generate carousels but could not see the PNGs in ops or
pick among templates. This slice adds authenticated slide serving, a
restricted Spotmu template registry (paper + bold), generate/regenerate
with `template_id`, and ops preview/lightbox.

## Done

- **Slide images (auth):** `GET /api/v1/artifacts/{id}/slides/{index}/image`
  streams the PNG from `ARTIFACT_STORAGE_DIR` + `slides[index].asset_ref`.
  Missing artifact / index / file is **404**. No public unauthenticated
  access (401). Readers may GET via existing RBAC.
- **Template registry:** `spotmu_paper_v1` (current warm-paper look,
  default) and `spotmu_bold_v1` (dark ground, stronger teal, left stripe,
  left-aligned copy). Same 1080×1080 text-led rules. Listed at
  `GET /api/v1/generate/templates`.
- **Generate:** `POST /api/v1/generate/carousel` accepts optional
  `template_id`. Persisted on `artifacts.template_id` (nullable text).
- **Regenerate:** `POST /api/v1/artifacts/{id}/regenerate` (admin/write)
  creates a **new** draft from the same `source_item_id` / `cluster_id`
  (history kept, consistent with generate). Optional `template_id`;
  omitted uses the original, then paper.
- **Ops:** Queue and Sources show a horizontal preview strip (fetch +
  blob object URLs so the httpOnly cookie is sent). Template picker on
  generate; regenerate control on Queue drafts. Click a thumb for a
  simple lightbox. Readers view; writers generate/regenerate.
- Alembic **`artifact_template_id`** (parent `ops_users_role_rbac`).
- Tests: image 401/200 (plus reader GET), template list, generate with
  `template_id`, unknown template, paper vs bold pixels.

## Locked choices

| Topic | Choice |
|---|---|
| Storage | Local `ARTIFACT_STORAGE_DIR` (no S3) |
| Templates | Restricted Spotmu names only |
| Re-generate | New draft row (history kept) |
| `template_id` | Nullable text column on `artifacts` |
| Image GET | Session cookie; readers allowed |
| Health | Still starts without `DATABASE_URL` |

## Trade-offs

- Existing artifacts with `template_id` NULL render as paper if
  regenerated without an explicit id.
- Orphan PNGs still possible if commit fails after write (same as 1.4).
- Preview uses blob URLs (not raw `<img src>`) so the session cookie
  attaches even if the browser would omit it on a cross-origin img.

## Verified

- Server unit tests from `apps/server`: **175 collected, 13 persist skips**
  (no Postgres). Includes image 401/200, reader GET image, template list,
  generate `template_id`, reader generate 403, paper vs bold pixels,
  Alembic head `artifact_template_id`.
- `npm run build` in `apps/ops` (`tsc -b` + Vite `dist/`).
- Health-without-DB pattern unchanged (`GET /health` does not import
  generate/storage).

## Out of scope

- Freeform brand designer / Phase 3 templates
- S3 or public CDN URLs
- Replace-in-place regenerate

## Scripts / files touched

- `apps/server/app/generate/templates.py`, `carousel.py`, `service.py`,
  `errors.py`, `carousel_cli.py`
- `apps/server/app/storage/artifacts.py`, `app/models/artifact.py`
- `apps/server/alembic/versions/artifact_template_id.py`
- `apps/server/app/api/v1/generate.py`, `artifacts.py`, `schemas.py`
- `apps/server/tests/test_carousel_preview.py` (+ route / alembic /
  schema / persist / models)
- `apps/ops` preview strip, template picker, Sources / Queue
- `docs/planning/carousel_template_v1.md`, `docs/startup.md`,
  `apps/server/README.md`, this file

## Next

- Badger: `alembic upgrade head` to `artifact_template_id`, restart
  `twerva-api`, rebuild/copy ops `dist/`.
- Operators: generate with paper vs bold, confirm Queue lightbox, then
  regenerate a second draft to compare.
