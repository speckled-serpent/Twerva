import assert from "node:assert/strict";

import type { AlbumReadResponse } from "./src/api/types.ts";
import {
  assetRefAfterShuffle,
  assetRefForAlbumChoice,
  albumForAssetRef,
  captionForSlide,
  chooseAlbumAssetRef,
  pickDefaultAlbumImage,
  skeletonAlbumFromAlbum,
  DEFAULT_ALBUM_ID,
  type SkeletonImageAlbum,
} from "./src/pages/skeletonAssets.ts";

const defaultAlbum: SkeletonImageAlbum = {
  album_id: DEFAULT_ALBUM_ID,
  name: "Default",
  slug: "default",
  asset_refs: [
    "theme-defaults/hong-kong-skyline.jpg",
    "theme-defaults/ocean-waves.jpg",
    "theme-defaults/utah-dunes.jpg",
  ],
  slides: [],
};

assert.equal(
  chooseAlbumAssetRef(defaultAlbum.asset_refs, null, 0),
  "theme-defaults/hong-kong-skyline.jpg",
);
assert.equal(
  chooseAlbumAssetRef(defaultAlbum.asset_refs, "theme-defaults/hong-kong-skyline.jpg", 0),
  "theme-defaults/ocean-waves.jpg",
);
assert.equal(
  chooseAlbumAssetRef(defaultAlbum.asset_refs, null, 0.99),
  "theme-defaults/utah-dunes.jpg",
);
assert.equal(
  chooseAlbumAssetRef(["theme-defaults/only.jpg"], "theme-defaults/only.jpg", 0),
  "theme-defaults/only.jpg",
);

assert.equal(
  assetRefForAlbumChoice(defaultAlbum, "theme-defaults/utah-dunes.jpg", 0),
  "theme-defaults/utah-dunes.jpg",
);
assert.equal(
  assetRefForAlbumChoice(defaultAlbum, "backgrounds/harbor.png", 0),
  "theme-defaults/hong-kong-skyline.jpg",
);

const shuffledRef: string | null = assetRefAfterShuffle(
  [defaultAlbum],
  DEFAULT_ALBUM_ID,
  "theme-defaults/hong-kong-skyline.jpg",
  0,
);
assert.equal(shuffledRef, "theme-defaults/ocean-waves.jpg");
assert.notEqual(shuffledRef, "theme-defaults/hong-kong-skyline.jpg");

assert.equal(
  albumForAssetRef([defaultAlbum], "theme-defaults/ocean-waves.jpg")?.album_id,
  DEFAULT_ALBUM_ID,
);
assert.equal(albumForAssetRef([defaultAlbum], "backgrounds/harbor.png"), null);

assert.throws(
  (): string => chooseAlbumAssetRef([], null, 0),
  /Album has no images/,
);
assert.equal(
  pickDefaultAlbumImage([defaultAlbum], 0),
  "theme-defaults/hong-kong-skyline.jpg",
);
assert.throws(
  (): string => pickDefaultAlbumImage([], 0),
  /Default album has no images/,
);

const storedAfterShuffle: string | null = shuffledRef;
assert.equal(
  assetRefForAlbumChoice(defaultAlbum, storedAfterShuffle ?? "", 0.4),
  storedAfterShuffle,
);

assert.equal(captionForSlide(["  Brass lamp  ", "ignored"]), "Brass lamp");
assert.equal(captionForSlide(["  ", "First field"]), "First field");
assert.equal(captionForSlide([]), "");

const uploadedAlbum: AlbumReadResponse = {
  id: "album-1",
  name: "Lamps",
  slug: "lamps",
  created_at: "2026-10-14T00:00:00Z",
  updated_at: "2026-10-14T00:00:00Z",
  images: [
    {
      id: "image-1",
      position: 0,
      relative_path: "albums/album-1/image-1.jpg",
      media_type: "jpeg",
      byte_size: 12,
      width: 8,
      height: 8,
      alt_text: "Desk lamp",
      license: "owned",
      source: "bench",
      license_note: "",
      intake: "upload",
      thumbnail_path: "albums/album-1/image-1-thumb.jpg",
    },
  ],
};
const lamps: SkeletonImageAlbum = skeletonAlbumFromAlbum(uploadedAlbum);
assert.equal(lamps.slides.length, 1);
assert.equal(lamps.slides[0]?.caption, "Desk lamp");
assert.equal(lamps.asset_refs[0], "albums/album-1/image-1.jpg");
assert.equal(lamps.slides[0]?.images[0]?.hasThumbnail, true);
assert.equal(albumForAssetRef([lamps], "albums/album-1/image-1.jpg")?.album_id, "album-1");
