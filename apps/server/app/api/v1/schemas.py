"""Pydantic create/read schemas for the Phase 1 persist-proof API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AccountStatus,
    ArtifactStatus,
    Platform,
    PostJobStatus,
    SourceType,
    SteerActionType,
)


class BrandCreateRequest(BaseModel):
    """Body for `POST /api/v1/brands`."""

    slug: str
    name: str
    notes: str | None = None
    voice_notes: str | None = None


class BrandReadResponse(BaseModel):
    """Serialized Brand row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    notes: str | None
    voice_notes: str | None
    created_at: datetime
    updated_at: datetime


class SourceItemCreateRequest(BaseModel):
    """Body for `POST /api/v1/source-items`."""

    brand_id: uuid.UUID
    title: str
    source_type: SourceType = SourceType.SPOTMU_INTEREST
    external_key: str | None = None
    interest_heading: str | None = None
    overview_bullets: list[str] = Field(default_factory=list)
    canonical_url: str | None = None
    brand_kit_refs: dict[str, object] | list[object] | None = None
    raw_payload: dict[str, object] | list[object] | None = None


class SourceItemReadResponse(BaseModel):
    """Serialized SourceItem row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    source_type: SourceType
    external_key: str | None
    title: str
    interest_heading: str | None
    overview_bullets: list[str]
    canonical_url: str | None
    brand_kit_refs: dict[str, object] | list[object] | None
    raw_payload: dict[str, object] | list[object] | None
    created_at: datetime
    updated_at: datetime


class ClusterCreateRequest(BaseModel):
    """Body for `POST /api/v1/clusters`."""

    brand_id: uuid.UUID
    slug: str
    name: str
    description: str | None = None
    is_active: bool = True


class ClusterReadResponse(BaseModel):
    """Serialized Cluster row, including linked source item ids (1.3e)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    slug: str
    name: str
    description: str | None
    is_active: bool
    source_item_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SpotmuSyncRequest(BaseModel):
    """Body for `POST /api/v1/ingest/spotmu/sync`."""

    slugs: list[str] | None = None
    limit: int = Field(default=20, ge=1, le=200)


class SpotmuIngestSlugError(BaseModel):
    """One failed slug from a sync run."""

    slug: str
    error: str


class SpotmuSyncResponse(BaseModel):
    """Counts and per-slug errors from an on-demand Spotmu sync."""

    created_count: int
    updated_count: int
    failed_count: int
    errors: list[SpotmuIngestSlugError]


class AccountCreateRequest(BaseModel):
    """Body for `POST /api/v1/accounts`. No OAuth token fields."""

    cluster_id: uuid.UUID
    platform: Platform
    handle: str
    external_account_id: str | None = None
    status: AccountStatus = AccountStatus.ACTIVE
    cadence_cap_per_day: int | None = None


class AccountReadResponse(BaseModel):
    """Serialized Account row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cluster_id: uuid.UUID
    platform: Platform
    handle: str
    external_account_id: str | None
    status: AccountStatus
    cadence_cap_per_day: int | None
    created_at: datetime
    updated_at: datetime


class ArtifactSlideSchema(BaseModel):
    """One ordered slide. `asset_ref` is relative to `ARTIFACT_STORAGE_DIR`."""

    role: str
    text: str
    asset_ref: str | None = None


class CarouselGenerateRequest(BaseModel):
    """Body for `POST /api/v1/generate/carousel`."""

    source_item_id: uuid.UUID
    cluster_id: uuid.UUID | None = None


class ArtifactCreateRequest(BaseModel):
    """Body for `POST /api/v1/artifacts`."""

    brand_id: uuid.UUID
    status: ArtifactStatus = ArtifactStatus.DRAFT
    source_item_id: uuid.UUID | None = None
    cluster_id: uuid.UUID | None = None
    format: str = "carousel"
    caption: str | None = None
    cta_url: str | None = None
    slides: list[ArtifactSlideSchema] | None = None
    approved_at: datetime | None = None


class ArtifactReadResponse(BaseModel):
    """Serialized Artifact row, including status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    source_item_id: uuid.UUID | None
    cluster_id: uuid.UUID | None
    status: ArtifactStatus
    format: str
    caption: str | None
    cta_url: str | None
    slides: list[object] | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ArtifactApproveRequest(BaseModel):
    """Optional body for `POST /api/v1/artifacts/{id}/approve`."""

    caption: str | None = None


class ArtifactRejectRequest(BaseModel):
    """Optional body for `POST /api/v1/artifacts/{id}/reject`.

    `reason` is accepted and ignored in MVP (no reject-reason column).
    """

    reason: str | None = None


class ArtifactPatchRequest(BaseModel):
    """Body for `PATCH /api/v1/artifacts/{id}` (caption / cta_url)."""

    caption: str | None = None
    cta_url: str | None = None


class SchedulePostJobRequest(BaseModel):
    """Body for `POST /api/v1/schedule`."""

    artifact_id: uuid.UUID
    account_id: uuid.UUID
    scheduled_for: datetime


class PostJobCreateRequest(BaseModel):
    """Body for `POST /api/v1/post-jobs`."""

    artifact_id: uuid.UUID
    account_id: uuid.UUID
    status: PostJobStatus = PostJobStatus.SCHEDULED
    scheduled_for: datetime | None = None
    published_at: datetime | None = None
    platform_post_id: str | None = None
    platform_post_url: str | None = None
    last_error: str | None = None


class PostJobReadResponse(BaseModel):
    """Serialized PostJob row, including status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    artifact_id: uuid.UUID
    account_id: uuid.UUID
    status: PostJobStatus
    scheduled_for: datetime | None
    published_at: datetime | None
    platform_post_id: str | None
    platform_post_url: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class MetricSnapshotCreateRequest(BaseModel):
    """Optional body for creating a MetricSnapshot (legacy persist shape)."""

    post_job_id: uuid.UUID
    captured_at: datetime
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    raw: dict[str, object] | list[object] | None = None


class PostJobMetricsCreateRequest(BaseModel):
    """Body for `POST /api/v1/post-jobs/{id}/metrics` (1.7a-i).

    `post_job_id` is the path parameter. `captured_at` defaults to UTC now
    in the service when omitted.
    """

    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    captured_at: datetime | None = None
    raw: dict[str, object] | list[object] | None = None


class MetricSnapshotReadResponse(BaseModel):
    """Serialized MetricSnapshot row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_job_id: uuid.UUID
    captured_at: datetime
    views: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    raw: dict[str, object] | list[object] | None


class ClusterMetricsSummaryResponse(BaseModel):
    """`GET /api/v1/clusters/{id}/metrics/summary` (1.7b).

    `median_views` is null when no post jobs have a latest snapshot with
    non-null `views` (empty cluster, jobs without snapshots, or views
    all null). It is not coerced to zero.
    """

    cluster_id: uuid.UUID
    post_job_count: int
    snapshot_job_count: int
    views_job_count: int
    median_views: float | None


class ClusterSteerRequest(BaseModel):
    """Body for `POST /api/v1/clusters/{id}/steer` (1.7c)."""

    action: SteerActionType
    reason: str | None = None
    created_by: str | None = "human"


class SteerActionReadResponse(BaseModel):
    """Serialized SteerAction row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cluster_id: uuid.UUID
    action: SteerActionType
    reason: str | None
    created_by: str | None
    created_at: datetime


class AgentSummaryArtifact(BaseModel):
    """Slim artifact line for the agent summary."""

    id: uuid.UUID
    status: ArtifactStatus
    caption: str | None
    created_at: datetime


class AgentSummaryPostJob(BaseModel):
    """Slim post-job line plus latest-wins views when present."""

    id: uuid.UUID
    status: PostJobStatus
    platform_post_id: str | None
    published_at: datetime | None
    latest_views: int | None
    latest_captured_at: datetime | None


class ClusterAgentSummaryResponse(BaseModel):
    """`GET /api/v1/clusters/{id}/agent-summary` JSON (1.7d)."""

    cluster_id: uuid.UUID
    slug: str
    name: str
    is_active: bool
    metrics: ClusterMetricsSummaryResponse
    recent_artifacts: list[AgentSummaryArtifact]
    recent_post_jobs: list[AgentSummaryPostJob]
    recent_steer_actions: list[SteerActionReadResponse]


class OpsLoginRequest(BaseModel):
    """Body for `POST /api/v1/auth/login`."""

    username: str
    password: str


class OpsUserReadResponse(BaseModel):
    """Serialized ops operator. Never includes `password_hash`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    created_at: datetime
    updated_at: datetime


class OpsLogoutResponse(BaseModel):
    """Body for `POST /api/v1/auth/logout`."""

    status: str
