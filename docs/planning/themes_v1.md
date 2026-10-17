# Skeletons v1

*Last updated: 2026-10-09*
*Status: Locked model. Carousel of truth for how a Skeleton styles a carousel frame.*

Skeletons is the styling area. A skeleton is a named carousel style: background, spacing, and elements. Spotmu is customer zero. Carousel only for now. Short video and other advertisement types are outside this model.

This document locks the model. It does not change the Skeletons screens or the `skeletons` table. Until a later implementation lands, carousel pixels still come from [`carousel_template_v1.md`](carousel_template_v1.md).

Scope: the posts we ship. That is one full image, or a few lines of text and maybe a logo. Edge layouts stay deferred until someone actually needs them.

---

## Draft, Live, and Duplicate

A skeleton is **Draft** or **Live**.

| State | Use |
|---|---|
| **Draft** | The style the operator is editing. |
| **Live** | The style generation uses for posts that ship. |

**Duplicate** copies a skeleton — background, spacing, and elements — into a new Draft. The skeleton that was copied stays as it was.

---

## Frame

The frame is **1080×1920** pixels, a 9:16 phone portrait. There is no per-skeleton size.

Each concrete generated frame is one image:

- one background filling the frame
- zero or more elements on top of that background

A post may be one frame or several. Placement and overlap are checked per frame, after that frame's text has wrapped and its images have been measured.

Zero elements is valid. The frame is the background alone. The case we ship is one full background picture and nothing else.

---

## Background

A frame has one background. The background is one of:

- picture
- solid color
- gradient

Texture is dropped for now. A texture is a picture of a texture, and it may return later as a default album of texture images.

---

## Spacing

Three spacing controls:

| Control | Meaning |
|---|---|
| **Page margin** | Space between the image edge and where elements may sit. |
| **Element gap** | Space between elements. |
| **Element margin** | Space between an element's content (text or image) and the edge of that element's rectangle. |

Page margin is one value, applied at every edge of the frame. The content area is the frame inside that margin. Elements sit in the content area.

Element margin is one value. It applies between the content and each edge of that element's rectangle:

- The rectangle's width is the full content width (the frame width inside the page margin).
- The content is inset from the left and right edges of the rectangle by element margin.
- Element height is the content height plus the element margin above the content and the element margin below the content.

Element gap sits between element rectangles in the same band. It is not part of page margin, and it is not added before the first element or after the last element in a band.

---

## Elements

An element is the layout slide.

An element is (text **or** an image file: svg, png, or jpeg) plus a rectangle background. The default rectangle is clear, so only the content shows. A rectangle may be given a background; that paint stays behind the content.

Every element stretches the full horizontal content width and stacks vertically inside its band.

Each element belongs to one placement band and has an order in that band.

### Placement bands

The bands are **Top**, **Middle**, and **Bottom**. Bands are placed independently. One band does not push another out of the way.

**Top.** The first top element sits page-margin down from the top. Later top elements stack below it, with element gap between them.

**Bottom.** The same rules, measured from the bottom edge upward. The lowest element is first: it sits page-margin up from the bottom. Later bottom elements stack above it, with element gap between them.

**Middle.** The whole middle collection is centered as a group. Compute the combined height of the middle elements, including element gap between them. Place that block so its center is the vertical center of the content area. Do not center only the first or last middle element.

An empty band adds no rectangles. A skeleton with elements in only one band still places that band by the rule above.

### Text element

A text element has:

- font family
- size
- color
- bold / italic / underline / strikethrough
- font weight, when the face supports it
- alignment: left / center / right

Text needs a carousel. Spotmu carousels are fine for now. Other carousels are deferred.

Text wraps inside the content width (the rectangle width minus element margin on the left and right). Wrapping changes the content height, which changes the element height. Elements in the same band reflow with that new height. Top reflows downward from the first top element. Bottom reflows upward from the lowest element. Middle recenters the whole middle block.

### Image element

An image element shows one stored image file (svg, png, or jpeg) inside the rectangle.

The image keeps its aspect ratio. Its width is the content width. That scaled height is the content height, and element height follows the spacing rule above.

The app will need upload and storage later. Images are stored assets referenced by elements. This document does not design upload, storage, or serving.

A logo on a text frame is an image element. A full-bleed photo with no type is a background picture and zero elements.

---

## Overlap

After a frame is placed, generation checks that concrete instance.

If bands collide because of wrap or too many tall elements — for example several Top elements extending into Middle — that instance is an error. Do not push the other band out of the way. Do not move Middle or Bottom to make room.

Rectangles from different bands overlap when their areas intersect. Sharing an edge is not an overlap. An instance whose bands do not overlap is valid, including a frame with zero elements.

Generation blocks the instances that overlap and highlights them so the operator can adjust the skeleton or the carousel for that instance. Instances that do not overlap continue.

---

## Generate samples

**Generate samples** renders previews from the skeleton and sample carousel material. Previews are not outbound posts.

The same per-instance overlap check applies. Generate samples surfaces the failures and highlights the blocked previews.

---

## Spotmu carousels

Spotmu is customer zero. A text element's carousel binds to Spotmu interest material:

- `title`
- `interest_heading`
- `overview_bullets`
- the public interest URL

Other carousels are deferred.

---

## Deferred

- Short video and any non-carousel advertisement type
- Edge layouts (side-by-side elements, free placement, partial-width rectangles)
- Image upload and storage
- Text carousels other than Spotmu
