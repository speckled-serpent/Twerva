import type {
  AccountCreateRequest,
  AccountReadResponse,
  ArtifactApproveRequest,
  ArtifactRegenerateRequest,
  ArtifactPatchRequest,
  ArtifactReadResponse,
  ArtifactStatus,
  CarouselTemplateReadResponse,
  BrandReadResponse,
  CampaignCreateRequest,
  CampaignReadResponse,
  SkeletonCreateRequest,
  SkeletonElementCreateRequest,
  SkeletonElementPatchRequest,
  SkeletonElementReadResponse,
  SkeletonPreviewRequest,
  SkeletonPreviewResponse,
  SkeletonDefaultImagesResponse,
  SkeletonFontFamiliesResponse,
  SkeletonPatchRequest,
  SkeletonReadResponse,
  SkeletonSampleRequest,
  SkeletonSampleResponse,
  SlideImageCreatePayload,
  SlideImageImportRequest,
  SlideImageLicense,
  SlideImageMetadataPatch,
  SlideImageReadResponse,
  SlidePreviewRequest,
  SlideReadResponse,
  SlideWriteRequest,
  CarouselGenerateRequest,
  ClusterAgentSummaryResponse,
  ClusterCreateRequest,
  ClusterMetricsSummaryResponse,
  ClusterReadResponse,
  ClusterSteerRequest,
  HealthReadResponse,
  MetricSnapshotReadResponse,
  OpsChangePasswordRequest,
  OpsChangePasswordResponse,
  OpsLoginRequest,
  OpsUserCreateRequest,
  OpsUserReadResponse,
  OpsUserResetPasswordRequest,
  OpsUserRolePatchRequest,
  PostJobReadResponse,
  SchedulePostJobRequest,
  AlbumCreateRequest,
  AlbumImageReadResponse,
  AlbumListItemResponse,
  AlbumPatchRequest,
  AlbumReadResponse,
  ResearchCreateRequest,
  ResearchListItemResponse,
  ResearchPatchRequest,
  ResearchReadResponse,
  CarouselAlbumAttachRequest,
  CarouselAlbumCreateRequest,
  CarouselCreateRequest,
  CarouselGuidancePatchRequest,
  TextGenerationStatusResponse,
  SlideAcceptTextRequest,
  SourceItemCreateRequest,
  SourceItemReadResponse,
  CarouselListItemResponse,
  CarouselPatchRequest,
  CarouselStepPatchRequest,
  CarouselReadResponse,
  SpotmuInterestSearchHit,
  SteerActionReadResponse,
} from "./types";
import {
  albumImageFilePath,
  albumImageImportPath,
  albumImageItemPath,
  albumImagesPath,
  albumImageThumbnailPath,
} from "./albumImagePaths";

export const UNAUTHORIZED_EVENT_NAME: string = "twerva:unauthorized";

/**
 * Error thrown when the Twerva API returns a non-success status.
 */
export class ApiClientError extends Error {
  readonly statusCode: number;
  readonly detailText: string;

  constructor(statusCode: number, detailText: string) {
    super(`API ${statusCode}: ${detailText}`);
    this.name = "ApiClientError";
    this.statusCode = statusCode;
    this.detailText = detailText;
  }
}

/**
 * Resolve the API origin.
 *
 * Empty string means relative URLs (`/api/...`, `/health`) so the Vite
 * dev proxy can forward to `http://127.0.0.1:8000`. Set
 * `VITE_API_BASE_URL` to talk to another origin (preview, tunnel).
 *
 * @returns Origin without a trailing slash, or an empty string
 */
export function resolveApiBaseUrl(): string {

  const configuredBaseUrl: string | undefined = import.meta.env.VITE_API_BASE_URL;

  if (configuredBaseUrl === undefined) {
    return "";
  }

  const trimmedBaseUrl: string = configuredBaseUrl.trim();

  if (trimmedBaseUrl === "") {
    return "";
  }

  return trimmedBaseUrl.replace(/\/$/, "");
}

export async function fetchHealthStatus(): Promise<HealthReadResponse> {

  return requestJson<HealthReadResponse>("GET", "/health");
}

export async function fetchCurrentOpsOperator(): Promise<OpsUserReadResponse> {

  return requestJson<OpsUserReadResponse>("GET", "/api/v1/auth/me");
}

export async function loginOpsOperator(
  opsLoginRequest: OpsLoginRequest,
): Promise<OpsUserReadResponse> {

  return requestJson<OpsUserReadResponse>(
    "POST",
    "/api/v1/auth/login",
    opsLoginRequest,
  );
}

export async function logoutOpsOperator(): Promise<void> {

  await requestJson<{ status: string }>("POST", "/api/v1/auth/logout");
}

export async function changeOwnOpsPassword(
  opsChangePasswordRequest: OpsChangePasswordRequest,
): Promise<OpsChangePasswordResponse> {

  return requestJson<OpsChangePasswordResponse>(
    "POST",
    "/api/v1/auth/change-password",
    opsChangePasswordRequest,
  );
}

export async function listOpsUsers(): Promise<OpsUserReadResponse[]> {

  return requestJson<OpsUserReadResponse[]>("GET", "/api/v1/auth/users");
}

export async function createOpsUser(
  opsUserCreateRequest: OpsUserCreateRequest,
): Promise<OpsUserReadResponse> {

  return requestJson<OpsUserReadResponse>(
    "POST",
    "/api/v1/auth/users",
    opsUserCreateRequest,
  );
}

export async function patchOpsUserRole(
  opsUserId: string,
  opsUserRolePatchRequest: OpsUserRolePatchRequest,
): Promise<OpsUserReadResponse> {

  return requestJson<OpsUserReadResponse>(
    "PATCH",
    `/api/v1/auth/users/${opsUserId}`,
    opsUserRolePatchRequest,
  );
}

export async function resetOpsUserPassword(
  opsUserId: string,
  opsUserResetPasswordRequest: OpsUserResetPasswordRequest,
): Promise<OpsChangePasswordResponse> {

  return requestJson<OpsChangePasswordResponse>(
    "POST",
    `/api/v1/auth/users/${opsUserId}/reset-password`,
    opsUserResetPasswordRequest,
  );
}

export async function listBrands(): Promise<BrandReadResponse[]> {

  return requestJson<BrandReadResponse[]>("GET", "/api/v1/brands");
}

export async function listCampaigns(): Promise<CampaignReadResponse[]> {

  return requestJson<CampaignReadResponse[]>("GET", "/api/v1/campaigns");
}

export async function fetchCampaignById(campaignId: string): Promise<CampaignReadResponse> {

  return requestJson<CampaignReadResponse>("GET", `/api/v1/campaigns/${campaignId}`);
}

export async function createCampaign(
  campaignCreateRequest: CampaignCreateRequest,
): Promise<CampaignReadResponse> {

  return requestJson<CampaignReadResponse>(
    "POST",
    "/api/v1/campaigns",
    campaignCreateRequest,
  );
}

export async function runCampaign(campaignId: string): Promise<CampaignReadResponse> {

  return requestJson<CampaignReadResponse>("POST", `/api/v1/campaigns/${campaignId}/run`);
}

export async function listCarousels(): Promise<CarouselListItemResponse[]> {

  return requestJson<CarouselListItemResponse[]>("GET", "/api/v1/carousels");
}

export async function fetchCarouselById(sourceId: string): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>("GET", `/api/v1/carousels/${sourceId}`);
}

export async function createCarousel(
  sourceCreateRequest: CarouselCreateRequest,
): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>("POST", "/api/v1/carousels", sourceCreateRequest);
}

export async function renameCarousel(
  sourceId: string,
  sourcePatchRequest: CarouselPatchRequest,
): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>(
    "PATCH",
    `/api/v1/carousels/${sourceId}`,
    sourcePatchRequest,
  );
}

/**
 * Store the open carousel step. Admin only. A locked step is refused.
 *
 * @param sourceId - Carousel UUID
 * @param stepPatchRequest - The step to open: 0 Basic, 2 Content, or 3 Slides
 * @returns The carousel, including the stored step and derived step states
 */
export async function patchCarouselStep(
  sourceId: string,
  stepPatchRequest: CarouselStepPatchRequest,
): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>(
    "PATCH",
    `/api/v1/carousels/${sourceId}/step`,
    stepPatchRequest,
  );
}

/**
 * Point the carousel at an album that already exists. Admin only.
 *
 * Replacing the attached album is 409 while a slide still points at
 * one of that album's images. The stored album stays.
 *
 * @param sourceId - Carousel UUID
 * @param attachRequest - Existing album id
 * @returns The carousel, including the attached album and step states
 */
export async function attachCarouselAlbum(
  sourceId: string,
  attachRequest: CarouselAlbumAttachRequest,
): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>(
    "PUT",
    `/api/v1/carousels/${sourceId}/album`,
    attachRequest,
  );
}

/**
 * Create an album by name and point the carousel at it. Admin only.
 *
 * The name follows `POST /api/v1/albums`. A blank name is 400. Replacing
 * the attached album is 409 while a slide still points at one of that
 * album's images, and that refusal does not create the album.
 *
 * @param sourceId - Carousel UUID
 * @param createRequest - Album name
 * @returns The carousel, including the new album and step states
 */
export async function createCarouselAlbum(
  sourceId: string,
  createRequest: CarouselAlbumCreateRequest,
): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/album`,
    createRequest,
  );
}

/**
 * Clear the carousel's album. The album row and its files stay. Admin only.
 *
 * Clearing is 409 while a slide still points at one of that album's
 * images, including the Default album. The stored album stays.
 *
 * @param sourceId - Carousel UUID
 * @returns The carousel, with a null album when the clear was stored
 */
export async function clearCarouselAlbum(
  sourceId: string,
): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>(
    "DELETE",
    `/api/v1/carousels/${sourceId}/album`,
  );
}

export async function fetchTextGenerationStatus(): Promise<TextGenerationStatusResponse> {

  return requestJson<TextGenerationStatusResponse>(
    "GET",
    "/api/v1/carousels/text-generation",
  );
}

export async function patchCarouselGuidance(
  sourceId: string,
  guidanceRequest: CarouselGuidancePatchRequest,
): Promise<CarouselReadResponse> {

  return requestJson<CarouselReadResponse>(
    "PATCH",
    `/api/v1/carousels/${sourceId}/guidance`,
    guidanceRequest,
  );
}

export async function generateCarouselSlide(sourceId: string): Promise<SlideReadResponse> {

  return requestJson<SlideReadResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides/generate`,
  );
}

export async function generateSlideText(
  sourceId: string,
  slideId: string,
): Promise<SlideReadResponse> {

  return requestJson<SlideReadResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides/${slideId}/generate`,
  );
}

export async function acceptSlideText(
  sourceId: string,
  slideId: string,
  acceptRequest: SlideAcceptTextRequest,
): Promise<SlideReadResponse> {

  return requestJson<SlideReadResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides/${slideId}/accept-text`,
    acceptRequest,
  );
}

export async function deleteCarousel(sourceId: string): Promise<void> {

  await requestJson<undefined>("DELETE", `/api/v1/carousels/${sourceId}`);
}

export async function createCarouselSlide(
  sourceId: string,
  slideWriteRequest: SlideWriteRequest,
): Promise<SlideReadResponse> {

  return requestJson<SlideReadResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides`,
    slideWriteRequest,
  );
}

interface SlideImageCreateItemJson {
  kind: "file" | "url";
  file_index: number | null;
  url: string | null;
  license: SlideImageLicense;
  source: string;
  license_note: string;
}

/**
 * Create a slide and its image in one multipart call. Disk storage.
 *
 * @param sourceId - Carousel UUID
 * @param slideWriteRequest - Name and one value per skeleton text element
 * @param images - The one image when the skeleton requires one
 * @returns The created slide, including the stored image
 */
export async function createSlideWithImages(
  sourceId: string,
  slideWriteRequest: SlideWriteRequest,
  images: SlideImageCreatePayload[],
): Promise<SlideReadResponse> {

  const formData: FormData = new FormData();
  const imageItems: SlideImageCreateItemJson[] = [];
  let fileIndex: number = 0;

  for (const image of images) {
    if (image.kind === "file") {
      if (image.file === null) {
        throw new Error("Choose an image file.");
      }

      formData.append("files", image.file);
      imageItems.push({
        kind: "file",
        url: null,
        license: image.license,
        source: image.source,
        license_note: image.license_note,
        file_index: fileIndex,
      });
      fileIndex += 1;
    } else {
      imageItems.push({
        kind: "url",
        url: image.url,
        license: image.license,
        source: image.source,
        license_note: image.license_note,
        file_index: null,
      });
    }
  }

  formData.append("slide_json", JSON.stringify({
    name: slideWriteRequest.name,
    texts: slideWriteRequest.texts,
    excluded_slide_ids: slideWriteRequest.excluded_slide_ids,
    images: imageItems,
  }));

  return requestForm<SlideReadResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides/with-images`,
    formData,
  );
}

export async function patchCarouselSlide(
  sourceId: string,
  slideId: string,
  slideWriteRequest: SlideWriteRequest,
): Promise<SlideReadResponse> {

  return requestJson<SlideReadResponse>(
    "PATCH",
    `/api/v1/carousels/${sourceId}/slides/${slideId}`,
    slideWriteRequest,
  );
}

export async function deleteCarouselSlide(sourceId: string, slideId: string): Promise<void> {

  await requestJson<undefined>(
    "DELETE",
    `/api/v1/carousels/${sourceId}/slides/${slideId}`,
  );
}

export async function patchSlideImageMetadata(
  sourceId: string,
  slideId: string,
  imageId: string,
  imagePatchRequest: SlideImageMetadataPatch,
): Promise<SlideImageReadResponse> {

  return requestJson<SlideImageReadResponse>(
    "PATCH",
    `/api/v1/carousels/${sourceId}/slides/${slideId}/images/${imageId}`,
    imagePatchRequest,
  );
}

export async function deleteSlideImage(
  sourceId: string,
  slideId: string,
  imageId: string,
): Promise<void> {

  await requestJson<undefined>(
    "DELETE",
    `/api/v1/carousels/${sourceId}/slides/${slideId}/images/${imageId}`,
  );
}

export async function uploadSlideImages(
  sourceId: string,
  slideId: string,
  files: File[],
  imageLicense: SlideImageLicense,
  source: string,
  altText: string,
  licenseNote: string,
): Promise<SlideImageReadResponse[]> {

  const formData: FormData = new FormData();

  for (const file of files) {
    formData.append("files", file);
  }

  formData.append("license", imageLicense);
  formData.append("source", source);
  formData.append("alt_text", altText);
  formData.append("license_note", licenseNote);

  return requestForm<SlideImageReadResponse[]>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides/${slideId}/images`,
    formData,
  );
}

export async function importSlideImage(
  sourceId: string,
  slideId: string,
  imageImportRequest: SlideImageImportRequest,
): Promise<SlideImageReadResponse> {

  return requestJson<SlideImageReadResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides/${slideId}/images/import`,
    imageImportRequest,
  );
}

/**
 * Same-origin URL for an image that already exists. The session cookie
 * is sent with the request. This is not an upload.
 *
 * @param sourceId - Album UUID
 * @param slideId - Slide UUID
 * @param imageId - Image UUID
 * @returns Path the grid can use as an img src
 */
export function slideImageFileUrl(
  sourceId: string,
  slideId: string,
  imageId: string,
): string {

  const requestPath: string =
    `/api/v1/carousels/${sourceId}/slides/${slideId}/images/${imageId}/file`;

  return `${resolveApiBaseUrl()}${requestPath}`;
}

/**
 * Thumbnail URL when the row has one. SVG and packaged defaults do not.
 *
 * @param sourceId - Album UUID
 * @param slideId - Slide UUID
 * @param imageId - Image UUID
 * @returns Path the grid can use as an img src
 */
export function slideImageThumbnailUrl(
  sourceId: string,
  slideId: string,
  imageId: string,
): string {

  const requestPath: string =
    `/api/v1/carousels/${sourceId}/slides/${slideId}/images/${imageId}/thumbnail`;

  return `${resolveApiBaseUrl()}${requestPath}`;
}

/**
 * Prefer the thumbnail. Fall back to the original file.
 *
 * @param sourceId - Album UUID
 * @param slideId - Slide UUID
 * @param image - Image row
 * @returns img src for the grid or editor
 */
export async function listAlbums(): Promise<AlbumListItemResponse[]> {

  return requestJson<AlbumListItemResponse[]>("GET", "/api/v1/albums");
}

export async function fetchAlbumById(albumId: string): Promise<AlbumReadResponse> {

  return requestJson<AlbumReadResponse>("GET", `/api/v1/albums/${albumId}`);
}

export async function createAlbum(
  albumCreateRequest: AlbumCreateRequest,
): Promise<AlbumReadResponse> {

  return requestJson<AlbumReadResponse>("POST", "/api/v1/albums", albumCreateRequest);
}

export async function patchAlbum(
  albumId: string,
  albumPatchRequest: AlbumPatchRequest,
): Promise<AlbumReadResponse> {

  return requestJson<AlbumReadResponse>(
    "PATCH",
    `/api/v1/albums/${albumId}`,
    albumPatchRequest,
  );
}

export async function deleteAlbum(albumId: string): Promise<void> {

  await requestJson<undefined>("DELETE", `/api/v1/albums/${albumId}`);
}

export async function listResearch(): Promise<ResearchListItemResponse[]> {

  return requestJson<ResearchListItemResponse[]>("GET", "/api/v1/research");
}

export async function fetchResearchById(researchId: string): Promise<ResearchReadResponse> {

  return requestJson<ResearchReadResponse>("GET", `/api/v1/research/${researchId}`);
}

export async function createResearch(
  researchCreateRequest: ResearchCreateRequest,
): Promise<ResearchReadResponse> {

  return requestJson<ResearchReadResponse>("POST", "/api/v1/research", researchCreateRequest);
}

export async function patchResearch(
  researchId: string,
  researchPatchRequest: ResearchPatchRequest,
): Promise<ResearchReadResponse> {

  return requestJson<ResearchReadResponse>(
    "PATCH",
    `/api/v1/research/${researchId}`,
    researchPatchRequest,
  );
}

export async function deleteResearch(researchId: string): Promise<void> {

  await requestJson<undefined>("DELETE", `/api/v1/research/${researchId}`);
}

export async function uploadAlbumImage(
  albumId: string,
  file: File,
  imageLicense: SlideImageLicense,
  source: string,
  altText: string,
  licenseNote: string,
): Promise<AlbumImageReadResponse> {

  const formData: FormData = new FormData();
  formData.append("file", file);
  formData.append("license", imageLicense);
  formData.append("source", source);
  formData.append("alt_text", altText);
  formData.append("license_note", licenseNote);

  return requestForm<AlbumImageReadResponse>(
    "POST",
    albumImagesPath(albumId),
    formData,
  );
}

export async function importAlbumImage(
  albumId: string,
  imageImportRequest: SlideImageImportRequest,
): Promise<AlbumImageReadResponse> {

  return requestJson<AlbumImageReadResponse>(
    "POST",
    albumImageImportPath(albumId),
    imageImportRequest,
  );
}

export async function deleteAlbumImage(albumId: string, imageId: string): Promise<void> {

  await requestJson<undefined>(
    "DELETE",
    albumImageItemPath(albumId, imageId),
  );
}

/**
 * Same-origin URL for an image stored on an album.
 *
 * @param albumId - Album UUID
 * @param imageId - Image UUID
 * @returns Path the grid can use as an img src
 */
export function albumImageFileUrl(albumId: string, imageId: string): string {

  const requestPath: string = albumImageFilePath(albumId, imageId);

  return `${resolveApiBaseUrl()}${requestPath}`;
}

/**
 * Thumbnail URL when the album image has one.
 *
 * @param albumId - Album UUID
 * @param imageId - Image UUID
 * @returns Path the grid can use as an img src
 */
export function albumImageThumbnailUrl(albumId: string, imageId: string): string {

  const requestPath: string = albumImageThumbnailPath(albumId, imageId);

  return `${resolveApiBaseUrl()}${requestPath}`;
}

/**
 * Prefer the album thumbnail. Fall back to the original file.
 *
 * @param albumId - Album UUID
 * @param image - Image row
 * @returns img src for the album editor or the skeleton picker
 */
export function albumImageDisplayUrl(
  albumId: string,
  image: AlbumImageReadResponse,
): string {

  if (image.thumbnail_path !== null && image.thumbnail_path !== "") {
    return albumImageThumbnailUrl(albumId, image.id);
  }

  return albumImageFileUrl(albumId, image.id);
}

export function slideImageDisplayUrl(
  sourceId: string,
  slideId: string,
  image: SlideImageReadResponse,
): string {

  if (image.thumbnail_path !== null && image.thumbnail_path !== "") {
    return slideImageThumbnailUrl(sourceId, slideId, image.id);
  }

  return slideImageFileUrl(sourceId, slideId, image.id);
}

export async function listSkeletons(): Promise<SkeletonReadResponse[]> {

  return requestJson<SkeletonReadResponse[]>("GET", "/api/v1/skeletons");
}

export async function fetchSkeletonById(skeletonId: string): Promise<SkeletonReadResponse> {

  return requestJson<SkeletonReadResponse>("GET", `/api/v1/skeletons/${skeletonId}`);
}

export async function fetchSkeletonDefaultImages(): Promise<SkeletonDefaultImagesResponse> {

  return requestJson<SkeletonDefaultImagesResponse>("GET", "/api/v1/skeletons/default-images");
}

export async function fetchSkeletonFontFamilies(): Promise<SkeletonFontFamiliesResponse> {

  return requestJson<SkeletonFontFamiliesResponse>("GET", "/api/v1/skeletons/font-families");
}

export async function createSkeleton(
  skeletonCreateRequest: SkeletonCreateRequest,
): Promise<SkeletonReadResponse> {

  return requestJson<SkeletonReadResponse>(
    "POST",
    "/api/v1/skeletons",
    skeletonCreateRequest,
  );
}

export async function patchSkeleton(
  skeletonId: string,
  skeletonPatchRequest: SkeletonPatchRequest,
): Promise<SkeletonReadResponse> {

  return requestJson<SkeletonReadResponse>(
    "PATCH",
    `/api/v1/skeletons/${skeletonId}`,
    skeletonPatchRequest,
  );
}

/**
 * Copy one skeleton into a new Draft. The carousel row is not modified.
 *
 * @param skeletonId - Carousel skeleton UUID
 * @returns The new Draft skeleton
 */
/**
 * Delete one skeleton and its elements.
 *
 * @param skeletonId - Skeleton UUID
 * @returns Nothing when the skeleton is gone
 */
export async function deleteSkeleton(skeletonId: string): Promise<void> {

  await requestJson<undefined>("DELETE", `/api/v1/skeletons/${skeletonId}`);
}

export async function duplicateSkeleton(skeletonId: string): Promise<SkeletonReadResponse> {

  return requestJson<SkeletonReadResponse>(
    "POST",
    `/api/v1/skeletons/${skeletonId}/duplicate`,
  );
}

/**
 * Render one skeleton preview. Does not create an artifact or a post job.
 *
 * @param skeletonId - Skeleton UUID
 * @param skeletonSampleRequest - The one Spotmu source item to render
 * @returns The preview id and any block reason
 */
/**
 * Render one frame from the form payload. Does not save a skeleton.
 *
 * @param skeletonPreviewRequest - Frame, elements, and preview text as they stand
 * @returns The PNG and any block reason
 */
/**
 * Draw the carousel skeleton with this slide's text and saved image.
 *
 * The PNG is inline. No slide, artifact, or preview file is written.
 *
 * @param sourceId - Carousel UUID
 * @param previewRequest - Unsaved text and an optional saved slide id
 * @returns The frame and any block reason
 */
export async function previewCarouselSlide(
  sourceId: string,
  previewRequest: SlidePreviewRequest,
): Promise<SkeletonPreviewResponse> {

  return requestJson<SkeletonPreviewResponse>(
    "POST",
    `/api/v1/carousels/${sourceId}/slides/preview`,
    previewRequest,
  );
}

export async function createSkeletonPreview(
  skeletonPreviewRequest: SkeletonPreviewRequest,
): Promise<SkeletonPreviewResponse> {

  return requestJson<SkeletonPreviewResponse>(
    "POST",
    "/api/v1/skeletons/preview",
    skeletonPreviewRequest,
  );
}

export async function createSkeletonSample(
  skeletonId: string,
  skeletonSampleRequest: SkeletonSampleRequest,
): Promise<SkeletonSampleResponse> {

  return requestJson<SkeletonSampleResponse>(
    "POST",
    `/api/v1/skeletons/${skeletonId}/samples`,
    skeletonSampleRequest,
  );
}

/**
 * Load one preview PNG. The session cookie is required.
 *
 * @param skeletonId - Skeleton UUID
 * @param previewId - Preview UUID from the samples response
 * @returns PNG bytes
 */
export async function fetchSkeletonSampleImageBlob(
  skeletonId: string,
  previewId: string,
): Promise<Blob> {

  const requestPath: string = `/api/v1/skeletons/${skeletonId}/samples/${previewId}/image`;
  const response: Response = await sendApiRequest("GET", requestPath);

  await throwIfResponseFailed(response, requestPath);

  const imageBlob: Blob = await response.blob();

  return imageBlob;
}

export async function createSkeletonElement(
  skeletonId: string,
  skeletonElementCreateRequest: SkeletonElementCreateRequest,
): Promise<SkeletonElementReadResponse> {

  return requestJson<SkeletonElementReadResponse>(
    "POST",
    `/api/v1/skeletons/${skeletonId}/elements`,
    skeletonElementCreateRequest,
  );
}

export async function patchSkeletonElement(
  skeletonId: string,
  elementId: string,
  skeletonElementPatchRequest: SkeletonElementPatchRequest,
): Promise<SkeletonElementReadResponse> {

  return requestJson<SkeletonElementReadResponse>(
    "PATCH",
    `/api/v1/skeletons/${skeletonId}/elements/${elementId}`,
    skeletonElementPatchRequest,
  );
}

export async function deleteSkeletonElement(
  skeletonId: string,
  elementId: string,
): Promise<void> {

  await requestJson<undefined>(
    "DELETE",
    `/api/v1/skeletons/${skeletonId}/elements/${elementId}`,
  );
}

export async function startCampaign(campaignId: string): Promise<CampaignReadResponse> {

  return requestJson<CampaignReadResponse>("POST", `/api/v1/campaigns/${campaignId}/start`);
}

export async function pauseCampaign(campaignId: string): Promise<CampaignReadResponse> {

  return requestJson<CampaignReadResponse>("POST", `/api/v1/campaigns/${campaignId}/pause`);
}

export async function resumeCampaign(campaignId: string): Promise<CampaignReadResponse> {

  return requestJson<CampaignReadResponse>("POST", `/api/v1/campaigns/${campaignId}/resume`);
}

export async function finishCampaign(campaignId: string): Promise<CampaignReadResponse> {

  return requestJson<CampaignReadResponse>("POST", `/api/v1/campaigns/${campaignId}/finish`);
}

export async function searchSpotmuInterests(
  query: string,
  limit?: number,
): Promise<SpotmuInterestSearchHit[]> {

  const trimmedQuery: string = query.trim();
  const queryParts: string[] = [`q=${encodeURIComponent(trimmedQuery)}`];

  if (limit !== undefined) {
    queryParts.push(`limit=${encodeURIComponent(String(limit))}`);
  }

  return requestJson<SpotmuInterestSearchHit[]>(
    "GET",
    `/api/v1/spotmu/interests/search?${queryParts.join("&")}`,
  );
}

export async function listSourceItems(): Promise<SourceItemReadResponse[]> {

  return requestJson<SourceItemReadResponse[]>("GET", "/api/v1/source-items");
}

export async function createSourceItem(
  sourceItemCreateRequest: SourceItemCreateRequest,
): Promise<SourceItemReadResponse> {

  return requestJson<SourceItemReadResponse>(
    "POST",
    "/api/v1/source-items",
    sourceItemCreateRequest,
  );
}

export async function generateCarouselArtifact(
  carouselGenerateRequest: CarouselGenerateRequest,
): Promise<ArtifactReadResponse> {

  return requestJson<ArtifactReadResponse>(
    "POST",
    "/api/v1/generate/carousel",
    carouselGenerateRequest,
  );
}

export async function listCarouselTemplates(): Promise<CarouselTemplateReadResponse[]> {

  return requestJson<CarouselTemplateReadResponse[]>("GET", "/api/v1/generate/templates");
}

export async function regenerateCarouselArtifact(
  artifactId: string,
  artifactRegenerateRequest?: ArtifactRegenerateRequest,
): Promise<ArtifactReadResponse> {

  return requestJson<ArtifactReadResponse>(
    "POST",
    `/api/v1/artifacts/${artifactId}/regenerate`,
    artifactRegenerateRequest ?? {},
  );
}

/**
 * Build the authenticated slide-image path (session cookie required).
 *
 * @param artifactId - Artifact UUID
 * @param slideIndex - 0-based slide index
 * @returns API path under `/api/v1/artifacts`
 */
export function buildArtifactSlideImagePath(artifactId: string, slideIndex: number): string {

  return `/api/v1/artifacts/${artifactId}/slides/${slideIndex}/image`;
}

export async function fetchArtifactSlideImageBlob(
  artifactId: string,
  slideIndex: number,
): Promise<Blob> {

  const requestPath: string = buildArtifactSlideImagePath(artifactId, slideIndex);
  const response: Response = await sendApiRequest("GET", requestPath);

  await throwIfResponseFailed(response, requestPath);

  const imageBlob: Blob = await response.blob();

  return imageBlob;
}

export async function listArtifacts(
  artifactStatus?: ArtifactStatus,
): Promise<ArtifactReadResponse[]> {

  const queryString: string =
    artifactStatus === undefined ? "" : `?status=${encodeURIComponent(artifactStatus)}`;

  return requestJson<ArtifactReadResponse[]>(
    "GET",
    `/api/v1/artifacts${queryString}`,
  );
}

export async function approveArtifact(
  artifactId: string,
  artifactApproveRequest?: ArtifactApproveRequest,
): Promise<ArtifactReadResponse> {

  return requestJson<ArtifactReadResponse>(
    "POST",
    `/api/v1/artifacts/${artifactId}/approve`,
    artifactApproveRequest ?? {},
  );
}

export async function rejectArtifact(artifactId: string): Promise<ArtifactReadResponse> {

  return requestJson<ArtifactReadResponse>(
    "POST",
    `/api/v1/artifacts/${artifactId}/reject`,
    {},
  );
}

export async function patchArtifact(
  artifactId: string,
  artifactPatchRequest: ArtifactPatchRequest,
): Promise<ArtifactReadResponse> {

  return requestJson<ArtifactReadResponse>(
    "PATCH",
    `/api/v1/artifacts/${artifactId}`,
    artifactPatchRequest,
  );
}

export async function listClusters(): Promise<ClusterReadResponse[]> {

  return requestJson<ClusterReadResponse[]>("GET", "/api/v1/clusters");
}

export async function createCluster(
  clusterCreateRequest: ClusterCreateRequest,
): Promise<ClusterReadResponse> {

  return requestJson<ClusterReadResponse>(
    "POST",
    "/api/v1/clusters",
    clusterCreateRequest,
  );
}

export async function listAccounts(): Promise<AccountReadResponse[]> {

  return requestJson<AccountReadResponse[]>("GET", "/api/v1/accounts");
}

export async function createAccount(
  accountCreateRequest: AccountCreateRequest,
): Promise<AccountReadResponse> {

  return requestJson<AccountReadResponse>(
    "POST",
    "/api/v1/accounts",
    accountCreateRequest,
  );
}

export async function schedulePostJob(
  schedulePostJobRequest: SchedulePostJobRequest,
): Promise<PostJobReadResponse> {

  return requestJson<PostJobReadResponse>(
    "POST",
    "/api/v1/schedule",
    schedulePostJobRequest,
  );
}

export async function listPostJobs(): Promise<PostJobReadResponse[]> {

  return requestJson<PostJobReadResponse[]>("GET", "/api/v1/post-jobs");
}

export async function publishPostJob(postJobId: string): Promise<PostJobReadResponse> {

  return requestJson<PostJobReadResponse>(
    "POST",
    `/api/v1/publish/run/${postJobId}`,
  );
}

export async function createStubPostJobMetrics(
  postJobId: string,
): Promise<MetricSnapshotReadResponse> {

  return requestJson<MetricSnapshotReadResponse>(
    "POST",
    `/api/v1/post-jobs/${postJobId}/metrics/stub`,
  );
}

export async function steerCluster(
  clusterId: string,
  clusterSteerRequest: ClusterSteerRequest,
): Promise<SteerActionReadResponse> {

  return requestJson<SteerActionReadResponse>(
    "POST",
    `/api/v1/clusters/${clusterId}/steer`,
    clusterSteerRequest,
  );
}

export async function fetchClusterMetricsSummary(
  clusterId: string,
): Promise<ClusterMetricsSummaryResponse> {

  return requestJson<ClusterMetricsSummaryResponse>(
    "GET",
    `/api/v1/clusters/${clusterId}/metrics/summary`,
  );
}

export async function fetchClusterAgentSummaryJson(
  clusterId: string,
): Promise<ClusterAgentSummaryResponse> {

  return requestJson<ClusterAgentSummaryResponse>(
    "GET",
    `/api/v1/clusters/${clusterId}/agent-summary`,
  );
}

export async function fetchClusterAgentSummaryMarkdown(clusterId: string): Promise<string> {

  return requestText("GET", `/api/v1/clusters/${clusterId}/agent-summary?format=markdown`);
}

async function requestForm<ResponseBody>(
  method: string,
  path: string,
  formData: FormData,
): Promise<ResponseBody> {

  const response: Response = await sendApiRequest(method, path, undefined, formData);

  await throwIfResponseFailed(response, path);

  const parsedJson: unknown = await response.json();

  return parsedJson as ResponseBody;
}

async function requestJson<ResponseBody>(
  method: string,
  path: string,
  body?: unknown,
): Promise<ResponseBody> {

  const response: Response = await sendApiRequest(method, path, body);

  await throwIfResponseFailed(response, path);

  if (response.status === 204) {
    return undefined as ResponseBody;
  }

  const parsedJson: unknown = await response.json();

  return parsedJson as ResponseBody;
}

async function requestText(method: string, path: string): Promise<string> {

  const response: Response = await sendApiRequest(method, path);

  await throwIfResponseFailed(response, path);

  const responseText: string = await response.text();

  return responseText;
}

async function sendApiRequest(
  method: string,
  path: string,
  body?: unknown,
  formData?: FormData,
): Promise<Response> {

  const apiBaseUrl: string = resolveApiBaseUrl();
  const requestUrl: string = `${apiBaseUrl}${path}`;
  const requestHeaders: HeadersInit = {};
  const fetchInit: RequestInit = {
    method,
    headers: requestHeaders,
    credentials: "include",
  };

  if (formData !== undefined) {
    fetchInit.body = formData;
  } else if (body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
    fetchInit.body = JSON.stringify(body);
  }

  const response: Response = await fetch(requestUrl, fetchInit);

  return response;
}

async function throwIfResponseFailed(
  response: Response,
  requestPath: string,
): Promise<void> {

  if (response.ok) {
    return;
  }

  if (response.status === 401 && requestPath !== "/api/v1/auth/login") {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT_NAME));
  }

  const detailText: string = await readErrorTextFromResponse(response);

  throw new ApiClientError(response.status, detailText);
}

async function readErrorTextFromResponse(response: Response): Promise<string> {

  const rawBodyText: string = await response.text();

  if (rawBodyText.trim() === "") {
    return response.statusText || `HTTP ${response.status}`;
  }

  try {
    const parsedBody: unknown = JSON.parse(rawBodyText);
    const formattedDetail: string = formatApiErrorDetail(parsedBody);

    return formattedDetail;
  } catch {
    return rawBodyText;
  }
}

function formatApiErrorDetail(parsedBody: unknown): string {

  if (typeof parsedBody === "string") {
    return parsedBody;
  }

  if (parsedBody === null || typeof parsedBody !== "object") {
    return "Request failed.";
  }

  const bodyRecord: Record<string, unknown> = parsedBody as Record<string, unknown>;
  const detailValue: unknown = bodyRecord.detail;

  if (typeof detailValue === "string") {
    return detailValue;
  }

  if (Array.isArray(detailValue)) {
    const messages: string[] = detailValue.map(formatValidationDetailItem);

    return messages.join("; ");
  }

  if (detailValue !== undefined) {
    return JSON.stringify(detailValue);
  }

  return JSON.stringify(parsedBody);
}

function formatValidationDetailItem(detailItem: unknown): string {

  if (typeof detailItem === "string") {
    return detailItem;
  }

  if (detailItem === null || typeof detailItem !== "object") {
    return String(detailItem);
  }

  const detailRecord: Record<string, unknown> = detailItem as Record<string, unknown>;
  const messageValue: unknown = detailRecord.msg;
  const locationValue: unknown = detailRecord.loc;

  if (typeof messageValue === "string" && Array.isArray(locationValue)) {
    const locationText: string = locationValue.map(String).join(".");

    return `${locationText}: ${messageValue}`;
  }

  if (typeof messageValue === "string") {
    return messageValue;
  }

  return JSON.stringify(detailItem);
}
