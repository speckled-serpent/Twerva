# Task 1.10e-i — Resolve theme text from a source item

*2026-10-04*

Leaf **1.10e-i** only. Text measurement, image measurement, overlap,
samples, and the ops editor stay undone.

## Done

- `resolve_theme_text` in `apps/server/app/themes/sources.py` reads one
  text element from a `SourceItem`.
- `title` is the stored title.
- `interest_heading` and `canonical_url` are blank when null.
- `overview_bullets` is the non-empty strings joined with newlines into
  one block. Empty bullets are omitted. This does not emit a frame per
  bullet.
- The text-source enum stays the four Spotmu keys.

## Trade-offs

- Bullets are stripped, and a whitespace-only bullet is omitted. Title,
  heading, and URL are returned as stored when they are not null.
- The function does not check `source_type`. Non-Spotmu resolution is
  still out of scope; the four columns are the Spotmu fields.

## Next

- **1.10e-ii** measure text and reflow the band.

## Scripts

- `apps/server/app/themes/sources.py`
- `apps/server/tests/test_theme_sources.py` (fake Spotmu source item,
  three bullets as one string, null heading and URL blank, disallowed
  key absent from the enum)
