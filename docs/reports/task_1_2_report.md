# Task 1.2 (interim) — 1.2b–1.2k domain schema

*2026-09-15*

1.2a is merged. This note covers **1.2b through 1.2k** only. **1.2l**
(HTTP CRUD) and **1.2m** (seed) are not started.

## Done

- **1.2b** Shared `StrEnum`s + native Postgres ENUM types. UUID PK
  convention: Postgres `UUID` + `gen_random_uuid()` (package docstring on
  `app.models`). Transitions and reserved `SourceType` values:
  `docs/planning/domain_statuses.md`.
- **1.2c–1.2j** SQLAlchemy models: `Brand`, `SourceItem`, `Cluster` +
  `cluster_source_items`, `Account`, `Artifact`, `PostJob`,
  `MetricSnapshot`, `SteerAction`. No OAuth columns. No API routes.
- **1.2k** Single Alembic revision `12bk_domain_schema` creates all
  tables, enums, FK/query indexes, and the partial unique index on
  `source_items`.

`GET /health` still does not import models or `app.db`.

## Revision id and apply commands (1.2k-iii)

**Revision:** `12bk_domain_schema` (first head; `down_revision` is empty).

Live SSH `alembic upgrade` on `twerva-server` is **not** required for this
PR. Production deploy, migrate, and rollback: [`docs/ops/deploy.md`](../ops/deploy.md).
Apply later from `apps/server` with the on-box URL:

```bash
set -a
source /opt/twerva/database_url.env
set +a
cd /path/to/Twerva/apps/server
alembic heads
alembic upgrade head
alembic current
```

Expected `alembic current` after upgrade: `12bk_domain_schema (head)`.

Local equivalent:

```bash
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
cd apps/server
alembic upgrade head
```

`alembic upgrade head` must be clean on an empty database (this revision
is the first).

## Locked choices

| Topic | Choice |
|---|---|
| UUID PKs | DB-generated `gen_random_uuid()`; `pgcrypto` enabled in the revision |
| Enums | Native Postgres ENUM (not check-constrained text) |
| 1.2e-ii | `cluster_source_items` ships; composite PK is the unique pair |
| 1.2f-ii | Unique (`platform`, `handle`) |
| 1.2i-i | Many snapshots per job; latest `captured_at` wins; no unique on `post_job_id` |
| Model names | Task-sheet names (`Brand`, …), not style-guide `OurBrands` |

## Trade-offs

- Steer `action` is ENUM `steer_action_type` instead of a CHECK on text
  so the schema has one closed-vocab style.
- `brand_product` / `editorial_brief` exist on `source_type` but have no
  ingest path.
- `updated_at` uses ORM `onupdate`; raw SQL updates do not bump it (no
  trigger in MVP).
- Live EC2 apply is documented, not executed in this slice.

## Verified

- `python -m unittest discover -s tests` (24 tests) — health without URL,
  fail-fast settings, engine/session, model metadata/indexes/enums,
  Alembic revision `12bk_domain_schema`.
- `GET /health` via uvicorn **without** `DATABASE_URL` → `200` `{"status":"ok"}`.
- `alembic upgrade head` on empty local Postgres 16 → clean;
  `alembic current` → `12bk_domain_schema (head)`.
- `alembic downgrade base` then `upgrade head` again — clean.
- Partial unique index: `WHERE (external_key IS NOT NULL)`.
- ORM round-trip: Brand → SourceItem → Cluster + join → Account →
  Artifact → PostJob → two MetricSnapshots (latest views wins) →
  SteerAction. UUID PKs assigned by `gen_random_uuid()`.
- Live `alembic upgrade` on `twerva-server` **not** run (1.2k-iii
  documented only).

## Out of scope (as specified)

- No FastAPI CRUD / Pydantic schemas (1.2l)
- No seed data (1.2m)
- No OAuth token columns
- No 1.3+ ingest, generate, publish, or ops UI

## Scripts touched

- `apps/server/app/models/` (`base`, `enums`, domain modules, package)
- `apps/server/app/db.py` (imports `Base` from the models package)
- `apps/server/alembic/env.py` (imports `app.models`, not only `Base`)
- `apps/server/alembic/versions/12bk_domain_schema.py`
- `apps/server/alembic/README`, `apps/server/README.md`
- `apps/server/tests/test_alembic.py`, `test_models.py`, `test_health.py`
- `docs/planning/domain_statuses.md`
- `docs/planning/task_sheet.md` (1.2b–1.2k leaves ticked)

## Next

- 1.2k-iii live: `alembic upgrade head` on `twerva-server`
- 1.2l thin HTTP API
- 1.2m idempotent Spotmu brand + example source item

---

# Task 1.2 (interim) — 1.2l HTTP API + 1.2m seed

*2026-09-15*

1.2b–k schema is merged (`12bk_domain_schema`). This note covers **1.2l**
and **1.2m**. Live SSH deploy of `twerva-api` is documented, not executed.

## Done

- **1.2l-i** Pydantic create/read schemas in `app/api/v1/schemas.py` for
  Brand, SourceItem, Cluster, Account, Artifact, PostJob, plus optional
  MetricSnapshot create/read (no metric routes).
- **1.2l-ii** `POST` + `GET` list + `GET` by id under `/api/v1` for Brand,
  SourceItem, Cluster, Account. No auth.
- **1.2l-iii** Same for Artifact and PostJob; both create and read include
  `status` (`draft` / `scheduled` defaults).
- **1.2l-iv** `GET /health` still does not import settings/models/`app.db`
  at module load. `/api/v1` mounts when `DATABASE_URL` can be resolved
  (env, `.env`, or test flag); otherwise the process stays health-only.
  Deploy steps for systemd `twerva-api` on `twerva-server` are in
  `apps/server/README.md`. Live SSH is deferred (same as 1.2a-v / 1.2k-iii).
- **1.2l-v** `tools/smoke_1_2l_api.sh` plus a README curl sketch:
  Brand `spotmu` → SourceItem → Cluster → Account → Artifact `draft` →
  PostJob `scheduled`, then GET each.
- **1.2m-i / 1.2m-ii / 1.2m-iii** Idempotent `python -m app.seed`: Brand
  `slug=spotmu` `name=Spotmu` and one fake SourceItem (`external_key=example`,
  three overview bullets, `https://spotmu.com/interest/example`). Not ingest.

No OAuth tokens, S3, Celery, ops UI, or 1.3 ingest.

## Trade-offs

- No new Alembic revision (seed is a module, not a data migration) so
  `12bk_domain_schema` stays the single head.
- MetricSnapshot has schemas only; SteerAction still has no API.
- Persist handler tests skip when Postgres is not reachable (metadata /
  schema / route-surface tests always run).
- Live `systemctl restart twerva-api` on EC2 is documented, not run.

## Verified

- `python -m unittest discover -s tests` — 1.2a–k tests plus schema,
  route-surface, lookups 404, seed idempotency. Persist handler test
  skips without Postgres; against local Postgres 16 +
  `alembic upgrade head` it passes.
- `GET /health` via uvicorn **without** `DATABASE_URL` → `200` `{"status":"ok"}`.
  `/api/v1/brands` is `404` in that health-only process (routes not mounted).
- `app/main.py` AST still excludes `app.db` / `app.models` / `app.settings`.
- `python -m app.seed` twice: first creates Brand + SourceItem; second
  prints `already present` with the same ids.
- `tools/smoke_1_2l_api.sh` against local uvicorn with `DATABASE_URL`:
  Brand `spotmu` reused → SourceItem → Cluster → Account → Artifact
  `draft` → PostJob `scheduled`, then GET each.
- Live `systemctl restart twerva-api` on `twerva-server` **not** run.

## Scripts touched

- `apps/server/app/main.py` (health-only import; lazy `/api/v1` attach)
- `apps/server/app/api/v1/` (schemas, routers, lookups, persist helper)
- `apps/server/app/seed.py`
- `apps/server/tests/test_api_schemas.py`, `test_api_routes.py`,
  `test_api_lookups.py`, `test_seed.py`, `test_api_persist.py`
- `tools/smoke_1_2l_api.sh`
- `apps/server/README.md`, root `README.md`
- `docs/planning/task_sheet.md` (1.2l / 1.2m leaves ticked)

## Next

- 1.2k-iii / 1.2l-iv live: `alembic upgrade head`, `python -m app.seed`,
  `systemctl restart twerva-api` on `twerva-server`
- 1.3 Spotmu ingest (replace the fake example SourceItem)
