import assert from "node:assert/strict";

import type {
  AssembledCarouselReadResponse,
  AssembledFrameReadResponse,
  CarouselAssemblyReadResponse,
} from "./src/api/types.ts";
import {
  FINAL_ASSEMBLE_NEEDS_SLIDES,
  FINAL_EMPTY_NOTICE,
  finalAssembleAccessibleName,
  finalAssembleEnabled,
  finalAssembleStatusMessage,
  finalAssemblyView,
} from "./src/pages/finalAssembly.ts";

const firstFrame: AssembledFrameReadResponse = {
  id: "frame-1",
  position: 0,
  slide_id: "slide-1",
  album_image_id: null,
  blocked: false,
  block_reason: null,
  block_detail: null,
};
const secondFrame: AssembledFrameReadResponse = {
  id: "frame-2",
  position: 0,
  slide_id: "slide-2",
  album_image_id: null,
  blocked: true,
  block_reason: "overlap",
  block_detail: "top overlaps middle.",
};
const firstGroup: AssembledCarouselReadResponse = {
  id: "group-1",
  position: 0,
  status: "draft",
  caption: "Harbor",
  cta_url: null,
  blocked: false,
  frames: [firstFrame],
};
const secondGroup: AssembledCarouselReadResponse = {
  id: "group-2",
  position: 1,
  status: "draft",
  caption: "Harbor",
  cta_url: null,
  blocked: true,
  frames: [secondFrame],
};
const assembly: CarouselAssemblyReadResponse = {
  id: "assembly-1",
  generation_number: 1,
  slide_count: 5,
  carousels: [secondGroup, firstGroup],
};

const emptyView = finalAssemblyView(null);
const assembledView = finalAssemblyView(assembly);

assert.equal(finalAssembleEnabled(true, 2), true);
assert.equal(finalAssembleEnabled(false, 2), false);
assert.equal(finalAssembleEnabled(true, 1), false);
assert.equal(finalAssembleAccessibleName(1), FINAL_ASSEMBLE_NEEDS_SLIDES);
assert.equal(
  finalAssembleAccessibleName(1),
  "Assemble. Add at least two live slides first.",
);
assert.equal(finalAssembleAccessibleName(2), "Assemble");
assert.equal(emptyView.emptyNotice, FINAL_EMPTY_NOTICE);
assert.equal(
  emptyView.emptyNotice,
  "No assembly yet. Assemble draws the live slides with this skeleton.",
);
assert.equal(emptyView.groups.length, 0);
assert.notEqual(emptyView.emptyNotice, "Final assembly is a later phase.");
assert.equal(assembledView.emptyNotice, null);
assert.equal(assembledView.groups.length, 2);
assert.equal(assembledView.groups[0].label, "Carousel 1");
assert.equal(assembledView.groups[1].label, "Carousel 2");
assert.equal(assembledView.groups[0].caption, "Harbor");
assert.equal(assembledView.groups[0].frames[0].id, "frame-1");
assert.equal(assembledView.groups[1].frames[0].block_detail, "top overlaps middle.");
assert.equal(finalAssembleStatusMessage(assembledView.groups.length), "Assembled 2 carousels.");
