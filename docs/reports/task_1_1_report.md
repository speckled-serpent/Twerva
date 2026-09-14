# Task 1.1 (partial) — Repo layout & coding discipline

*2026-09-14*

## Done

- Monorepo skeleton: `apps/`, `packages/`, `tools/`, `docs/` (with existing prompts/planning + new `reports/`)
- Root `README.md` pointing at strategy/product/task docs
- `.gitignore` for env, venvs, node_modules, caches
- Copied/adapted Spotmu `docs/prompts/style_guide.md` → Twerva
- Added `docs/prompts/directory.md` (Twerva-flavored monorepo rules)
- Added `.cursorrules` for Twerva agents (loop, brand-before-SKU, rent pipes, style guide mandatory, task reports)

## Trade-offs

- Did not invent app stack yet — layout only; stack choice remains an open 1.1 checkbox (prefer Spotmu-aligned when we pick).
- Style guide examples still use Spotmu domain nouns in places; rules are what matter for generation discipline.
- Domain registered by Mu; DNS/TLS/AWS provision still open.

## Next

- DNS → AWS + TLS
- Pick compute/Postgres/S3 shape on Spotmu account
- Stack decision, then empty ops app shell
