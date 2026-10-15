import assert from "node:assert/strict";

import {
  CREATE_SOURCE_NAME_ERROR,
  CREATE_SOURCE_THEME_ERROR,
  createSourceFieldError,
} from "./src/pages/createSource.ts";

assert.equal(createSourceFieldError("  ", "theme-1"), CREATE_SOURCE_NAME_ERROR);
assert.equal(createSourceFieldError("Shelf", ""), CREATE_SOURCE_THEME_ERROR);
assert.equal(createSourceFieldError("Shelf", "theme-1"), null);
