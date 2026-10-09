# Albums v1

*Last updated: 2026-10-09*
*Status: Draft consolidation. Not a design. Mu will lock the model after review.*

This note gathers what Themes already decided about albums, and lists the features a later albums or content system would need. It does not pick a schema, an API, or a storage layout.

Mu may call the concept **Content** rather than **Albums**. **Library** is the other name in play. This doc says "album" for what the theme editor already has, and leaves the product name open.

Related: [`themes_v1.md`](themes_v1.md), [`docs/prompts/project.md`](../prompts/project.md), [`docs/prompts/product.md`](../prompts/product.md).

---

## Already decided

These are in the product or the code today. They are not proposals.

**Spotmu is customer zero.** Theme text still comes from a Spotmu interest: title, interest heading, overview bullets, or the public URL. Picture backgrounds and image elements are optional. Albums matter less while the hose is that text. They matter more in Phase 3, when an internal house brand's editorial is the hose and a suite of images has to vary without becoming one photo on repeat.

**One album exists: Default.** The theme image dropdown was built to list albums. Only Default is registered. It is the bundled photos in `apps/server/app/themes/default_images/`, shipped as package data so prod can read them without copying files onto the artifact disk.

**A theme stores a concrete path.** Choosing Default, or Shuffle, picks one file once and saves `theme-defaults/<filename>`. Sample and preview render that file. They do not roll again. Shuffle only changes the path when the operator asks. An old path that is not in the album stays selected as "Saved image". A missing file is a missing-asset error, not a substitute picture.

**Those six photos are CC0 or public domain.** `default_images/LICENSES.md` records family-level source, author, and license for each file. CC BY, CC BY-SA, and current Unsplash or Pexels terms are not acceptable for this set.

**Texture is not a background kind.** It was removed. A texture is a picture of a texture, and it may come back later as a default album of texture images, not as its own kind.

**Upload is deferred.** [`themes_v1.md`](themes_v1.md) says an image element is a stored file, and that upload, storage, and serving are later work. Non-Spotmu text sources are deferred the same way. The frame holds a path. It does not grow an upload pipeline.

**Bytes for generated posts stay on one disk.** Prod is one EC2 box, Postgres, and `ARTIFACT_STORAGE_DIR` (`/opt/twerva/artifacts` on the server). S3 is parked until volume or more than one host needs it. The Default album is the exception: those JPEGs live in the package, not under that directory. Any other asset ref still resolves there.

---

## Features a later system would need

A plain list. Order is not priority. Each line is a capability, not a design.

1. **A name** operators will say: Albums, Content, or Library.
2. **What a collection holds.** Images only, or also text snippets, fonts, colors, and other brand material.
3. **More than one collection.** Default stays. A texture set is the likely second. House-brand sets come with Phase 3.
4. **Who owns a collection.** Global (like Default), a brand, or a campaign.
5. **A record of each asset**, not only a filename: license, source, author, alt text, tags, dimensions.
6. **Provenance on the way in.** Upload, URL import, licensed stock, Spotmu-supplied, or generated. The license has to be known before the file can ship. The Default set is the bar we already used.
7. **Where the bytes live.** Disk now, S3 when the parked storage decision moves. Originals, thumbnails, allowed formats (svg, png, jpeg, webp), and size limits.
8. **How a theme points at an asset.** Today's rule is a concrete path. The other shape is "use this album" and choose at sample or generate time. Shuffle showed the tradeoff: a stored path stays still; a late roll changes the picture under a theme the operator already saved.
9. **Variety at generate time.** A campaign or a batch may want the next image from an album, not the same file on every post. That rotation has to be explicit so a saved theme does not drift.
10. **Ops screens.** A list of albums, a grid for one album, add, edit metadata, and delete. Delete needs to know which themes still reference the file.
11. **The same roles as the rest of ops.** An admin changes albums. A reader can look.
12. **A way off the packaged Default album** without breaking themes that already store `theme-defaults/…`.

---

## Open questions

For Mu. Not answered here.

1. Is the product name Albums, Content, or Library?
2. Is v1 images only, with text, fonts, and colors later, or is a mixed library the point from the start?
3. Does Phase 3 brand editorial live in this same object, or beside it?
4. Who owns an album first: global, brand, or campaign?
5. Do we keep "pick once, store the path" as the only theme reference, or also allow "this album" with a choice at generate time?
6. When a batch should vary, what rotates: Shuffle by hand, next unused file, or a random pick that is then stored on the artifact?
7. Which sources are in the first upload-shaped slice: operator upload only, or also URL import and stock?
8. What license rules block an asset from being saved, beyond the CC0 / public-domain bar used for Default?
9. Do new bytes stay under `ARTIFACT_STORAGE_DIR` until S3 is actually needed?
10. Does deleting an in-use asset fail, or detach the themes that reference it?
11. Does the texture album come back with this work, or stay a later default album?
12. What is the smallest slice that is worth building before a house brand needs it?
