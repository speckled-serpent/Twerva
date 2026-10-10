# Albums v1

*Last updated: 2026-10-10*
*Status: Proposed design. Not locked. Mu accepts or changes each **Proposed** line.*

Albums are the first content source Twerva can draw from. A source is material a later campaign, instruction set, or model can point at. This slice is images only, so that work can start. Spotmu stays customer zero. Its posts still take text from an interest. Albums matter here for picture backgrounds and image elements, and they matter more when a Phase 3 house brand needs a set of pictures instead of one frame on repeat.

This document proposes the model. It does not change tables or screens. Until it is implemented, the theme editor still has one Default album of packaged photos and stores a concrete `theme-defaults/…` path. See the consolidation this replaces, and [`themes_v1.md`](themes_v1.md).

---

## Proposed answers

Each line is a recommendation, not a lock.

| Topic | Proposed | Why |
|---|---|---|
| Name | **Albums** in the UI. "Content source" is the broader idea. | The editor already says album. A wider library can use the same idea later without a rename now. |
| What it holds | Images only. Text, fonts, and colors later. | Themes already need pictures. Mixed material is a second product. |
| Brand editorial | Same idea later, not a second system. Not in this slice. | Phase 3 should add kinds, not a parallel library. |
| Ownership | Global. An admin owns every album. Brand and campaign scope later. | One ops team, one box. Scoping can wait for a house brand. |
| Theme reference | Keep a concrete path. Optional "random from this album" only when a post is generated. | Shuffle already showed that a late roll changes a picture the operator saved. Samples stay still. |
| Variety | Generate picks one asset at random, then stores that path on the new artifact. The theme path does not change. | The shipped post is stable. The next post can differ. |
| Intake | Admin upload and URL import. Stock, Spotmu-supplied, and generated files later. | Those two cover "we have a file" and "we have a link" without a vendor. |
| License | Required license and source. Allowlist: CC0, public domain, owned, licensed-with-proof. Anything else cannot be saved. | Default was cleaned to CC0 and PD. New files should not reopen that hole. |
| Bytes | Disk under `ARTIFACT_STORAGE_DIR`, behind a small storage interface. S3 is a later implementation of that interface. | Prod is one EC2. S3 stays parked until a second host or real volume. |
| Thumbnails | Yes, for the grid. | A detail page of full frames is the wrong preview. |
| Delete | Block when a theme or an artifact still points at the asset or the album. | Detach would silently change saved themes. |
| Texture | Later, as an album of images. Not in this slice. | The background kind stays picture, color, or gradient. |
| First slice | Albums, licensed images, theme picker still storing a path, generate-time random. | Enough for campaigns to draw from. Not a brand CMS. |

---

## What an album is

An album is a named set of images. Global. No brand id and no campaign id in this slice.

The operator picks an image in the theme editor the way they do now: the choice is stored as a concrete relative path. Shuffle still writes a different path once. It does not turn on random.

**Proposed.** A picture background or an image element may also name an album for generate time only. Samples, live preview, and the saved theme keep using the concrete path. Generate, when that mode is on, picks one asset from the album at random, writes that path onto the new artifact, and leaves the theme alone.

A missing file is still a missing-asset error. No substitute picture.

---

## Data model

Two tables. Themes gain two nullable album pointers. Existing path columns stay.

**`albums`**

| Column | Notes |
|---|---|
| `id` | UUID. |
| `name` | Shown in the UI. |
| `slug` | Unique. Default's slug is `default`. |
| `created_at`, `updated_at` | |

**`album_assets`**

| Column | Notes |
|---|---|
| `id` | UUID. |
| `album_id` | FK → `albums`. |
| `relative_path` | Unique. What a theme or artifact stores. |
| `media_type` | `svg`, `png`, `jpeg`, or `webp`. |
| `byte_size` | |
| `width`, `height` | Null for SVG. |
| `alt_text` | Optional. |
| `tags` | Text list. Optional. |
| `license` | `cc0`, `public_domain`, `owned`, or `licensed`. |
| `source` | Required. Where it came from. A URL or a short note. |
| `license_note` | Required when `license` is `licensed`. Otherwise empty. |
| `intake` | `upload` or `url`. |
| `thumbnail_path` | Null for SVG. |
| `created_at`, `updated_at` | |

**Proposed theme columns.** `themes.background_album_id` and `theme_elements.image_album_id`, both nullable FKs. Null means generate uses the stored path. Set means generate picks at random from that album. `background_asset_ref` and `image_asset_ref` stay the concrete path samples use.

Save is rejected when license is outside the allowlist, source is blank, `licensed` has no note, or the file fails the limits below.

---

## Storage and limits

**Proposed.** New bytes go under `ARTIFACT_STORAGE_DIR`, prefix `albums/<album_id>/<asset_id>.<ext>`. Thumbnails are JPEG, longest edge 480, beside the original. SVG is stored as-is and has no thumbnail; the grid uses the SVG.

The packaged Default files stay in `apps/server/app/themes/default_images/`. Their `relative_path` stays `theme-defaults/<filename>`. The renderer keeps resolving that prefix from the package. Other paths still resolve under `ARTIFACT_STORAGE_DIR`.

A storage interface is `save`, `open`, and `delete` for the `albums/` prefix. The first implementation is the local disk. S3, when it is no longer parked, is another implementation. Callers do not see which.

| Limit | Proposed |
|---|---|
| Formats | SVG, PNG, JPEG, WebP. Others rejected. |
| Size | 8 MB per file. |
| URL import | Server downloads the URL once. Render does not fetch it again. Same size and type limits. |
| Thumbnail | Raster only. Longest edge 480, JPEG. |

---

## How a picture is resolved

**Samples and live preview.** Read the stored `background_asset_ref` or `image_asset_ref`. Ignore `background_album_id` and `image_album_id`. The preview matches the path the operator saved.

**Generate** (the path that inserts an artifact). If the album id for that picture is null, use the stored path. If it is set, pick one asset in that album at random, and store that asset's `relative_path` on the new artifact. Do not update the theme. The next generate may pick a different file. The artifact already written does not change.

**Theme editor.** The album dropdown lists `albums`. Choosing an image still saves the concrete path. Shuffle still saves a different concrete path from that album. A separate control, off by default, sets the album id used only at generate time. An old path that is not in any album stays "Saved image" and still renders when the file exists.

---

## Migrating Default

Seed one album, name Default, slug `default`.

One `album_assets` row per file already in `default_images/`. `relative_path` is the existing `theme-defaults/…` value, so themes that already store those paths do not need a rewrite. `license` and `source` come from `default_images/LICENSES.md` (`cc0` or `public_domain`). `intake` is `upload`. No thumbnail copy is required for these six; the grid may use the packaged JPEG.

Do not move the bytes onto the artifact disk. The package remains the source for that prefix.

---

## API

Readers may GET. Admins may change. Same rule as themes.

| Call | Behavior |
|---|---|
| `GET /api/v1/albums` | Albums, each with its asset paths. Replaces the hard-coded Default list. |
| `POST /api/v1/albums` | `{name}`. Slug from the name. |
| `GET /api/v1/albums/{id}` | One album and its assets, including license, source, and thumbnail path. |
| `PATCH /api/v1/albums/{id}` | Name. |
| `DELETE /api/v1/albums/{id}` | 409 when any asset path is in use, or a theme points at the album for generate-time random. |
| `POST /api/v1/albums/{id}/assets` | Multipart upload plus license, source, optional alt and tags. |
| `POST /api/v1/albums/{id}/assets/import` | `{url, license, source, …}`. Server stores the bytes. |
| `PATCH /api/v1/albums/{id}/assets/{asset_id}` | Metadata only. Not the bytes. |
| `DELETE /api/v1/albums/{id}/assets/{asset_id}` | 409 when a theme or artifact stores that `relative_path`. |
| `GET` thumbnail | Stream the thumbnail, or the SVG. Signed-in operators, including readers. |

A bad license, a blank source, a missing license note, a bad type, or a file over 8 MB is 400. Nothing is written.

---

## Ops UI

Two pages. No new visual system. The theme editor changes only enough to list real albums.

**Albums.** A list: name, image count. Admin can create one.

**Album.** A grid of thumbnails. Admin can upload, import from a URL, edit alt text, tags, license, and source, and delete. Delete explains the block when the asset or the album is in use. License and source are required on the form. `licensed` shows the note field and will not save without it.

**Theme editor.** The picture and image controls list these albums. Pick and Shuffle still store a concrete path. **Proposed.** A checkbox, off by default: "At generate time, pick at random from this album." Samples ignore it.

Readers see the list, the grid, and the theme control. They cannot create, upload, import, edit, or delete.

---

## Permissions

| Role | Albums |
|---|---|
| Reader | List, open, see metadata and thumbnails. Use an album when a theme is not theirs to save. |
| Admin | Create, upload, import, edit metadata, delete when unused. |

No per-album owner. Global, as proposed above.

---

## MVP and later

**MVP**

- `albums` and `album_assets`
- Upload, URL import, license allowlist, thumbnails, disk storage behind an interface
- Default seeded in place, existing `theme-defaults/…` paths unchanged
- Theme picker and Shuffle storing a concrete path
- Generate-time random stored on the artifact only
- Delete blocked when in use
- Admin writes, reader reads

**Later**

- Text snippets, fonts, colors, and other brand material on the same content-source idea
- Brand or campaign ownership
- Texture as another album
- Stock, Spotmu-supplied, and generated intake
- S3 behind the same storage interface
- Instruction sets and the decision model that choose among sources. This doc only gives them an album to name.

---

## Still open

Only Mu can answer these. They are not given a proposed default above.

1. For `licensed`, is a short note enough proof, or do you want a URL or an attached file?
2. After generate picks a random image, is the artifact the only place that choice should show?
3. When instruction sets arrive, should one name an album directly, or only through the theme's generate-time mode?
4. May an admin add images to Default, or is Default frozen as the six packaged photos?
5. Is global-only right until a house brand exists, even if the first brand wants its own album sooner?
