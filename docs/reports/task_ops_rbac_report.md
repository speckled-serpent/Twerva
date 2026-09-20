# Task — Ops RBAC, password change, user provisioning

*2026-09-20*

Extend live ops session auth so Mu can rotate the bootstrap password,
create additional operators, and give agents a **reader** (GET-only)
role. Session cookies stay; social `accounts` is untouched.

## Done

- Alembic revision **`ops_users_role_rbac`**: native enum `ops_user_role`
  (`admin` | `reader`), column `ops_users.role` NOT NULL. Existing rows
  backfilled to `admin`. Server default for new inserts is `reader`.
- Bootstrap still seeds only the **first empty-DB** operator and now
  sets `role=admin`. Env is not a password reset.
- `/me` and login include `role`. Never return `password_hash`.
- Self `POST /api/v1/auth/change-password` `{current_password,
  new_password}` (any signed-in user). Wrong current password is 400.
- Admin `GET` / `POST /api/v1/auth/users`; optional `PATCH
  /api/v1/auth/users/{id}` (role) and `POST
  .../users/{id}/reset-password`. Last admin cannot be demoted.
- RBAC: **admin** full access. **reader** may GET `/api/v1` except
  user-admin routes; mutations are **403** except `change-password`,
  `logout`, and GET `/me`. `GET /health` stays public. Login / logout /
  me stay as before.
- Ops UI: header role badge; **Account** change-password form; admin
  **Users** page (list / create / role / reset); write buttons disabled
  for readers; 403 banner text is explicit.
- Docs: `docs/ops/deploy.md`, `docs/startup.md`, server/ops READMEs.

## Locked choices

| Topic | Choice |
|---|---|
| Role storage | Postgres enum `ops_user_role`, not check-constrained text |
| New-row default | `reader` (bootstrap and backfill stay `admin`) |
| Reader mutations | 403 on protected router; change-password stays on `/auth` |
| Session | Same signed cookie; password change does not revoke it |
| Last admin | Cannot PATCH the only admin down to reader |

## Trade-offs

- Signed cookies still cannot be revoked per device without rotating
  `SESSION_SECRET`. Password change keeps the current cookie valid.
- Reader GET of `/auth/users` is 403 (admin-only), even though it is a
  GET. Domain GETs remain allowed.
- Fake in-memory session in `test_auth.py` is still HTTP-only (no
  Postgres). Domain GET for readers returns an empty brand list.

## Verified

- Server unit tests: 162 collected, 13 persist skips (no Postgres).
  Auth: change-password success/fail/unauthenticated; admin list/create;
  reader GET brands allowed; reader POST brands 403; non-admin cannot
  list/create users; `/me` includes `role`; Alembic head
  `ops_users_role_rbac`.
- `npm run build` in `apps/ops` (`tsc -b` + Vite `dist/`).
- Browser walk-through of Account/Users against a live API was not
  available in this environment (no Postgres). UI is type-checked and
  built; exercise on `twerva.com` after migrate.

## Out of scope

- OAuth / SSO
- Per-device session revoke table
- Soft-delete / disable of ops users
- Changing social `accounts`

## Scripts / files touched

- `apps/server/app/models/ops_user.py`, `app/models/enums.py`
- `apps/server/alembic/versions/ops_users_role_rbac.py`
- `apps/server/app/auth/dependencies.py`, `app/auth/bootstrap.py`
- `apps/server/app/api/v1/authentication.py`, `schemas.py`, `router.py`
- `apps/server/tests/test_auth.py` (+ alembic / routes / models)
- `apps/ops` Account / Users pages, nav, session context, write disables
- `docs/ops/deploy.md`, `docs/startup.md`, READMEs
- this file

## Next

- Badger: `alembic upgrade head` to `ops_users_role_rbac`, restart
  `twerva-api`, rebuild/copy ops `dist/`.
- Mu: sign in as bootstrap admin, change password, create a reader for
  agents.
