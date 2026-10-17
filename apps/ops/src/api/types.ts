export type ArtifactStatus = "draft" | "approved" | "rejected";

export type PostJobStatus =
  | "scheduled"
  | "publishing"
  | "published"
  | "failed"
  | "measured";

export type Platform = "instagram" | "tiktok";

export type AccountStatus = "active" | "paused" | "disabled";

export type SourceType = "spotmu_interest" | "brand_product" | "editorial_brief";

export type CampaignType = "spotmu" | "spotmu_test" | "other";

export type AdvertisementType = "carousel";

export type CampaignStatus = "ready" | "running" | "paused" | "finished";

export type SteerActionName = "kill" | "pause" | "double_down" | "resume";

export interface BrandReadResponse {
  id: string;
  slug: string;
  name: string;
  notes: string | null;
  voice_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceItemCreateRequest {
  brand_id: string;
  title: string;
  source_type?: SourceType;
  external_key?: string | null;
  interest_heading?: string | null;
  overview_bullets?: string[];
  canonical_url?: string | null;
}

export interface SourceItemReadResponse {
  id: string;
  brand_id: string;
  source_type: SourceType;
  external_key: string | null;
  title: string;
  interest_heading: string | null;
  overview_bullets: string[];
  canonical_url: string | null;
  brand_kit_refs: Record<string, unknown> | unknown[] | null;
  raw_payload: Record<string, unknown> | unknown[] | null;
  created_at: string;
  updated_at: string;
}

export interface ClusterCreateRequest {
  brand_id: string;
  slug: string;
  name: string;
  description?: string | null;
  is_active?: boolean;
}

export interface ClusterReadResponse {
  id: string;
  brand_id: string;
  slug: string;
  name: string;
  description: string | null;
  is_active: boolean;
  source_item_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface AccountCreateRequest {
  cluster_id: string;
  platform: Platform;
  handle: string;
  external_account_id?: string | null;
  status?: AccountStatus;
  cadence_cap_per_day?: number | null;
}

export interface AccountReadResponse {
  id: string;
  cluster_id: string;
  platform: Platform;
  handle: string;
  external_account_id: string | null;
  status: AccountStatus;
  cadence_cap_per_day: number | null;
  created_at: string;
  updated_at: string;
}

export interface ArtifactSlide {
  role: string;
  text: string;
  asset_ref?: string | null;
}

export interface ArtifactReadResponse {
  id: string;
  brand_id: string;
  source_item_id: string | null;
  cluster_id: string | null;
  status: ArtifactStatus;
  format: string;
  caption: string | null;
  cta_url: string | null;
  slides: ArtifactSlide[] | unknown[] | null;
  template_id?: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CarouselGenerateRequest {
  source_item_id: string;
  cluster_id?: string | null;
  template_id?: string | null;
}

export interface CarouselTemplateReadResponse {
  template_id: string;
  name: string;
  description: string;
  is_default: boolean;
}

export interface ArtifactRegenerateRequest {
  template_id?: string | null;
}

export interface ArtifactApproveRequest {
  caption?: string | null;
}

export interface ArtifactPatchRequest {
  caption?: string | null;
  cta_url?: string | null;
}

export interface SchedulePostJobRequest {
  artifact_id: string;
  account_id: string;
  scheduled_for: string;
}

export interface PostJobReadResponse {
  id: string;
  artifact_id: string;
  account_id: string;
  status: PostJobStatus;
  scheduled_for: string | null;
  published_at: string | null;
  platform_post_id: string | null;
  platform_post_url: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MetricSnapshotReadResponse {
  id: string;
  post_job_id: string;
  captured_at: string;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  raw: Record<string, unknown> | unknown[] | null;
}

export interface ClusterMetricsSummaryResponse {
  cluster_id: string;
  post_job_count: number;
  snapshot_job_count: number;
  views_job_count: number;
  median_views: number | null;
}

export interface ClusterSteerRequest {
  action: SteerActionName;
  reason?: string | null;
  created_by?: string | null;
}

export interface SteerActionReadResponse {
  id: string;
  cluster_id: string;
  action: SteerActionName;
  reason: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AgentSummaryArtifact {
  id: string;
  status: ArtifactStatus;
  caption: string | null;
  created_at: string;
}

export interface AgentSummaryPostJob {
  id: string;
  status: PostJobStatus;
  platform_post_id: string | null;
  published_at: string | null;
  latest_views: number | null;
  latest_captured_at: string | null;
}

export interface ClusterAgentSummaryResponse {
  cluster_id: string;
  slug: string;
  name: string;
  is_active: boolean;
  metrics: ClusterMetricsSummaryResponse;
  recent_artifacts: AgentSummaryArtifact[];
  recent_post_jobs: AgentSummaryPostJob[];
  recent_steer_actions: SteerActionReadResponse[];
}

export interface HealthReadResponse {
  status: string;
}

export interface CampaignInterestWrite {
  slug: string;
  title?: string | null;
  spotmu_interest_id?: string | null;
}

export interface CampaignCreateRequest {
  name: string;
  campaign_type: CampaignType;
  advertisement_type?: AdvertisementType;
  skeleton_id: string;
  carousel_id: string;
  platforms: Platform[];
  account_ids: string[];
  interests: CampaignInterestWrite[];
}

export interface CampaignCarouselSlideRead {
  slide_id: string;
  name: string;
  position: number;
}

export interface CampaignCarouselRead {
  id: string;
  position: number;
  slides: CampaignCarouselSlideRead[];
}

export interface CampaignInterestReadResponse {
  slug: string;
  title: string | null;
  spotmu_interest_id: string | null;
}

export interface CampaignAccountReadResponse {
  id: string;
  platform: Platform;
  handle: string;
}

export interface CampaignReadResponse {
  id: string;
  name: string;
  slug: string;
  hashtag: string;
  campaign_type: CampaignType;
  advertisement_type: AdvertisementType;
  status: CampaignStatus;
  platforms: Platform[];
  skeleton_id: string | null;
  carousel_id: string | null;
  skeleton_name: string | null;
  carousel_name: string | null;
  account_count: number;
  interest_count: number;
  accounts: CampaignAccountReadResponse[];
  interests: CampaignInterestReadResponse[];
  carousels: CampaignCarouselRead[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export type SkeletonStatus = "draft" | "live";

export type BackgroundKind = "picture" | "color" | "gradient";

export interface SkeletonGradientStop {
  offset: number;
  color: string;
}

export interface SkeletonGradient {
  angle_deg: number;
  stops: SkeletonGradientStop[];
}

export interface SkeletonCreateRequest {
  name: string;
  advertisement_type?: AdvertisementType;
  template_key?: string | null;
  status?: SkeletonStatus;
  page_margin?: number;
  element_gap?: number;
  element_margin?: number;
  background_kind?: BackgroundKind;
  background_color?: string | null;
  background_gradient?: SkeletonGradient | null;
  background_asset_ref?: string | null;
  elements?: SkeletonElementCreateRequest[];
}

export interface SkeletonPatchRequest {
  status?: SkeletonStatus | null;
  page_margin?: number | null;
  element_gap?: number | null;
  element_margin?: number | null;
  background_kind?: BackgroundKind | null;
  background_color?: string | null;
  background_gradient?: SkeletonGradient | null;
  background_asset_ref?: string | null;
}

export type SkeletonElementBand = "top" | "middle" | "bottom";

export type SkeletonElementContentKind = "text" | "image";

export type SkeletonElementTextSource =
  | "title"
  | "interest_heading"
  | "overview_bullets"
  | "canonical_url";

export type SkeletonElementAlignment = "left" | "center" | "right";

export interface SkeletonElementCreateRequest {
  name: string;
  band: SkeletonElementBand;
  content_kind: SkeletonElementContentKind;
  sort_order?: number | null;
  rectangle_color?: string | null;
  rectangle_opacity?: number | null;
  rectangle_radius?: number | null;
  text_source?: SkeletonElementTextSource | null;
  font_family?: string | null;
  font_size?: number | null;
  font_color?: string | null;
  bold?: boolean | null;
  italic?: boolean | null;
  underline?: boolean | null;
  strikethrough?: boolean | null;
  font_weight?: number | null;
  alignment?: SkeletonElementAlignment | null;
  image_asset_ref?: string | null;
}

export interface SkeletonElementPatchRequest {
  name?: string | null;
  band?: SkeletonElementBand | null;
  content_kind?: SkeletonElementContentKind | null;
  sort_order?: number | null;
  rectangle_color?: string | null;
  rectangle_opacity?: number | null;
  rectangle_radius?: number | null;
  text_source?: SkeletonElementTextSource | null;
  font_family?: string | null;
  font_size?: number | null;
  font_color?: string | null;
  bold?: boolean | null;
  italic?: boolean | null;
  underline?: boolean | null;
  strikethrough?: boolean | null;
  font_weight?: number | null;
  alignment?: SkeletonElementAlignment | null;
  image_asset_ref?: string | null;
}

export interface SkeletonElementReadResponse {
  id: string;
  skeleton_id: string;
  band: SkeletonElementBand;
  sort_order: number;
  content_kind: SkeletonElementContentKind;
  name: string;
  rectangle_color: string | null;
  rectangle_opacity: number;
  rectangle_radius: number;
  text_source: SkeletonElementTextSource | null;
  font_family: string | null;
  font_size: number | null;
  font_color: string | null;
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strikethrough: boolean;
  font_weight: number | null;
  alignment: SkeletonElementAlignment | null;
  image_asset_ref: string | null;
  created_at: string;
  updated_at: string;
}

export type SkeletonSampleBlockReason = "overlap" | "missing_asset" | "measure_error";

export interface SkeletonSampleRequest {
  source_item_id: string;
}

export interface SkeletonSampleOverlap {
  band_a: SkeletonElementBand;
  band_b: SkeletonElementBand;
  element_ids: string[];
}

export interface SkeletonSampleResponse {
  preview_id: string;
  blocked: boolean;
  block_reason: SkeletonSampleBlockReason | null;
  detail: string | null;
  overlaps: SkeletonSampleOverlap[];
}

export interface SkeletonPreviewElementRequest extends SkeletonElementCreateRequest {
  preview_text?: string | null;
}

export interface SkeletonPreviewRequest {
  status?: SkeletonStatus;
  page_margin?: number;
  element_gap?: number;
  element_margin?: number;
  background_kind?: BackgroundKind;
  background_color?: string | null;
  background_gradient?: SkeletonGradient | null;
  background_asset_ref?: string | null;
  elements?: SkeletonPreviewElementRequest[];
}

export interface SkeletonPreviewResponse {
  blocked: boolean;
  block_reason: SkeletonSampleBlockReason | null;
  detail: string | null;
  overlaps: SkeletonSampleOverlap[];
  image_png_base64: string;
}

export interface SkeletonImageAlbumResponse {
  album_id: string;
  name: string;
  asset_refs: string[];
}

export interface SkeletonDefaultImagesResponse {
  albums: SkeletonImageAlbumResponse[];
}

export interface SkeletonFontFamilyResponse {
  family_id: string;
  name: string;
  category: string;
}

export interface SkeletonFontFamiliesResponse {
  families: SkeletonFontFamilyResponse[];
  fallback_name: string;
}

export interface SkeletonReadResponse {
  id: string;
  name: string;
  slug: string;
  advertisement_type: AdvertisementType;
  template_key: string | null;
  status: SkeletonStatus;
  page_margin: number;
  element_gap: number;
  element_margin: number;
  background_kind: BackgroundKind;
  background_color: string | null;
  background_gradient: SkeletonGradient | null;
  background_asset_ref: string | null;
  elements: SkeletonElementReadResponse[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export interface SpotmuInterestSearchHit {
  slug: string;
  title: string;
  spotmu_interest_id: string | null;
  interest_heading: string | null;
}

export type OpsUserRole = "admin" | "reader";

export interface OpsLoginRequest {
  username: string;
  password: string;
}

export interface OpsUserReadResponse {
  id: string;
  username: string;
  role: OpsUserRole;
  created_at: string;
  updated_at: string;
}

export interface OpsChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface OpsChangePasswordResponse {
  status: string;
}

export interface OpsUserCreateRequest {
  username: string;
  password: string;
  role: OpsUserRole;
}

export interface OpsUserRolePatchRequest {
  role: OpsUserRole;
}

export interface OpsUserResetPasswordRequest {
  new_password: string;
}

export type SlideImageLicense = "cc0" | "public_domain" | "owned" | "licensed";

export type SlideImageMediaType = "svg" | "png" | "jpeg";

export type SlideImageIntake = "upload" | "url";

export interface SlideElementTextReadResponse {
  skeleton_element_id: string;
  value: string;
}

export interface SlideImageReadResponse {
  id: string;
  position: number;
  relative_path: string;
  media_type: SlideImageMediaType;
  byte_size: number;
  width: number | null;
  height: number | null;
  alt_text: string | null;
  license: SlideImageLicense;
  source: string;
  license_note: string;
  intake: SlideImageIntake;
  thumbnail_path: string | null;
}

export type SlideTextStatus = "live" | "draft";

export interface SlideReadResponse {
  id: string;
  position: number;
  name: string;
  text_status: SlideTextStatus;
  texts: SlideElementTextReadResponse[];
  draft_texts: SlideElementTextReadResponse[];
  excluded_slide_ids: string[];
  images: SlideImageReadResponse[];
}

export type CarouselStepState = "locked" | "available" | "done";

export interface CarouselResearchReadResponse {
  id: string;
  title: string;
  slug: string;
  position: number;
}

export interface CarouselStepsResponse {
  basic: CarouselStepState;
  instructions: CarouselStepState;
  content: CarouselStepState;
  slides: CarouselStepState;
  final: CarouselStepState;
}

export interface CarouselListItemResponse {
  id: string;
  skeleton_id: string;
  album_id: string | null;
  name: string;
  slug: string;
  generation_number: number;
  editor_step: number;
  slide_count: number;
  created_at: string;
  updated_at: string;
}

export interface CarouselReadResponse {
  id: string;
  skeleton_id: string;
  album_id: string | null;
  name: string;
  slug: string;
  generation_number: number;
  editor_step: number;
  inspiration: string;
  rules: string;
  live_slide_count: number;
  created_at: string;
  updated_at: string;
  research: CarouselResearchReadResponse[];
  steps: CarouselStepsResponse;
  slides: SlideReadResponse[];
}

export interface AlbumImageReadResponse {
  id: string;
  position: number;
  relative_path: string;
  media_type: SlideImageMediaType;
  byte_size: number;
  width: number | null;
  height: number | null;
  alt_text: string | null;
  license: SlideImageLicense;
  source: string;
  license_note: string;
  intake: SlideImageIntake;
  thumbnail_path: string | null;
}

export interface AlbumListItemResponse {
  id: string;
  name: string;
  slug: string;
  image_count: number;
  created_at: string;
  updated_at: string;
}

export interface AlbumReadResponse {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
  images: AlbumImageReadResponse[];
}

export interface AlbumCreateRequest {
  name: string;
}

export interface AlbumImageWrite {
  id: string;
  alt_text: string | null;
  license: SlideImageLicense;
  source: string;
  license_note: string;
}

export interface AlbumPatchRequest {
  name: string;
  images: AlbumImageWrite[];
}

export interface ResearchListItemResponse {
  id: string;
  title: string;
  slug: string;
  word_count: number;
  character_count: number;
  created_at: string;
  updated_at: string;
}

export interface ResearchReadResponse {
  id: string;
  title: string;
  slug: string;
  body: string;
  word_count: number;
  character_count: number;
  created_at: string;
  updated_at: string;
}

export interface ResearchCreateRequest {
  title: string;
}

export interface ResearchPatchRequest {
  title: string;
  body: string;
}

export interface CarouselGuidancePatchRequest {
  inspiration: string;
  rules: string;
}

export interface TextGenerationStatusResponse {
  available: boolean;
  detail: string;
}

export interface SlideAcceptTextRequest {
  texts: SlideElementTextWrite[];
}

export interface CarouselCreateRequest {
  name: string;
  skeleton_id: string;
}

export interface CarouselPatchRequest {
  name: string;
}

export interface SlideElementTextWrite {
  skeleton_element_id: string;
  value: string;
}

export interface SlideWriteRequest {
  name: string;
  texts: SlideElementTextWrite[];
  excluded_slide_ids: string[];
}

export interface SlidePreviewRequest {
  texts: SlideElementTextWrite[];
  slide_id: string | null;
}

export interface SlideImageMetadataPatch {
  alt_text: string | null;
  license: SlideImageLicense;
  source: string;
  license_note: string;
}

export interface SlideImageImportRequest {
  url: string;
  alt_text: string | null;
  license: SlideImageLicense;
  source: string;
  license_note: string;
}

export interface SlideImageCreatePayload {
  kind: "file" | "url";
  file: File | null;
  url: string | null;
  license: SlideImageLicense;
  source: string;
  license_note: string;
}
