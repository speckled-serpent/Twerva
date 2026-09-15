# Task 1.6a — Buy vs build publish spike & lock

*2026-09-15*

Compare unified publish vendors vs native Meta + TikTok APIs. No vendor
signup in this spike. Public docs only.

Twerva already owns generate, approve, cadence, clusters, and (later)
measure/steer. The pipe is “post this media + caption to account X and
return a platform id/URL.” Product rule: **rent pipes, build the brain.**

## Lock (1.6a-ii)

| Piece | Locked value |
|---|---|
| Interface | `PublishAdapter.publish(...)` in `apps/server` |
| Default adapter | **`mock`** (`PUBLISH_ADAPTER=mock`) |
| First live vendor (later) | **Ayrshare** behind `PUBLISH_ADAPTER=ayrshare` when keys exist |
| Live HTTP in 1.6 | **Not wired** — no OAuth, no signup, CI stays mock |
| Native Meta / TikTok | Deferred until a vendor is too limiting |
| Postiz self-host | Parked (we would own Meta/TikTok developer apps) |
| Zernio (formerly Late) | Strong runner-up; swap via the same adapter |
| Tokens | Still not stored on `accounts` (plaintext columns stay out) |

Config (1.6b-iii):

- `PUBLISH_ADAPTER` — `mock` (default) or `ayrshare`
- `AYRSHARE_API_KEY` — required only when the adapter name is `ayrshare`;
  unused by mock; **do not** put in git

`GET /health` does not load this. `/api/v1` uses settings as today.

## Comparison

### Ayrshare (recommended first live vendor)

- REST `POST https://api.ayrshare.com/api/post` with `post`, `platforms`,
  `mediaUrls`. Optional `scheduleDate` (UTC). Bearer API key.
- Instagram + TikTok in one API. IG carousel: up to **10** images/videos
  in `mediaUrls` (Twerva 1080×1080 PNGs fit). IG Business/Creator +
  Facebook Page required on the connected account.
- Response includes per-platform `id` and `postUrl` — maps onto
  `post_jobs.platform_post_id` / `platform_post_url`. TikTok may return
  `id: "pending"` until their async processing webhook.
- Analytics endpoints exist (useful for 1.7 later).
- **Gap vs Twerva today:** `mediaUrls` must be **publicly fetchable**.
  Phase 1.4 stores PNGs on local `ARTIFACT_STORAGE_DIR` (not public
  nginx, not S3). Live Ayrshare needs an upload/hosting step (Ayrshare
  media API, temporary signed URL, or parked S3). Mock does not.
- Auth: vendor dashboard OAuth for IG/TikTok — not Twerva’s job in 1.6.
  Store their profile/account id in `accounts.external_account_id` by
  hand when we go live.

### Zernio (formerly Late)

- REST `POST https://zernio.com/api/v1/posts` + official Python SDK
  (`zernio-sdk`). Bearer `ZERNIO_API_KEY`. First two connected accounts
  free (except X).
- 16 platforms including Instagram and TikTok. `publish_now` or
  `scheduledFor`. Media via `mediaItems` URLs.
- TikTok wants extra consent/privacy fields (`tiktokSettings`).
- Rebrand from Late is recent; old SDK names still work.
- Same public-media-URL gap as Ayrshare. Ads API exists — **do not**
  pull that into Twerva (never a paid-ads bidder).

### Postiz (open-source / self-host)

- AGPL scheduler with a public REST API
  (`/api/public/v1/posts`, `/upload`). Cloud or self-host.
- Self-host means **we** register Meta + TikTok developer apps, HTTPS
  redirect URLs, and keep tokens on our box. That is building the pipe,
  not renting it. TikTok Direct Post still needs their audit.
- Fine as an escape hatch if Ayrshare/Zernio cost or lock-in hurts.
  Not the MVP default.

### Native Meta Graph + TikTok Content Posting API

- Instagram Content Publishing: Business/Creator + Page, app review
  (`instagram_content_publish`), often Business Verification. Carousel
  is a container dance (item containers → carousel container → publish).
- TikTok Content Posting: Inbox vs Direct Post; Direct Post needs
  audit before public posts. Photo carousels and video are different
  products.
- Two OAuth stacks, two review queues, two failure modes. Slow for a
  bootstrap internal control plane. Matches product.md: official APIs
  work but are slow to certify.

## Recommendation (MVP + Phase 2)

1. **Ship the adapter + mock now** so schedule → published is real in
   Twerva’s DB without vendor signup (this task).
2. **First paid pipe: Ayrshare.** Documented carousel + platform ids,
   one HTTP shape, analytics later. Enable only when Mu adds
   `AYRSHARE_API_KEY` and connected test accounts.
3. Keep Zernio as the swap candidate if Ayrshare pricing or TikTok
   pending-ids are painful.
4. Do **not** self-host Postiz or native Meta/TikTok until the vendor
   adapter is proven too limiting (task-sheet parking lot).

## Failure modes (any live vendor)

| Mode | Handling in 1.6 |
|---|---|
| Adapter exception | `post_jobs.status=failed`, `last_error` set |
| Retry | Same `POST /api/v1/publish/run/{id}` on `failed` (no Redis/backoff) |
| Missing slide files | Fail the run; do not pretend publish succeeded |
| Live media not public | Out of scope for mock; note for Ayrshare follow-up |
| Vendor rate limits | Not handled; cadence caps (1.5) are our side |

## Out of scope (as specified)

- Real OAuth / vendor signup
- Connecting live IG/TikTok test accounts
- Celery/Redis
- Ops UI (1.8)
- Storing refresh tokens on `accounts`
