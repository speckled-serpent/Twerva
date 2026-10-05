# Task 1.10h-i — Frame fields

*2026-10-05*

Leaf **1.10h-i** only. Element editing, duplicate, and sample
previews stay off this page.

## Done

- The open theme in `ThemesPage` edits Draft/Live, background kind, the
  payload for that kind, and the three spacing numbers.
- Color is a hex field. Gradient is an angle plus stops. Picture and
  texture are a text `asset_ref`. There is no file picker.
- Save calls `PATCH /api/v1/themes/{id}`. A Live theme missing its
  payload shows the API error on the form and does not replace the
  saved frame.
- Create Theme is still name-only. A reader sees the values and cannot
  save (`ReadOnlyNotice`, disabled fields, disabled Save frame).

## Trade-offs

- Save sends the status, the kind, the payload for that kind, and the
  three spacing numbers. Payloads for the other kinds are left as they
  were.
- A blank gradient angle is sent as a null gradient so Live validation
  can fire. A filled angle is sent as the locked stop list.

## Next

- **1.10h-ii** element editor.

## Scripts

- `apps/ops/src/pages/ThemesPage.tsx`
- `apps/ops/src/api/client.ts` (`patchTheme`)
- `apps/ops/src/api/types.ts` (`ThemePatchRequest`)
