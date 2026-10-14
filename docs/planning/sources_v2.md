# Sources v2

*Last updated: 2026-10-14*
*Status: Proposed design. Not locked. **Decided** is Mu's model. **Proposed** is a recommendation he can accept or change.*

Sources are the content Twerva draws from. This slice stores them and lets an operator manage them. Campaigns, instruction sets, and a model can point at a source later. How those pieces combine is in [Later](#later-campaign-combination-rules-and-model).

Spotmu stays customer zero. A theme's text still comes from an interest. A picture background or an image element picks one image from an album unit and stores that file's path.

Until this is implemented, the theme editor still has one Default album of six packaged photos and stores a concrete `theme-defaults/…` path. See [`themes_v1.md`](themes_v1.md). This document replaces the albums-only sketch.

---

## Concepts

**Source. Decided.** Content Twerva can draw from. Two kinds: an album or a resource.

**Album. Decided.** A named collection of units. The units in one album may be images only, text only, or mixed.

**Unit. Decided.** A small piece of content whose parts belong together. Zero or more images, and zero or more text, with at least one of the two. Later, when a post is generated from a unit, that text stays with those images.

**Decided** examples:

- One or several photos of a specific lamp, plus that lamp's name, price, and description.
- A single stock cityscape, with no text.
- A single poem. Each Rumi poem is its own unit.

**Fields and free text. Decided.** A unit may carry structured labeled fields (name, price, description, as key and value) and free text. Fields keep a product-style unit reliable. A poem can be free text alone.

**Tags. Decided.** Optional labels on a unit, such as "Chicago" on an ambiguous cityscape. They exist so a later step can associate images with stories. This slice only stores them.

**Image provenance. Decided.** Each image has a license and a source. The license is one of CC0, public domain, owned, or licensed-with-proof. Anything else cannot be saved.

**Resource. Decided.** A large body of reference information, kept whole, not split into units. Example: research on the Holy Roman Empire compiled from many sources into one synthesis. The MVP file is Markdown or TXT, uploaded and stored as-is, with provenance notes. PDF conversion and turning many inputs into a synthesis come later.

---

## Proposed answers

| Topic | Proposed | Why |
|---|---|---|
| Shape | One `sources` row, `kind` of `album` or `resource`. | A later campaign can point at one id. |
| Tags | A text list on the unit, not on each image. | The photos of one lamp share the lamp's tags. |
| Field labels | Free-text keys. The form suggests name, price, and description. | A poem has no price. |
| Empty unit | Save requires an image, or free text, or a field with a value. | A unit is content. |
| One album | A unit belongs to one album. | Cross-album reuse can wait. |
| Theme reference | Store the image's concrete path, and nothing else. | Render stays a file lookup. Coupling text to images is later. |
| Variety | Pick and Shuffle write one path. Generate uses that path. No roll at generate time. | A late roll changes a picture the operator saved. |
| Ownership | Global. An admin owns every source. Brand and campaign scope later. | One ops team, until a house brand. |
| Bytes | Disk under `ARTIFACT_STORAGE_DIR`, behind `save`, `open`, and `delete`. S3 is a later implementation. | Prod is one EC2. |
| Thumbnails | Yes, for unit images in the grid. | A grid of full frames is the wrong preview. |
| Delete | Block when a theme or an artifact still stores that image path. A resource may be deleted in this slice. | Removing an image file would change a saved theme. Nothing points at a resource yet. |
| Image intake | Admin upload and URL import. | A file on hand, or a link, with no vendor. |
| Resource intake | Upload only. Replace the file to change the body. | The operator already compiled the document. |
| Resource note | One required provenance note on the resource. | Notes, not a citation manager. |
| Licensed proof | A required `license_note` when the license is `licensed`. | "With proof" needs a place to put the proof. |
| Texture | Later, as an album of image-only units. | Background kinds stay picture, color, or gradient. |
| Default | An admin may add units. The six packaged photos are the seed. | Default is the first album, not a special lock. |

---

## Data model

**`sources`**

| Column | Notes |
|---|---|
| `id` | UUID. |
| `kind` | `album` or `resource`. |
| `name` | Shown in the UI. |
| `slug` | Unique. Default's slug is `default`. |
| `created_at`, `updated_at` | |

An album is a source with `kind = album`. It has units. A resource is a source with `kind = resource`. It has one file and no units.

**`units`**

| Column | Notes |
|---|---|
| `id` | UUID. |
| `source_id` | FK → `sources`. That source is an album. |
| `position` | Order in the album. |
| `free_text` | Optional body. A poem lives here. |
| `tags` | Text list. Optional. |
| `created_at`, `updated_at` | |

**`unit_fields`**

| Column | Notes |
|---|---|
| `id` | UUID. |
| `unit_id` | FK → `units`. |
| `position` | Order on the unit. |
| `label` | Key, such as `name`, `price`, `description`. |
| `value` | Text. |

**`unit_images`**

| Column | Notes |
|---|---|
| `id` | UUID. |
| `unit_id` | FK → `units`. |
| `position` | Order inside the unit. |
| `relative_path` | Unique. What a theme or artifact stores. |
| `media_type` | `svg`, `png`, or `jpeg`. |
| `byte_size` | |
| `width`, `height` | Null for SVG. |
| `alt_text` | Optional. |
| `license` | `cc0`, `public_domain`, `owned`, or `licensed`. |
| `source` | Required. Where this image came from. A URL or a short note. |
| `license_note` | Required when `license` is `licensed`. Otherwise empty. |
| `intake` | `upload` or `url`. |
| `thumbnail_path` | Null for SVG. |
| `created_at`, `updated_at` | |

**`resource_files`**

| Column | Notes |
|---|---|
| `source_id` | PK, FK → `sources`. That source is a resource. |
| `relative_path` | The uploaded file. |
| `media_type` | `markdown` or `plain`. |
| `byte_size` | |
| `original_filename` | |
| `provenance` | Required. Where the synthesis came from. |

Save is rejected when a unit has no image and no text, when an image license is outside the allowlist, when image source is blank, when `licensed` has no note, when resource provenance is blank, or when a file fails the limits below.

---

## Storage and limits

**Proposed.** New image bytes go under `ARTIFACT_STORAGE_DIR` at `albums/<source_id>/<unit_id>/<image_id>.<ext>`. Thumbnails are JPEG, longest edge 480. SVG is stored as-is and has no thumbnail; the grid uses the SVG.

A resource file goes at `resources/<source_id>/body.md` or `body.txt`. The bytes are the upload, unchanged.

The packaged Default files stay in `apps/server/app/themes/default_images/`. Their `relative_path` stays `theme-defaults/<filename>`. The renderer keeps resolving that prefix from the package. Other paths resolve under `ARTIFACT_STORAGE_DIR`.

Callers use `save`, `open`, and `delete`. The first implementation is the local disk. S3, when it is no longer parked, is another implementation.

| Limit | Proposed |
|---|---|
| Image formats | SVG, PNG, JPEG. Same suffixes a theme asset ref already allows. |
| Image size | 8 MB per file. |
| URL import | The server downloads the URL once. Render does not fetch it again. Same size and type limits. |
| Thumbnail | Raster only. Longest edge 480, JPEG. |
| Resource formats | `.md` and `.txt` only. |
| Resource size | 2 MB per file. |

---

## How a theme picks an image

The picture background and the image element browse albums, then units that have at least one image, then the images in that unit. Text-only units stay out of this picker.

**Proposed.** The picker shows the unit's free text, or its first field, as a caption beside those images, so the lamp photos read as that lamp. The caption is not copied onto the theme.

Choosing an image stores that image's `relative_path` on `background_asset_ref` or `image_asset_ref`. Shuffle stores a different image path from the same album. Samples, live preview, and generate read that stored path. A missing file is a missing-asset error. There is no substitute picture.

An old path that belongs to no unit stays "Saved image" and still renders when the file exists.

The unit's text, fields, and tags stay on the unit. Putting them on a frame is the later combination step.

---

## Migrating Default

**Decided.** The six packaged photos become an album of six image-only units.

Seed one source, kind `album`, name Default, slug `default`. One unit per file in `default_images/`, each with one `unit_images` row and no free text, fields, or tags. `relative_path` stays `theme-defaults/…`, so themes that already store those paths do not need a rewrite. `license` and `source` come from `default_images/LICENSES.md` (`cc0` or `public_domain`). `intake` is `upload`. The grid may use the packaged JPEG as its thumbnail.

The package remains the source for that prefix. The bytes are not copied onto the artifact disk.

---

## API

Readers may GET. Admins may change. Same rule as themes.

| Call | Behavior |
|---|---|
| `GET /api/v1/sources?kind=` | Albums or resources. |
| `POST /api/v1/sources` | `{name, kind}`. Slug from the name. A resource also takes `provenance` and the file. |
| `GET /api/v1/sources/{id}` | One album with its units, or one resource with its note and file name. |
| `PATCH /api/v1/sources/{id}` | Name. For a resource, provenance. |
| `DELETE /api/v1/sources/{id}` | Album: 409 when any of its image paths is in use. Resource: allowed in this slice, because nothing points at it yet. |
| `POST /api/v1/sources/{id}/units` | Create a unit on an album. |
| `PATCH /api/v1/sources/{id}/units/{unit_id}` | Free text, tags, and fields. |
| `DELETE …/units/{unit_id}` | 409 when any of its image paths is in use. |
| `POST …/units/{unit_id}/images` | Multipart upload plus license, source, optional alt and license note. |
| `POST …/units/{unit_id}/images/import` | `{url, license, source, …}`. The server stores the bytes. |
| `PATCH` / `DELETE` one image | Metadata only on PATCH. DELETE is 409 when a theme or artifact stores that `relative_path`. |
| `PUT …/resource` | Replace the Markdown or TXT file. |
| `GET` file or thumbnail | Stream it for a signed-in operator, including readers. |

A bad license, a blank source, a missing license note, a bad type, or a file over the size limit is 400. Nothing is written.

---

## Ops UI

One Sources area. Two tabs. No new visual system.

**Albums.** A list: name, unit count. Admin can create one.

**Album.** A grid of units. A card shows the first thumbnail, or a text excerpt when the unit has no image, plus tags. Admin can add a unit and delete one. Delete explains the block when an image is in use.

**Unit.** Images, with upload and URL import. Each image has license, source, optional alt, and the license note when the license is `licensed`. Below that: free text, labeled fields (add or remove a row), and tags. Save enforces the empty-unit rule and the license allowlist.

**Resources.** A list: name. Admin uploads a `.md` or `.txt` and a provenance note.

**Resource.** The note, and the file shown as text. Admin can replace the file and edit the note. Changing the body means uploading a new file.

**Theme editor.** Picture and image controls list these albums, then units that have images, then the images. Pick and Shuffle still store a concrete path.

Readers see the lists, the unit, the resource text, and the theme control. They cannot create, upload, import, edit, or delete.

---

## Permissions

| Role | Sources |
|---|---|
| Reader | List and open albums, units, images, thumbnails, and resources. |
| Admin | Create, upload, import, edit, and delete when unused. |

Ownership is global, as proposed above. There is no per-source owner.

---

## MVP and later

**MVP**

Build order is the [Phase plan](#phase-plan).

- Sources, units, fields, tags, unit images, and one file per resource
- Upload and URL import for images. Upload for Markdown and TXT
- License allowlist on each image. Provenance note on each resource
- Thumbnails. Disk storage behind an interface
- Default seeded as six image-only units. Existing `theme-defaults/…` paths unchanged
- Theme picker and Shuffle store a concrete image path
- Delete of an image, unit, or album blocked when that path is in use
- Admin writes, reader reads

**Later, besides the combination section below**

- PDF upload, and building a resource from several inputs
- Brand or campaign ownership of a source
- Texture as an album of image-only units
- S3 behind the same storage interface
- WebP, once a theme asset ref allows it

---

## Later: campaign combination rules and model

A campaign will say how to combine sources. Two shapes Mu already described:

- Use an album's units directly, so the coupled text stays with its images.
- Pick a resource that holds a lot of text, plus an image-only album. An agent pulls facts from the resource, chooses images by their tags, and lays text over those images.

That choosing, and the model that does it, are out of this slice. v2 only gives them a source to name: an album of units, or a resource file.

---

## Still open

The table above already recommends an answer for each of these. They stay open because only Mu knows if that recommendation matches what he wants.

1. For `licensed`, the table uses a short note. Is that enough proof, or do you want a URL or an attached file as well?
2. The table stores only the image path on the theme. Should the theme also store the unit id, so the coupled text can be found without a search?
3. The table keeps every source global until a house brand exists. Do you want per-brand sources as soon as the first brand does?
4. The table lets an admin add units to Default. Should those six packaged photos stay frozen instead?

---

## Phase plan

Build in this order. Each phase ships something a reviewer can test without the later phases. The phases follow the **Proposed** table. Still-open items 1–4 are the forks that would change a phase.

**Phase 1 — Model and Default.** **Migration:** yes. One Alembic revision after `themes_element_rectangle`. Do not edit that revision. Tables `sources`, `units`, `unit_fields`, and `unit_images`, as in the data model. Seed one album, slug `default`, with six image-only units. Each `relative_path` stays `theme-defaults/…`. License and source come from `default_images/LICENSES.md`. Bytes stay in the package. Read API: `GET /api/v1/sources?kind=album` and `GET /api/v1/sources/{id}`. Readers may GET. **Done when:** a clean database migrates; a test reads Default and the six units with those paths and `cc0` or `public_domain`; a theme that already stores one of those paths still renders; no theme row is rewritten. **Out of scope:** ops pages, upload, URL import, thumbnails, resources, the theme picker, write and delete routes.

**Phase 2 — Albums and units in ops.** **Migration:** no. Write API for albums and units: create, rename, edit free text, fields, tags, and the license, source, alt, and note on an image that already exists. Reject an empty unit, a license outside the allowlist, a blank image source, and `licensed` with no note. Delete of an image, unit, or album is 409 while a theme or artifact stores that path. Ops: Sources, an Albums tab, a units grid, and a unit editor. The grid shows the packaged JPEG for a `theme-defaults/` path, streamed with the existing package resolver. Admin writes. Reader reads. **Done when:** an admin creates an album and a text-only unit with a field and a tag, reloads, and sees them; deleting a Default image whose path a theme stores returns 409 and the row remains; a reader cannot save. **Out of scope:** new image bytes, URL import, generated thumbnails, the Resources tab, replacing the hard-coded theme album list.

**Phase 3 — Image intake.** **Migration:** no. `thumbnail_path` is already on `unit_images`. Disk storage behind `save`, `open`, and `delete`, prefix `albums/<source_id>/<unit_id>/<image_id>.<ext>` under `ARTIFACT_STORAGE_DIR`. Multipart upload and URL import. The server downloads a URL once. SVG, PNG, or JPEG, 8 MB. The same license gate as Phase 2; a failure writes nothing. Thumbnail JPEG, longest edge 480. SVG has no thumbnail. The unit editor gains upload and import. The grid uses the thumbnail when one exists. **Done when:** an admin uploads a JPEG and imports a PNG from a URL, both appear with license and source, a file over 8 MB or a missing license note is 400 and leaves no row, and a theme path from Phase 1 still resolves. **Out of scope:** S3, WebP, resources, pointing the theme picker at the new albums.

**Phase 4 — Resources.** **Migration:** yes. Table `resource_files`, as in the data model. Upload `.md` or `.txt`, stored as-is, 2 MB, with a required provenance note. Replacing the file is a new upload. Ops: a Resources tab, the note, and the file as text. Delete is allowed, because nothing points at a resource yet. **Done when:** an admin uploads a Markdown file and a note, reloads, and the bytes match; a `.txt` works; a PDF or a blank note is 400; a reader can open the text and cannot upload. **Out of scope:** PDF conversion, auto-synthesis, tags on a resource, campaign links, image changes.

**Phase 5 — Theme pickers.** **Migration:** no. Themes keep `background_asset_ref` and `image_asset_ref`. The picture and image controls list albums, then units that have an image, then those images. Text-only units stay off the picker. A caption from free text or the first field is display only. Pick and Shuffle store one concrete path. Samples, live preview, and generate read that path. An unknown path stays "Saved image". This replaces the hard-coded Default catalog. **Done when:** an admin picks one Default image and one uploaded image, reloads, and both stored paths are those files; Shuffle writes a different path once and a second sample uses the saved path; a reader sees the list and cannot upload. **Out of scope:** a unit id on the theme, generate-time random, copying unit text onto the frame, resources in the picker.

**Later.** **Migration:** none in this plan. Not part of the v2 build. Campaign combination rules and the model, as in [Later: campaign combination rules and model](#later-campaign-combination-rules-and-model): a unit's text with its images, or a resource plus an image-only album chosen by tags. Also S3 as another storage implementation, brand or campaign ownership, texture as an album of image-only units, PDF and multi-input synthesis, and WebP once a theme asset ref allows it. **Done when:** a later doc, after Mu answers the still-open list. **Out of scope:** the whole of this phase, for v2.
