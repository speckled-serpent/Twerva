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
  platforms: Platform[];
  account_ids: string[];
  interests: CampaignInterestWrite[];
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
  account_count: number;
  interest_count: number;
  accounts: CampaignAccountReadResponse[];
  interests: CampaignInterestReadResponse[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export type ThemeStatus = "draft" | "live";

export type BackgroundKind = "picture" | "color" | "gradient";

export interface ThemeGradientStop {
  offset: number;
  color: string;
}

export interface ThemeGradient {
  angle_deg: number;
  stops: ThemeGradientStop[];
}

export interface ThemeCreateRequest {
  name: string;
  advertisement_type?: AdvertisementType;
  template_key?: string | null;
  status?: ThemeStatus;
  page_margin?: number;
  element_gap?: number;
  element_margin?: number;
  background_kind?: BackgroundKind;
  background_color?: string | null;
  background_gradient?: ThemeGradient | null;
  background_asset_ref?: string | null;
  elements?: ThemeElementCreateRequest[];
}

export interface ThemePatchRequest {
  status?: ThemeStatus | null;
  page_margin?: number | null;
  element_gap?: number | null;
  element_margin?: number | null;
  background_kind?: BackgroundKind | null;
  background_color?: string | null;
  background_gradient?: ThemeGradient | null;
  background_asset_ref?: string | null;
}

export type ThemeElementBand = "top" | "middle" | "bottom";

export type ThemeElementContentKind = "text" | "image";

export type ThemeElementTextSource =
  | "title"
  | "interest_heading"
  | "overview_bullets"
  | "canonical_url";

export type ThemeElementAlignment = "left" | "center" | "right";

export interface ThemeElementCreateRequest {
  band: ThemeElementBand;
  content_kind: ThemeElementContentKind;
  sort_order?: number | null;
  rectangle_color?: string | null;
  rectangle_opacity?: number | null;
  rectangle_radius?: number | null;
  text_source?: ThemeElementTextSource | null;
  font_family?: string | null;
  font_size?: number | null;
  font_color?: string | null;
  bold?: boolean | null;
  italic?: boolean | null;
  underline?: boolean | null;
  strikethrough?: boolean | null;
  font_weight?: number | null;
  alignment?: ThemeElementAlignment | null;
  image_asset_ref?: string | null;
}

export interface ThemeElementPatchRequest {
  band?: ThemeElementBand | null;
  content_kind?: ThemeElementContentKind | null;
  sort_order?: number | null;
  rectangle_color?: string | null;
  rectangle_opacity?: number | null;
  rectangle_radius?: number | null;
  text_source?: ThemeElementTextSource | null;
  font_family?: string | null;
  font_size?: number | null;
  font_color?: string | null;
  bold?: boolean | null;
  italic?: boolean | null;
  underline?: boolean | null;
  strikethrough?: boolean | null;
  font_weight?: number | null;
  alignment?: ThemeElementAlignment | null;
  image_asset_ref?: string | null;
}

export interface ThemeElementReadResponse {
  id: string;
  theme_id: string;
  band: ThemeElementBand;
  sort_order: number;
  content_kind: ThemeElementContentKind;
  rectangle_color: string | null;
  rectangle_opacity: number;
  rectangle_radius: number;
  text_source: ThemeElementTextSource | null;
  font_family: string | null;
  font_size: number | null;
  font_color: string | null;
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strikethrough: boolean;
  font_weight: number | null;
  alignment: ThemeElementAlignment | null;
  image_asset_ref: string | null;
  created_at: string;
  updated_at: string;
}

export type ThemeSampleBlockReason = "overlap" | "missing_asset" | "measure_error";

export interface ThemeSampleRequest {
  source_item_id: string;
}

export interface ThemeSampleOverlap {
  band_a: ThemeElementBand;
  band_b: ThemeElementBand;
  element_ids: string[];
}

export interface ThemeSampleResponse {
  preview_id: string;
  blocked: boolean;
  block_reason: ThemeSampleBlockReason | null;
  detail: string | null;
  overlaps: ThemeSampleOverlap[];
}

export interface ThemePreviewRequest {
  source_item_id: string;
  status?: ThemeStatus;
  page_margin?: number;
  element_gap?: number;
  element_margin?: number;
  background_kind?: BackgroundKind;
  background_color?: string | null;
  background_gradient?: ThemeGradient | null;
  background_asset_ref?: string | null;
  elements?: ThemeElementCreateRequest[];
}

export interface ThemePreviewResponse {
  blocked: boolean;
  block_reason: ThemeSampleBlockReason | null;
  detail: string | null;
  overlaps: ThemeSampleOverlap[];
  image_png_base64: string;
}

export interface ThemeImageAlbumResponse {
  album_id: string;
  name: string;
  asset_refs: string[];
}

export interface ThemeDefaultImagesResponse {
  albums: ThemeImageAlbumResponse[];
}

export interface ThemeFontFamilyResponse {
  family_id: string;
  name: string;
  category: string;
}

export interface ThemeFontFamiliesResponse {
  families: ThemeFontFamilyResponse[];
  fallback_name: string;
}

export interface ThemeReadResponse {
  id: string;
  name: string;
  slug: string;
  advertisement_type: AdvertisementType;
  template_key: string | null;
  status: ThemeStatus;
  page_margin: number;
  element_gap: number;
  element_margin: number;
  background_kind: BackgroundKind;
  background_color: string | null;
  background_gradient: ThemeGradient | null;
  background_asset_ref: string | null;
  elements: ThemeElementReadResponse[];
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

export type ContentSourceKind = "album" | "resource";

export type UnitImageLicense = "cc0" | "public_domain" | "owned" | "licensed";

export type UnitImageMediaType = "svg" | "png" | "jpeg";

export type UnitImageIntake = "upload" | "url";

export interface UnitFieldReadResponse {
  id: string;
  position: number;
  label: string;
  value: string;
}

export interface UnitImageReadResponse {
  id: string;
  position: number;
  relative_path: string;
  media_type: UnitImageMediaType;
  byte_size: number;
  width: number | null;
  height: number | null;
  alt_text: string | null;
  license: UnitImageLicense;
  source: string;
  license_note: string;
  intake: UnitImageIntake;
  thumbnail_path: string | null;
}

export interface UnitReadResponse {
  id: string;
  position: number;
  free_text: string | null;
  tags: string[];
  fields: UnitFieldReadResponse[];
  images: UnitImageReadResponse[];
}

export interface SourceListItemResponse {
  id: string;
  kind: ContentSourceKind;
  name: string;
  slug: string;
  unit_count: number;
  created_at: string;
  updated_at: string;
}

export interface SourceReadResponse {
  id: string;
  kind: ContentSourceKind;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
  units: UnitReadResponse[];
}

export interface SourceCreateRequest {
  name: string;
  kind: ContentSourceKind;
}

export interface SourcePatchRequest {
  name: string;
}

export interface UnitFieldWrite {
  label: string;
  value: string;
}

export interface UnitWriteRequest {
  free_text: string | null;
  tags: string[];
  fields: UnitFieldWrite[];
}

export interface UnitImageMetadataPatch {
  alt_text: string | null;
  license: UnitImageLicense;
  source: string;
  license_note: string;
}
