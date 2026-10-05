# Task 1.10f-i — Overlap

*2026-10-05*

Leaf **1.10f-i** only. Samples and the ops editor stay undone.
Letter 1.10f is this one leaf.

## Done

- `find_band_overlaps` in `apps/server/app/themes/overlap.py` checks
  each placed instance on its own.
- Rectangles from different bands overlap when their areas intersect.
  Sharing an edge is allowed. A same-band stack with gap zero or more
  is not an overlap. Zero elements is not blocked.
- The result is `{blocked, overlaps: [{band_a, band_b, element_ids}]}`
  per instance. Coordinates are not changed, and Middle and Bottom are
  not pushed.

## Trade-offs

- Each intersecting pair of elements is its own overlap record.
  `band_a` is the earlier band.
- The check reads rectangles it is given. It does not call layout or
  measurement.

## Next

- **1.10g** generate samples.

## Scripts

- `apps/server/app/themes/overlap.py`
- `apps/server/tests/test_theme_overlap.py` (tall top through middle
  stays blocked at the original `y`, an edge-touching pair is allowed,
  a two-instance call flags only the colliding instance)
