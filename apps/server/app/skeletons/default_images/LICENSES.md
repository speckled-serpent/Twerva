# Default skeleton images

These JPEGs ship inside the `app.skeletons` package (`default_images/`).
`pyproject.toml` lists them as package data, so a production install of
the server can read them without copying files into `ARTIFACT_STORAGE_DIR`
(`/opt/twerva/artifacts` in production, `./data/artifacts` locally). That
directory is a runtime volume and is not part of the git tree.

A skeleton stores a concrete relative path such as
`theme-defaults/utah-dunes.jpg`. The renderer resolves the
`theme-defaults/` prefix from this directory. Any other `asset_ref`
still resolves under `ARTIFACT_STORAGE_DIR`. An old path keeps rendering
when that file is in the store, and a missing file still surfaces as a
missing-asset error.

Each photo below is public domain or CC0 1.0. Anyone may use it for any
purpose, including commercial use, with no attribution and no other
conditions. The copies in this directory are center-cropped to 1080×1920
and saved as JPEG. The resize does not add a license condition.

Do not add CC BY, CC BY-SA, or current Unsplash or Pexels license files.

## hong-kong-skyline.jpg

- Source: https://commons.wikimedia.org/wiki/File:Hong_Kong_skyscrapers_in_a_night_of_typhoon.jpg
- Author: Wilfredor
- License: CC0 1.0 Universal Public Domain Dedication. The file page uses `{{self|cc-zero}}`. Commons license name: "CC0". Usage terms: "Creative Commons Zero, Public Domain Dedication". Deed: https://creativecommons.org/publicdomain/zero/1.0/deed.en

## joshua-tree-desert.jpg

- Source: https://commons.wikimedia.org/wiki/File:A_Desert_Landscape_(53437341027).jpg
- Author: Joshua Tree National Park
- License: Public domain. The file page uses `{{PD-USGov-NPS}}` (work of the U.S. National Park Service, created by an employee as part of official duties). Commons license name: "Public domain". Flickr review of https://flickr.com/photos/115357548@N08/53437341027 passed with review license "Public Domain Mark". No attribution or other conditions.

## ocean-waves.jpg

- Source: https://commons.wikimedia.org/wiki/File:Waves_in_sea.jpg
- Author: Saral Shots
- License: CC0 1.0 Universal Public Domain Dedication. The file page uses `{{self|cc-zero}}`. Commons license name: "CC0". Usage terms: "Creative Commons Zero, Public Domain Dedication". Deed: https://creativecommons.org/publicdomain/zero/1.0/deed.en

## santa-cruz-pacific.jpg

- Source: https://commons.wikimedia.org/wiki/File:Pacific_Ocean_along_Cliff_Drive,_Santa_Cruz_CA_Aug_2019.jpg
- Author: Thomson200
- License: CC0 1.0 Universal Public Domain Dedication. The file page uses `{{self|cc-zero}}`. Commons license name: "CC0". Usage terms: "Creative Commons Zero, Public Domain Dedication". Deed: https://creativecommons.org/publicdomain/zero/1.0/deed.en

## seoul-skyline.jpg

- Source: https://commons.wikimedia.org/wiki/File:Seoul_Skyline_Night_2018.jpg
- Author: mauveine.kim
- License: CC0 1.0 Universal Public Domain Dedication. The file page uses `{{cc0}}`. FlickreviewR passed https://www.flickr.com/photos/161399994@N08/44531748074 with review license `cc-zero`. Commons license name: "CC0". Usage terms: "Creative Commons Zero, Public Domain Dedication". Deed: https://creativecommons.org/publicdomain/zero/1.0/deed.en

## utah-dunes.jpg

- Source: https://commons.wikimedia.org/wiki/File:Utah_Dunes_Landscape_-_West_Desert_District.jpg
- Author: Bureau of Land Management - Utah / Bob Wick
- License: Public domain. The file page uses `{{PD-USGov-BLM}}` (work of the U.S. Bureau of Land Management, created by an employee as part of official duties). Commons license name: "Public domain". Flickr review of https://www.flickr.com/photos/blmutah/49992112532 passed with review license "Public Domain Mark". No attribution or other conditions.
