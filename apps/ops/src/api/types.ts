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
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CarouselGenerateRequest {
  source_item_id: string;
  cluster_id?: string | null;
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

export interface OpsLoginRequest {
  username: string;
  password: string;
}

export interface OpsUserReadResponse {
  id: string;
  username: string;
  created_at: string;
  updated_at: string;
}
