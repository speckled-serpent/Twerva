# Task 1.10h-ii — Element editor

*2026-10-05*

Leaf **1.10h-ii** only. Duplicate and Generate samples stay off this page.

## Done

- The open theme lists elements by Top, Middle, and Bottom. An admin can
  add, edit, delete, reorder within a band, and move an element to
  another band.
- Content is text or image. A blank rectangle color saves as clear.
- Text controls are family, size, color, bold, italic, underline,
  strikethrough, optional weight, alignment, and a source picker. The
  picker offers only title, interest heading, overview bullets, and the
  public URL.
- Image content is one typed `asset_ref` (svg, png, jpeg). There is no
  file picker.
- A text element and an image element survive reload. Delete, reorder,
  and a band move survive reload. A reader sees the values and cannot
  save. Create Theme is still name-only.

## Trade-offs

- Save sends the band plus a full content payload. Text clears
  `image_asset_ref`. Image sets `text_source` to null. A band change
  omits `sort_order`, so the server appends on the new band.
- Reorder sends only `sort_order`. Move earlier and Move later stay
  disabled when the draft band differs from the saved band.

## Next

- **1.10h-iii** Duplicate.

## Scripts

- `apps/ops/src/pages/ThemeElementEditor.tsx`
- `apps/ops/src/pages/ThemesPage.tsx`
- `apps/ops/src/api/client.ts` (`createThemeElement`, `patchThemeElement`, `deleteThemeElement`)
- `apps/ops/src/api/types.ts` (`ThemeElementCreateRequest`, `ThemeElementPatchRequest`)
