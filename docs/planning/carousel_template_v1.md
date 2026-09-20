# Carousel template v1

*Phase 1.4a. Locked for the MVP text-led Spotmu carousel. Not a brand-kit
parity target.*

Render implementation: `apps/server/app/generate/carousel.py`.
Storage: local `ARTIFACT_STORAGE_DIR` (see §1.4b). S3 stays parked.

Restricted Spotmu templates (no freeform designer): `GET /api/v1/generate/templates`.
`spotmu_paper_v1` is the default current look. `spotmu_bold_v1` keeps the same
1080×1080 text-led rules with a darker ground and stronger accent. Generate
and regenerate persist `artifacts.template_id`. Authenticated
`GET /api/v1/artifacts/{id}/slides/{index}/image` streams the PNG
(readers may GET). `POST /api/v1/artifacts/{id}/regenerate` inserts a
**new** draft from the same source item (history kept).

---

## Canvas

| Token | Value |
|---|---|
| Width × height | **1080 × 1080** px |
| Format | PNG |
| Safe inset | 96 px from each edge |
| Platform | Instagram-friendly square; TikTok can reuse the same frames |

Do not generate video in this template.

---

## Slide roles (ordered)

Every generate produces this sequence. Empty overview bullets are
skipped; if there are **no** usable bullets, still emit cover → heading
→ CTA (three frames).

| `role` | Purpose | Source of `text` |
|---|---|---|
| `cover` | Open on the interest name | `source_item.title` |
| `heading` | One-line brief | `interest_heading`, or `title` again when heading is blank |
| `bullet` | One claim per slide | each non-empty `overview_bullets[]` entry |
| `cta` | Close with a landing | short prompt + resolved `cta_url` |

`artifacts.slides` is an ordered JSON list of
`{role, text, asset_ref}`. `asset_ref` is a path relative to
`ARTIFACT_STORAGE_DIR` (not an S3 key).

---

## Color and type (calm, text-led)

Cite Spotmu lightly: warm paper, near-black ink, one muted teal accent.
No stock photos, no mascot, no decorative illustration.

| Token | Hex | Use |
|---|---|---|
| `COLOR_BACKGROUND` | `#F6F1E8` | Full-bleed paper |
| `COLOR_INK` | `#1C1917` | Primary type |
| `COLOR_MUTED` | `#57534E` | Role label, secondary line |
| `COLOR_ACCENT` | `#0F766E` | Thin rule / mark (teal, Spotmu-adjacent) |
| `COLOR_RULE` | `#D6D3D1` | Hairline separator |

Typography: system sans (DejaVu / Liberation when present; Pillow
default otherwise). Sizes are starting points — wrap and shrink to keep
copy inside the inset.

| Face | Size | Use |
|---|---|---|
| Label | 22 | Role word (`SPOTMU`, `THE BRIEF`, `NOTE`, `CONTINUE`) |
| Cover title | 64 | `cover` body |
| Heading | 56 | `heading` body |
| Bullet | 48 | `bullet` body |
| CTA | 44 | CTA prompt |
| Footer | 20 | `spotmu.com` mark |

---

## CTA rules

`artifact.cta_url` (and the URL drawn on the CTA slide):

1. Use `source_item.canonical_url` when it is non-blank.
2. Else `https://spotmu.com/interest/{external_key}` when `external_key`
   is present (Spotmu slug).
3. Else `https://spotmu.com`.

CTA slide copy is a short prompt (`Read more on Spotmu`) plus that URL.
Do not invent UTM query strings in v1.

---

## Caption and hashtags (1.4a-ii)

Caption is stored on `artifact.caption` as one string:

```
{title}

{interest_heading}   # omitted when blank or identical to title

{cta_url}

#spotmu #learn #curiosity #ideas #carousel #readmore #interests
```

Rules:

- Short caption from title / heading only — do not paste every bullet.
- **3–8** generic, safe hashtags (v1 locks the seven above).
- No scraped, trending, or source-specific spam tags.
- No emoji required.

---

## Bullet slide policy (1.4a-iii)

- One bullet per slide.
- Skip entries that are empty or whitespace-only.
- Soft cap **160 characters** per bullet slide. Overflow splits on word
  boundaries into extra `bullet` slides (same role).
- A single oversized word is hard-split at the cap.
- Zero usable bullets → no `bullet` slides; cover / heading / CTA remain.

---

## File names

Under `{ARTIFACT_STORAGE_DIR}/{artifact_id}/`:

```
{slide_index}_{role}.png
```

`slide_index` is the 0-based order in `slides` (`0_cover.png`,
`1_heading.png`, …). `asset_ref` is `{artifact_id}/{slide_index}_{role}.png`.
