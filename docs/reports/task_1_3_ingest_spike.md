# Task 1.3a — Spotmu ingest path spike & lock

*2026-09-15*

Live curls against production Spotmu. Field shapes taken from the public
JSON (Spotmu router/schema names used only as labels — Spotmu was not
modified).

## Lock (1.3a-ii)

**MVP path:** unauthenticated public JSON by slug + sitemap discovery.

| Piece | Locked value |
|---|---|
| Public origin | `https://spotmu.com` |
| Same backend alias | `https://app.spotmu.com` (identical JSON in this spike) |
| Interest JSON | `GET {origin}/api/v1/interests/slug/{slug}` |
| Discovery | `GET {origin}/sitemap.xml` (`<loc>https://spotmu.com/interest/{slug}</loc>`) |
| Twerva config | `SPOTMU_API_BASE_URL` (default `https://spotmu.com`) |
| Canonical URL we store | `{SPOTMU_API_BASE_URL}/interest/{slug}` |

Do **not** GET `/interests/slug/{slug}` at the site origin. That path is
the SPA shell (`text/html` 200), not the API. The FastAPI route the task
sheet called `GET /interests/slug/{slug}` is mounted under **`/api/v1`**
on the live origin.

Rejected for MVP: authenticated Spotmu export, HTML scrape of
`/interest/:slug` (SPA shell only).

## Live curls (1.3a-iii)

Recorded 2026-09-15 from this spike. Status lines and bodies are
production.

### Sitemap (discovery)

```bash
curl -sS -D - -o /tmp/sitemap.xml https://spotmu.com/sitemap.xml
```

- `https://spotmu.com/sitemap.xml` → **200** `application/xml` (~53 KB)
- `https://app.spotmu.com/sitemap.xml` → **200**, same document
- `https://spotmu.com/robots.txt` → `Sitemap: https://spotmu.com/sitemap.xml`
- Count this run: **437** `<loc>` URLs, **436** `/interest/{slug}` pages
- Example loc: `https://spotmu.com/interest/ai-agents`

### Interest JSON (fetch one)

```bash
curl -sS -D - https://spotmu.com/api/v1/interests/slug/ai-agents
```

- `https://spotmu.com/api/v1/interests/slug/ai-agents` → **200**
  `application/json` (~4.4 KB). No auth header.
- `https://app.spotmu.com/api/v1/interests/slug/ai-agents` → **200**, same
  body (same process / nginx).
- `https://spotmu.com/api/v1/interests/slug/amazon` → **200**, same keys.
- Unknown slug on the JSON path:
  `GET /api/v1/interests/slug/this-slug-does-not-exist-twerva-spike`
  → **404** `{"detail":"Interest not found"}`

### Paths that are *not* the API

| URL | Result |
|---|---|
| `https://spotmu.com/interests/slug/ai-agents` | **200** `text/html` SPA index |
| Same with `Accept: application/json` | still **200** HTML |
| `https://spotmu.com/api/interests/slug/ai-agents` | **404** `{"detail":"Not Found"}` |
| `https://spotmu.com/interest/ai-agents` | **200** `text/html` SPA index (no brief fields in HTML) |

## Public JSON field coverage vs `source_items`

Live `PublicInterestPageResponse` keys on `ai-agents` / `amazon`:

`interest_hash_id`, `slug`, `title`, `interest_heading`,
`overview_summary`, `overview_bullets`, `overview_text`,
`overview_created_at`, `last_updated`, `serve_story_count`,
`categories`, `teasers`.

| Twerva `source_items` | Public payload | Mapping |
|---|---|---|
| `source_type` | (none) | always `spotmu_interest` |
| `external_key` | `slug` | slug string |
| `title` | `title` | as-is |
| `interest_heading` | `interest_heading` | as-is |
| `overview_bullets` | `overview_bullets` | **string**, newline-separated — split to `list[str]` |
| `canonical_url` | (none) | construct `{origin}/interest/{slug}` |
| `brand_kit_refs` | (none) | no logo / brand-kit fields on this payload → `null` |
| `raw_payload` | full JSON | store the object |

`overview_bullets` is **not** a JSON array on the live API. Example
(`ai-agents`): one string with five lines. Twerva still stores JSONB
`list[str]` after split. Parser must also accept a list if Spotmu
changes shape later.

`teasers` / `overview_text` / `categories` / `interest_hash_id` are
forward-compat only (kept inside `raw_payload`). They are not brand-kit
refs.

## Option comparison (1.3a-i)

### 1. Public JSON `GET /api/v1/interests/slug/{slug}`

- **Auth:** none.
- **Coverage:** title, heading, bullets (after split), slug; kit refs
  absent; canonical URL constructed.
- **Failures:** 404 unknown slug; HTML if the `/api/v1` prefix is
  omitted; timeout / non-JSON; bullets arriving as a string.
- **Verdict:** lock this for fetch-one.

### 2. Sitemap `/sitemap.xml`

- **Auth:** none.
- **Coverage:** slug list only (plus lastmod). No brief fields.
- **Failures:** XML parse errors; homepage loc must be skipped; cap
  required (436 interests today).
- **Verdict:** lock this for discovery. No public “list interests” JSON
  was found.

### 3. Authenticated Spotmu API / export

- **Auth:** would need a Spotmu credential Twerva does not have on box.
- **Coverage:** unknown extra vs public page; not required — public JSON
  already has the 1.3 fields.
- **Failures:** secret handling, coupling to private routes.
- **Verdict:** skip for MVP (task: no private auth unless public is
  insufficient).

### 4. HTML scrape `/interest/:slug`

- **Auth:** none.
- **Coverage:** SPA shell only in this spike — brief fields are not in
  the HTML document.
- **Failures:** brittle, fights the existing JSON API.
- **Verdict:** out of scope (task: do not scrape HTML when JSON exists).

## Failure modes to handle in 1.3b

- HTTP 404 → do not upsert.
- 200 + `text/html` (wrong path) → non-JSON error, no upsert.
- Timeout / connect error → explicit error.
- `overview_bullets` string vs list → normalize to `list[str]`.

## Config

```bash
# optional; default is the locked public origin
export SPOTMU_API_BASE_URL=https://spotmu.com
```

Client builds:

- `{SPOTMU_API_BASE_URL}/api/v1/interests/slug/{slug}`
- `{SPOTMU_API_BASE_URL}/sitemap.xml`

Not a secret. Production can rely on the default. Override only if the
public origin changes.

## Next

1.3b typed client against this lock; 1.3c upsert; 1.3d sitemap sync
(on-demand, limited); 1.3e manual cluster attach.
