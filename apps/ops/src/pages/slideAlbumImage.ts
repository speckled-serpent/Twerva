import type {
  AlbumImageReadResponse,
  SkeletonElementReadResponse,
  SkeletonReadResponse,
  SlideElementTextWrite,
  SlideImageReadResponse,
  SlideReadResponse,
  SlideWriteRequest,
} from "../api/types";
import { ALBUM_HAS_NO_IMAGES_COPY } from "./carouselContent.ts";
import { orderedTextElements, textDraftsForSkeleton } from "./slideSkeletonShape.ts";

/** Attached album with no images. The operator adds them on Content. */
export const SLIDE_ALBUM_EMPTY_COPY: string =
  `${ALBUM_HAS_NO_IMAGES_COPY} Add images on Content.`;

/** Picture skeleton opened with no album. Slides is normally locked first. */
export const SLIDE_ALBUM_MISSING_COPY: string =
  "No album is attached. Choose or create one on Content.";

/** Picture skeleton saved with no chosen image. Matches the slide write 400. */
export const SLIDE_IMAGE_REQUIRED_COPY: string =
  "This skeleton needs an image on the slide.";

/** An admin chooses one image from the carousel's album. */
export const SLIDE_ALBUM_PICK_HINT: string =
  "Choose an image from this carousel's album.";

/** A reader can see the album images and cannot change the slide's image. */
export const SLIDE_ALBUM_READONLY_COPY: string =
  "Choosing the slide image is an admin action.";

/**
 * Album images in the order the album stores them.
 *
 * Every image stays in the list. Two slides may point at one image.
 *
 * @param images - Images on the attached album
 * @returns A new list, lowest position first
 */
export function albumImagesInPositionOrder(
  images: readonly AlbumImageReadResponse[],
): AlbumImageReadResponse[] {

  const orderedImages: AlbumImageReadResponse[] = [...images].sort(
    (left: AlbumImageReadResponse, right: AlbumImageReadResponse): number => {

      if (left.position !== right.position) {
        return left.position - right.position;
      }

      return left.id.localeCompare(right.id);
    },
  );

  return orderedImages;
}

/**
 * Album image the slide already points at.
 *
 * The slide read lists that image as `images`, and the id is the
 * album image id. A new slide has none yet.
 *
 * @param slide - The open slide, or null while adding one
 * @returns The album image id, or null when the slide has no image
 */
export function savedSlideAlbumImageId(slide: SlideReadResponse | null): string | null {

  if (slide === null) {
    return null;
  }

  const savedImage: SlideImageReadResponse | undefined = slide.images[0];

  if (savedImage === undefined) {
    return null;
  }

  return savedImage.id;
}

/**
 * Client check before creating or saving a picture slide.
 *
 * A skeleton that needs no picture does not ask for an image. A picture
 * skeleton needs one chosen from the album. The server repeats this.
 *
 * @param needsImage - True when the skeleton uses a slide image
 * @param albumImageId - The chosen or already stored album image, or null
 * @returns The error to show, or null when the save can include the image
 */
export function slideImageRequiredError(
  needsImage: boolean,
  albumImageId: string | null,
): string | null {

  if (!needsImage || albumImageId !== null) {
    return null;
  }

  return SLIDE_IMAGE_REQUIRED_COPY;
}

/**
 * Name, text, and exclusion save. The image field is left out.
 *
 * Omitting `album_image_id` keeps the slide's current image. This is
 * the autosave body for an existing slide, and for a new slide whose
 * skeleton does not use a picture.
 *
 * @param name - Trimmed slide name
 * @param texts - One value per skeleton text element
 * @param excludedSlideIds - Other slides this one cannot be shown with
 * @returns The slide write body, without an image id
 */
export function slideTextSaveRequest(
  name: string,
  texts: readonly SlideElementTextWrite[],
  excludedSlideIds: readonly string[],
): SlideWriteRequest {

  const slideWriteRequest: SlideWriteRequest = {
    name,
    texts: [...texts],
    excluded_slide_ids: [...excludedSlideIds],
  };

  return slideWriteRequest;
}

/**
 * Create body for a picture slide. The chosen album image is the only image field.
 *
 * No file and no URL are sent. The image already lives on the album.
 *
 * @param name - Trimmed slide name
 * @param texts - One value per skeleton text element
 * @param excludedSlideIds - Other slides this one cannot be shown with
 * @param albumImageId - An image on the carousel's album
 * @returns The slide create body
 */
export function newPictureSlideWriteRequest(
  name: string,
  texts: readonly SlideElementTextWrite[],
  excludedSlideIds: readonly string[],
  albumImageId: string,
): SlideWriteRequest {

  const slideWriteRequest: SlideWriteRequest = slideTextSaveRequest(
    name,
    texts,
    excludedSlideIds,
  );
  slideWriteRequest.album_image_id = albumImageId;

  return slideWriteRequest;
}

/**
 * Save that stores one album image on an existing slide.
 *
 * Name, text, and exclusions are the stored slide, not unsaved form
 * edits. Choosing an image does not save those fields. A set
 * `album_image_id` is what this body changes.
 *
 * @param slide - The saved slide
 * @param skeleton - The carousel's skeleton
 * @param albumImageId - The album image the operator chose
 * @returns The slide PATCH body
 */
export function imageChoiceWriteRequest(
  slide: SlideReadResponse,
  skeleton: SkeletonReadResponse,
  albumImageId: string,
): SlideWriteRequest {

  const storedDrafts: Record<string, string> = textDraftsForSkeleton(skeleton, slide);
  const textElements: SkeletonElementReadResponse[] = orderedTextElements(skeleton.elements);
  const storedTexts: SlideElementTextWrite[] = textElements.map(
    (element: SkeletonElementReadResponse): SlideElementTextWrite => {

      const textWrite: SlideElementTextWrite = {
        skeleton_element_id: element.id,
        value: storedDrafts[element.id] ?? "",
      };

      return textWrite;
    },
  );
  const slideWriteRequest: SlideWriteRequest = slideTextSaveRequest(
    slide.name,
    storedTexts,
    slide.excluded_slide_ids,
  );
  slideWriteRequest.album_image_id = albumImageId;

  return slideWriteRequest;
}
