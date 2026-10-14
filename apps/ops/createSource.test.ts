import assert from "node:assert/strict";

import {
  CREATE_SOURCE_FILE_ERROR,
  CREATE_SOURCE_NAME_ERROR,
  CREATE_SOURCE_PROVENANCE_ERROR,
  CREATE_SOURCE_TYPE_ERROR,
  createSourceFieldError,
} from "./src/pages/createSource.ts";

assert.equal(createSourceFieldError("album", "  ", "", null), CREATE_SOURCE_NAME_ERROR);
assert.equal(createSourceFieldError("album", "Shelf", "", null), null);
assert.equal(createSourceFieldError("album", "Shelf", "", "notes.pdf"), null);

assert.equal(createSourceFieldError("resource", "", "From the bench.", "notes.md"), CREATE_SOURCE_NAME_ERROR);
assert.equal(
  createSourceFieldError("resource", "Notes", "   ", "notes.md"),
  CREATE_SOURCE_PROVENANCE_ERROR,
);
assert.equal(
  createSourceFieldError("resource", "Notes", "From the bench.", null),
  CREATE_SOURCE_FILE_ERROR,
);
assert.equal(
  createSourceFieldError("resource", "Notes", "From the bench.", "notes.pdf"),
  CREATE_SOURCE_TYPE_ERROR,
);
assert.equal(createSourceFieldError("resource", "Notes", "From the bench.", "Notes.MD"), null);
assert.equal(createSourceFieldError("resource", "Notes", "From the bench.", "notes.txt"), null);
