# Task 1.10h-iv — Generate samples

*2026-10-05*

Leaf **1.10h-iv** only. The section close stays undone.

## Done

- The open theme picks one Spotmu source item and calls
  `POST /api/v1/themes/{id}/samples`. The preview image stays on that
  page.
- A blocked preview stays up with an error banner and a highlight on
  the image. The text names overlap bands, a missing asset, or a
  measure error.
- A clear preview shows the image without that banner or highlight.
- With no source chosen, Generate samples does not call the API.
  Brand products are not in the picker.
- The click does not call `POST /api/v1/generate/carousel` and does not
  create an artifact or a post job. A reader cannot generate.

## Trade-offs

- The picker is the saved Spotmu source list, not a live Spotmu search.
- One preview is kept for the open theme. Generating again replaces it.

## Next

- What's left is `docs/planning/phase_map.md`.

## Scripts

- `apps/ops/src/pages/ThemeSamplePanel.tsx`
- `apps/ops/src/pages/ThemesPage.tsx`
- `apps/ops/src/api/client.ts` (`createThemeSample`, `fetchThemeSampleImageBlob`)
- `apps/ops/src/api/types.ts` (`ThemeSampleRequest`, `ThemeSampleResponse`)
- `apps/ops/src/index.css` (`.sample-preview`)
