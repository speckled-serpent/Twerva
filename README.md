# Twerva

*Pronunciation: TWER-vuh*

Bootstrap **distribution control plane** — middle node between product/brand content and social platforms.

```
source → generate → approve → publish → measure → steer
```

Not a social network. Not an ads bidder. Not an autoposter that only feeds empty personal accounts.

- **Phase 1–2:** Spotmu as customer zero (media content hose).
- **Phase 3:** Internal brands / internal projects (real PoC).
- **Phase 4 (optional):** External brands / spin-off — not required for “worth it.”

Sibling to Spotmu: **separate service and URL**, same Spotmu AWS account for billing until a real spin-off.

## Docs

| Doc | Role |
|---|---|
| [`docs/prompts/project.md`](docs/prompts/project.md) | Strategy, SWOT, roadmap |
| [`docs/prompts/product.md`](docs/prompts/product.md) | Product design, build vs buy |
| [`docs/planning/task_sheet.md`](docs/planning/task_sheet.md) | Build tasks |
| [`docs/overview.md`](docs/overview.md) | Spotmu handoff seed |
| [`docs/prompts/style_guide.md`](docs/prompts/style_guide.md) | Code style (from Spotmu) |
| [`docs/prompts/directory.md`](docs/prompts/directory.md) | Monorepo layout rules |
| [`.cursorrules`](.cursorrules) | Agent / Cursor discipline |

## Repo layout

```
apps/          # deployable services (ops console, API, workers) — TBD
packages/      # shared libraries
tools/         # scripts and deploy helpers
docs/          # project, product, planning, reports
```

See `docs/prompts/directory.md`.

## Status

- Domain: registered.
- Docs: strategy + product + task sheet in place.
- App skeleton / AWS service: not yet (task sheet §1.1).

## Development discipline

All generated code must follow `docs/prompts/style_guide.md` and `.cursorrules`. Prefer small, task-sheet-scoped changes.
