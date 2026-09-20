# Task — Ops web auth + public console

*2026-09-20*

Make `https://twerva.com` the ops console (not SSH-tunnel + local Vite
only) without exposing unauthenticated `/api/v1`. Operator accounts
live in Postgres; the first admin is seeded from env.

## Done

- Alembic revision **`ops_users_web_auth`**: table `ops_users`
  (`id` UUID PK, unique `username`, `password_hash`, timestamps).
- **Session approach:** signed httpOnly cookie (`itsdangerous`
  `URLSafeTimedSerializer` + `SESSION_SECRET`). Payload is
  `ops_users.id`. No `ops_sessions` table. Logout clears the cookie.
  TTL is `SESSION_TTL_SECONDS` (default 12h). Rotating
  `SESSION_SECRET` invalidates every session.
- Password hashes: **bcrypt** (`bcrypt` package, not passlib).
- Settings: `OPS_ADMIN_USERNAME`, `OPS_ADMIN_PASSWORD` (bootstrap
  only), `SESSION_SECRET` (required outside tests when `DATABASE_URL`
  is set), cookie name/flags (`HttpOnly`, `SameSite=Lax`, `Secure`).
- Bootstrap: startup (non-test, when `/api/v1` mounts) and
  `python -m app.auth.bootstrap`. Creates the first row only when the
  table is empty and both admin env vars are set. Never logs the
  password.
- Public routes: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`,
  `GET /api/v1/auth/me`. All other `/api/v1/*` use
  `require_authenticated_ops_operator` (401). `GET /health` stays
  public and import-light.
- CORS: `OPS_CORS_ORIGINS` + `allow_credentials=True` for local Vite
  without the proxy. Production same-origin nginx does not need CORS.
- Ops UI: login page, `credentials: "include"`, logout in nav,
  `GET /auth/me` 401 → login. Production build uses relative `/api`
  (no `VITE_API_BASE_URL`). Vite proxy kept for local/dev.
- Deploy/startup docs: build `dist/` → `/var/www/twerva-ops`, nginx
  sample (certbot-compatible), env paths, migrate + bootstrap.
- Loopback smokes source `tools/lib/ops_session.sh` and login first.

## Locked choices

| Topic | Choice |
|---|---|
| Session store | Signed cookie, not `ops_sessions` |
| Cookie name | `twerva_ops_session` |
| Hash | bcrypt 12 rounds |
| First admin | Env bootstrap only; never a standing password override |
| Public nginx | `/` (console), `/api/`, `/health`. No `/docs` |
| uvicorn | Still `127.0.0.1:8000` only |

## Trade-offs

- Signed cookies cannot be revoked per device without rotating
  `SESSION_SECRET`. Fine for a single operator; add `ops_sessions` if
  we need remote logout later.
- Existing handler-level persist tests still call functions directly
  (no cookie). HTTP smokes now need `OPS_ADMIN_*`.
- Bootstrap does not reset a forgotten password. That is a manual SQL
  / future CLI.

## Verified

- Server unit tests: 149 collected, 13 persist skips (no Postgres).
  Auth: login success/fail, `/me`, protected 401, health without
  `DATABASE_URL`, bootstrap skip/create, Alembic head.
- `npm run build` in `apps/ops` (`tsc -b` + Vite `dist/`).
- Browser: same-origin preview of that `dist/` — failed login stays on
  Sign in, successful login opens Sources with username + Log out,
  session holds across Queue/Accounts, logout + reload stays signed
  out.

## Out of scope

- OAuth / SSO
- Multi-tenant product accounts
- Real passwords in the repo
- Exposing uvicorn or FastAPI `/docs` on the public internet

## Scripts / files touched

- `apps/server/app/models/ops_user.py`, `app/auth/*`, `app/api/v1/authentication.py`
- `apps/server/alembic/versions/ops_users_web_auth.py`
- `apps/server/app/settings.py`, `app/main.py`, `app/api/v1/router.py`
- `apps/server/tests/test_auth.py` (+ alembic / models / routes / settings)
- `apps/ops/src/pages/LoginPage.tsx`, `App.tsx`, `api/client.ts`, `components/NavBar.tsx`
- `docs/ops/deploy.md`, `docs/startup.md`, READMEs
- `tools/lib/ops_session.sh` + smoke / agent scripts
- this file

## Next

- Badger/Sparky on `twerva-server`: `pip install`, `alembic upgrade
  head`, write `SESSION_SECRET` + bootstrap admin into the systemd env
  file, `python -m app.auth.bootstrap`, build/copy ops `dist/`, apply
  nginx, restart `twerva-api`.
- Do not merge this PR until that apply is scheduled; this PR only
  lands the code + runbook.
