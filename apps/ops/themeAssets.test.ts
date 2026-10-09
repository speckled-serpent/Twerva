import assert from "node:assert/strict";

import {
  assetRefAfterShuffle,
  assetRefForAlbumChoice,
  albumForAssetRef,
  chooseAlbumAssetRef,
  DEFAULT_ALBUM_ID,
  type ThemeImageAlbum,
} from "./src/pages/themeAssets.ts";

const defaultAlbum: ThemeImageAlbum = {
  album_id: DEFAULT_ALBUM_ID,
  name: "Default",
  asset_refs: [
    "theme-defaults/hong-kong-skyline.jpg",
    "theme-defaults/ocean-waves.jpg",
    "theme-defaults/utah-dunes.jpg",
  ],
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
