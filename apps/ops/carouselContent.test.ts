import assert from "node:assert/strict";

import type { AlbumListItemResponse } from "./src/api/types.ts";
import {
  ALBUM_HAS_NO_IMAGES_COPY,
  ALBUM_NAME_REQUIRED_COPY,
  ALBUM_OPTIONAL_COPY,
  ALBUM_REQUIRED_COPY,
  albumActionErrorText,
  albumImageCountLabel,
  albumsToChoose,
  detachedAlbumCopy,
} from "./src/pages/carouselContent.ts";

const SLIDES_STILL_POINT: string =
  "Slides still point at that album's images, so clear those slide images first.";

assert.equal(detachedAlbumCopy(true), ALBUM_REQUIRED_COPY);
assert.match(ALBUM_REQUIRED_COPY, /skeleton needs an album/);
assert.match(ALBUM_REQUIRED_COPY, /Choose or create one/);
assert.equal(detachedAlbumCopy(false), ALBUM_OPTIONAL_COPY);
assert.match(ALBUM_OPTIONAL_COPY, /No album is attached/);
assert.match(ALBUM_OPTIONAL_COPY, /do not use a picture/);
assert.equal(ALBUM_HAS_NO_IMAGES_COPY, "This album has no images yet.");
assert.equal(ALBUM_NAME_REQUIRED_COPY, "Name is required.");
assert.equal(albumImageCountLabel(0), "0 images");
assert.equal(albumImageCountLabel(1), "1 image");
assert.equal(albumImageCountLabel(6), "6 images");

const conflict: { detailText: string } = { detailText: SLIDES_STILL_POINT };
assert.equal(albumActionErrorText(conflict), SLIDES_STILL_POINT);
assert.equal(albumActionErrorText(new Error("Album not found: missing")), "Album not found: missing");
assert.equal(albumActionErrorText("nope"), "The album could not be changed.");

const harbor: AlbumListItemResponse = albumItem("harbor", "Harbor", 2);
const defaultAlbum: AlbumListItemResponse = albumItem("default", "Default", 6);
const amber: AlbumListItemResponse = albumItem("amber", "Amber", 0);

assert.deepEqual(
  albumsToChoose([harbor, defaultAlbum, amber], null, false).map(albumName),
  ["Amber", "Default", "Harbor"],
);
assert.deepEqual(
  albumsToChoose([harbor, defaultAlbum], defaultAlbum.id, true).map(albumName),
  ["Harbor"],
);
assert.deepEqual(
  albumsToChoose([defaultAlbum], defaultAlbum.id, true).map(albumName),
  [],
);

function albumItem(id: string, name: string, imageCount: number): AlbumListItemResponse {

  return {
    id,
    name,
    slug: id,
    image_count: imageCount,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function albumName(album: AlbumListItemResponse): string {

  return album.name;
}
