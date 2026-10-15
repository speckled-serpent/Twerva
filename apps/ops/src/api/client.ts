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
  ThemeCreateRequest,
  ThemeElementCreateRequest,
  ThemeElementPatchRequest,
  ThemeElementReadResponse,
  ThemePreviewRequest,
  ThemePreviewResponse,
  ThemeDefaultImagesResponse,
  ThemeFontFamiliesResponse,
  ThemePatchRequest,
  ThemeReadResponse,
  ThemeSampleRequest,
  ThemeSampleResponse,
  UnitImageCreatePayload,
  UnitImageImportRequest,
  UnitImageLicense,
  UnitImageMetadataPatch,
  UnitImageReadResponse,
  UnitPreviewRequest,
  UnitReadResponse,
  UnitWriteRequest,
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
  SourceCreateRequest,
  SourceItemCreateRequest,
  SourceItemReadResponse,
  SourceListItemResponse,
  SourcePatchRequest,
  SourceReadResponse,
  SpotmuInterestSearchHit,
  SteerActionReadResponse,
} from "./types";

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

export async function listAlbums(): Promise<SourceListItemResponse[]> {

  return requestJson<SourceListItemResponse[]>("GET", "/api/v1/sources");
}

export async function fetchSourceById(sourceId: string): Promise<SourceReadResponse> {

  return requestJson<SourceReadResponse>("GET", `/api/v1/sources/${sourceId}`);
}

export async function createAlbum(
  sourceCreateRequest: SourceCreateRequest,
): Promise<SourceReadResponse> {

  return requestJson<SourceReadResponse>("POST", "/api/v1/sources", sourceCreateRequest);
}

export async function renameSource(
  sourceId: string,
  sourcePatchRequest: SourcePatchRequest,
): Promise<SourceReadResponse> {

  return requestJson<SourceReadResponse>(
    "PATCH",
    `/api/v1/sources/${sourceId}`,
    sourcePatchRequest,
  );
}

export async function deleteSource(sourceId: string): Promise<void> {

  await requestJson<undefined>("DELETE", `/api/v1/sources/${sourceId}`);
}

export async function createSourceUnit(
  sourceId: string,
  unitWriteRequest: UnitWriteRequest,
): Promise<UnitReadResponse> {

  return requestJson<UnitReadResponse>(
    "POST",
    `/api/v1/sources/${sourceId}/units`,
    unitWriteRequest,
  );
}

interface UnitImageCreateItemJson {
  kind: "file" | "url";
  file_index: number | null;
  url: string | null;
  license: UnitImageLicense;
  source: string;
  license_note: string;
}

/**
 * Create a unit and its image in one multipart call. Disk storage.
 *
 * @param sourceId - Source UUID
 * @param unitWriteRequest - Name and one value per theme text element
 * @param images - The one image when the theme requires one
 * @returns The created unit, including the stored image
 */
export async function createUnitWithImages(
  sourceId: string,
  unitWriteRequest: UnitWriteRequest,
  images: UnitImageCreatePayload[],
): Promise<UnitReadResponse> {

  const formData: FormData = new FormData();
  const imageItems: UnitImageCreateItemJson[] = [];
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

  formData.append("unit_json", JSON.stringify({
    name: unitWriteRequest.name,
    texts: unitWriteRequest.texts,
    images: imageItems,
  }));

  return requestForm<UnitReadResponse>(
    "POST",
    `/api/v1/sources/${sourceId}/units/with-images`,
    formData,
  );
}

export async function patchSourceUnit(
  sourceId: string,
  unitId: string,
  unitWriteRequest: UnitWriteRequest,
): Promise<UnitReadResponse> {

  return requestJson<UnitReadResponse>(
    "PATCH",
    `/api/v1/sources/${sourceId}/units/${unitId}`,
    unitWriteRequest,
  );
}

export async function deleteSourceUnit(sourceId: string, unitId: string): Promise<void> {

  await requestJson<undefined>(
    "DELETE",
    `/api/v1/sources/${sourceId}/units/${unitId}`,
  );
}

export async function patchUnitImageMetadata(
  sourceId: string,
  unitId: string,
  imageId: string,
  imagePatchRequest: UnitImageMetadataPatch,
): Promise<UnitImageReadResponse> {

  return requestJson<UnitImageReadResponse>(
    "PATCH",
    `/api/v1/sources/${sourceId}/units/${unitId}/images/${imageId}`,
    imagePatchRequest,
  );
}

export async function deleteUnitImage(
  sourceId: string,
  unitId: string,
  imageId: string,
): Promise<void> {

  await requestJson<undefined>(
    "DELETE",
    `/api/v1/sources/${sourceId}/units/${unitId}/images/${imageId}`,
  );
}

export async function uploadUnitImages(
  sourceId: string,
  unitId: string,
  files: File[],
  imageLicense: UnitImageLicense,
  source: string,
  altText: string,
  licenseNote: string,
): Promise<UnitImageReadResponse[]> {

  const formData: FormData = new FormData();

  for (const file of files) {
    formData.append("files", file);
  }

  formData.append("license", imageLicense);
  formData.append("source", source);
  formData.append("alt_text", altText);
  formData.append("license_note", licenseNote);

  return requestForm<UnitImageReadResponse[]>(
    "POST",
    `/api/v1/sources/${sourceId}/units/${unitId}/images`,
    formData,
  );
}

export async function importUnitImage(
  sourceId: string,
  unitId: string,
  imageImportRequest: UnitImageImportRequest,
): Promise<UnitImageReadResponse> {

  return requestJson<UnitImageReadResponse>(
    "POST",
    `/api/v1/sources/${sourceId}/units/${unitId}/images/import`,
    imageImportRequest,
  );
}

/**
 * Same-origin URL for an image that already exists. The session cookie
 * is sent with the request. This is not an upload.
 *
 * @param sourceId - Album UUID
 * @param unitId - Unit UUID
 * @param imageId - Image UUID
 * @returns Path the grid can use as an img src
 */
export function unitImageFileUrl(
  sourceId: string,
  unitId: string,
  imageId: string,
): string {

  const requestPath: string =
    `/api/v1/sources/${sourceId}/units/${unitId}/images/${imageId}/file`;

  return `${resolveApiBaseUrl()}${requestPath}`;
}

/**
 * Thumbnail URL when the row has one. SVG and packaged defaults do not.
 *
 * @param sourceId - Album UUID
 * @param unitId - Unit UUID
 * @param imageId - Image UUID
 * @returns Path the grid can use as an img src
 */
export function unitImageThumbnailUrl(
  sourceId: string,
  unitId: string,
  imageId: string,
): string {

  const requestPath: string =
    `/api/v1/sources/${sourceId}/units/${unitId}/images/${imageId}/thumbnail`;

  return `${resolveApiBaseUrl()}${requestPath}`;
}

/**
 * Prefer the thumbnail. Fall back to the original file.
 *
 * @param sourceId - Album UUID
 * @param unitId - Unit UUID
 * @param image - Image row
 * @returns img src for the grid or editor
 */
export function unitImageDisplayUrl(
  sourceId: string,
  unitId: string,
  image: UnitImageReadResponse,
): string {

  if (image.thumbnail_path !== null && image.thumbnail_path !== "") {
    return unitImageThumbnailUrl(sourceId, unitId, image.id);
  }

  return unitImageFileUrl(sourceId, unitId, image.id);
}

export async function listThemes(): Promise<ThemeReadResponse[]> {

  return requestJson<ThemeReadResponse[]>("GET", "/api/v1/themes");
}

export async function fetchThemeById(themeId: string): Promise<ThemeReadResponse> {

  return requestJson<ThemeReadResponse>("GET", `/api/v1/themes/${themeId}`);
}

export async function fetchThemeDefaultImages(): Promise<ThemeDefaultImagesResponse> {

  return requestJson<ThemeDefaultImagesResponse>("GET", "/api/v1/themes/default-images");
}

export async function fetchThemeFontFamilies(): Promise<ThemeFontFamiliesResponse> {

  return requestJson<ThemeFontFamiliesResponse>("GET", "/api/v1/themes/font-families");
}

export async function createTheme(
  themeCreateRequest: ThemeCreateRequest,
): Promise<ThemeReadResponse> {

  return requestJson<ThemeReadResponse>(
    "POST",
    "/api/v1/themes",
    themeCreateRequest,
  );
}

export async function patchTheme(
  themeId: string,
  themePatchRequest: ThemePatchRequest,
): Promise<ThemeReadResponse> {

  return requestJson<ThemeReadResponse>(
    "PATCH",
    `/api/v1/themes/${themeId}`,
    themePatchRequest,
  );
}

/**
 * Copy one theme into a new Draft. The source row is not modified.
 *
 * @param themeId - Source theme UUID
 * @returns The new Draft theme
 */
/**
 * Delete one theme and its elements.
 *
 * @param themeId - Theme UUID
 * @returns Nothing when the theme is gone
 */
export async function deleteTheme(themeId: string): Promise<void> {

  await requestJson<undefined>("DELETE", `/api/v1/themes/${themeId}`);
}

export async function duplicateTheme(themeId: string): Promise<ThemeReadResponse> {

  return requestJson<ThemeReadResponse>(
    "POST",
    `/api/v1/themes/${themeId}/duplicate`,
  );
}

/**
 * Render one theme preview. Does not create an artifact or a post job.
 *
 * @param themeId - Theme UUID
 * @param themeSampleRequest - The one Spotmu source item to render
 * @returns The preview id and any block reason
 */
/**
 * Render one frame from the form payload. Does not save a theme.
 *
 * @param themePreviewRequest - Source, frame, and elements as they stand
 * @returns The PNG and any block reason
 */
/**
 * Draw the source theme with this unit's text and saved image.
 *
 * The PNG is inline. No unit, artifact, or preview file is written.
 *
 * @param sourceId - Source UUID
 * @param previewRequest - Unsaved text and an optional saved unit id
 * @returns The frame and any block reason
 */
export async function previewSourceUnit(
  sourceId: string,
  previewRequest: UnitPreviewRequest,
): Promise<ThemePreviewResponse> {

  return requestJson<ThemePreviewResponse>(
    "POST",
    `/api/v1/sources/${sourceId}/units/preview`,
    previewRequest,
  );
}

export async function createThemePreview(
  themePreviewRequest: ThemePreviewRequest,
): Promise<ThemePreviewResponse> {

  return requestJson<ThemePreviewResponse>(
    "POST",
    "/api/v1/themes/preview",
    themePreviewRequest,
  );
}

export async function createThemeSample(
  themeId: string,
  themeSampleRequest: ThemeSampleRequest,
): Promise<ThemeSampleResponse> {

  return requestJson<ThemeSampleResponse>(
    "POST",
    `/api/v1/themes/${themeId}/samples`,
    themeSampleRequest,
  );
}

/**
 * Load one preview PNG. The session cookie is required.
 *
 * @param themeId - Theme UUID
 * @param previewId - Preview UUID from the samples response
 * @returns PNG bytes
 */
export async function fetchThemeSampleImageBlob(
  themeId: string,
  previewId: string,
): Promise<Blob> {

  const requestPath: string = `/api/v1/themes/${themeId}/samples/${previewId}/image`;
  const response: Response = await sendApiRequest("GET", requestPath);

  await throwIfResponseFailed(response, requestPath);

  const imageBlob: Blob = await response.blob();

  return imageBlob;
}

export async function createThemeElement(
  themeId: string,
  themeElementCreateRequest: ThemeElementCreateRequest,
): Promise<ThemeElementReadResponse> {

  return requestJson<ThemeElementReadResponse>(
    "POST",
    `/api/v1/themes/${themeId}/elements`,
    themeElementCreateRequest,
  );
}

export async function patchThemeElement(
  themeId: string,
  elementId: string,
  themeElementPatchRequest: ThemeElementPatchRequest,
): Promise<ThemeElementReadResponse> {

  return requestJson<ThemeElementReadResponse>(
    "PATCH",
    `/api/v1/themes/${themeId}/elements/${elementId}`,
    themeElementPatchRequest,
  );
}

export async function deleteThemeElement(
  themeId: string,
  elementId: string,
): Promise<void> {

  await requestJson<undefined>(
    "DELETE",
    `/api/v1/themes/${themeId}/elements/${elementId}`,
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
