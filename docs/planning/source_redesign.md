# Source Redesign: Theme-Bound Sources

## Why

Matching and content decisions move to source-creation time, so the output becomes predictable. On-the-fly generation at campaign time was rejected because it publishes unreviewed output.

- Keep the term "sources". The album / content / resource naming debate is dropped.
- Drop the album-versus-resource distinction. Every source is one thing.
- Create source asks only for a name and a required theme. There is no algorithmic theme-source matching at the campaign layer.
- Old sources that do not fit the new structure can be deleted.
- Opening a source shows units that follow the selected theme: an image field only if the theme requires an image, plus one text input per theme text element.
- One image per unit. To test text variants on the same image, add more units that reuse it.
- Each unit gets an ID/name.
- Per-unit exclusion rules: a unit declares other unit IDs it cannot be shown with, so random carousel picks never repeat the same story/image pairing.
- Optional theme enhancement, not required now: word-count limits or warnings on text elements, leaning toward a warning rather than a hard block.
- In-source preview while developing.
- Generation: images are uploaded manually. Text comes from an LLM using inspiration and rules inside the source, and is reviewed before it goes live.
- Campaign flow: pick a theme first, then a dropdown of matching sources, pick one, and run. The campaign assembles already-reviewed content.
