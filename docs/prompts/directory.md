# Twerva Monorepo Structure Guidelines

Adapted from Spotmu’s `directory.md`. Same discipline: separate apps, shared packages, tools, docs.

## Core directories

- **`/apps`** — Deployable applications and services (e.g. `ops` console, `server` / workers).
- **`/packages`** — Shared internal libraries and types used across apps.
- **`/tools`** — Build scripts, deploy helpers, repo-wide tooling.
- **`/docs`** — Strategy, product, planning, reports (`docs/prompts/`, `docs/planning/`, `docs/reports/`).

## Rules

1. **Separation of concerns.** Apps do not depend on other apps. Shared code goes in `/packages`.
2. **Language workspaces.** Python: venv / requirements per app or root as appropriate. TypeScript: workspaces linking `/packages` into `/apps`.
3. **No circular dependencies.** `/packages` must not depend on `/apps`.
4. **Local colocation.** Tests, scripts, and notes for a module live next to that module; global docs stay under `/docs`.
5. **Root stays thin.** Only globally important files at repo root (README, lockfiles, workspace config, `.cursorrules`).

Stack choices for Twerva apps are still open (see task sheet); structure comes first so we do not invent a second pattern from Spotmu.
