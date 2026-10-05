# Task 1.10h-iii — Duplicate

*2026-10-05*

Leaf **1.10h-iii** only. Generate samples stays off this page.

## Done

- The open theme has one Duplicate button. It calls
  `POST /api/v1/themes/{id}/duplicate` and opens the returned Draft.
- The copy is named `Copy of {name}`, status Draft, with an empty
  template key. The source list row stays Live, and the source
  `updated_at` does not change.
- The Themes list shows Draft or Live on each row. A reader can see
  Duplicate and cannot press it. Create Theme is still name-only.

## Trade-offs

- Duplicate copies the saved theme. Unsaved frame edits on the open
  page are not written first.
- The new Draft is inserted at the top of the in-memory list. The
  server list is still newest first, so a reload matches.

## Next

- **1.10h-iv** Generate samples.

## Scripts

- `apps/ops/src/pages/ThemesPage.tsx`
- `apps/ops/src/pages/themeDisplay.tsx` (`themeStatusLabel`)
- `apps/ops/src/api/client.ts` (`duplicateTheme`)
