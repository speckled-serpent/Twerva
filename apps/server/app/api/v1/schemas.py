"""Pydantic create/read schemas for the Phase 1 persist-proof API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AccountStatus,
    AdvertisementType,
    ArtifactStatus,
    BackgroundKind,
    CampaignStatus,
    CampaignType,
    OpsUserRole,
    Platform,
    PostJobStatus,
    SourceType,
    SteerActionType,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
    SkeletonStatus,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
    SlideTextStatus,
)
from app.carousels.slide_skeleton import CarouselStepState
from app.models.skeleton import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ELEMENT_GAP,
    DEFAULT_ELEMENT_MARGIN,
    DEFAULT_PAGE_MARGIN,
)


class CampaignInterestWrite(BaseModel):
    """One Spotmu interest attached on campaign create (no ingest)."""

    slug: str
    title: str | None = None
    spotmu_interest_id: str | None = None


class CampaignCreateRequest(BaseModel):
    """Body for `POST /api/v1/campaigns`.

    Slug and hashtag are generated from ``name``. Status is always
    ``ready``. ``other`` campaign types are rejected by the handler.
    Spotmu and Spotmu-test require a non-empty name plus at least one
    platform and interest after the handler strips and dedupes. Spotmu
    also requires at least one account; Spotmu-test may send an empty
    ``account_ids`` list. Empty lists stay allowed on the model so
    ``other`` still parses. ``skeleton_id`` and ``carousel_id`` are required.
    The carousel has to be bound to that skeleton.
    """

    name: str = Field(min_length=1)
    campaign_type: CampaignType
    advertisement_type: AdvertisementType = AdvertisementType.CAROUSEL
    skeleton_id: uuid.UUID
    carousel_id: uuid.UUID
    platforms: list[Platform] = Field(default_factory=list)
    account_ids: list[uuid.UUID] = Field(default_factory=list)
    interests: list[CampaignInterestWrite] = Field(default_factory=list)


class CampaignInterestReadResponse(BaseModel):
    """Serialized campaign interest snapshot."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str | None
    spotmu_interest_id: str | None


class CampaignAccountReadResponse(BaseModel):
    """Serialized campaign account handle (publish later)."""

    id: uuid.UUID
    platform: Platform
    handle: str


class CampaignCarouselSlideRead(BaseModel):
    """One live slide placed on a carousel frame."""

    slide_id: uuid.UUID
    name: str
    position: int


class CampaignCarouselRead(BaseModel):
    """One carousel from the latest run, in skeleton frame order."""

    id: uuid.UUID
    position: int
    slides: list[CampaignCarouselSlideRead] = Field(default_factory=list)


class CampaignReadResponse(BaseModel):
    """Serialized Campaign plus join counts and snapshots."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    hashtag: str
    campaign_type: CampaignType
    advertisement_type: AdvertisementType
    status: CampaignStatus
    platforms: list[Platform]
    skeleton_id: uuid.UUID | None = None
    carousel_id: uuid.UUID | None = None
    skeleton_name: str | None = None
    carousel_name: str | None = None
    account_count: int
    interest_count: int
    accounts: list[CampaignAccountReadResponse] = Field(default_factory=list)
    interests: list[CampaignInterestReadResponse] = Field(default_factory=list)
    carousels: list[CampaignCarouselRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None


class SkeletonCreateRequest(BaseModel):
    """Body for `POST /api/v1/skeletons`.

    Slug is generated from ``name``. ``advertisement_type`` defaults to
    carousel (the only implemented format). ``template_key`` is optional
    and, when set, must name an existing carousel generator. Omitted
    frame fields use the defaults: ``status`` ``draft``, spacing 96 / 0 /
    0, kind ``color``, color ``#F6F1E8``, and null gradient and asset
    ref. Present frame fields are stored, and a Live row must have the
    payload for its kind. ``elements`` are created in the same write.
    An omitted or empty list stores zero elements. A validation error
    stores nothing.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    advertisement_type: AdvertisementType = AdvertisementType.CAROUSEL
    template_key: str | None = None
    status: SkeletonStatus | None = None
    page_margin: int | None = None
    element_gap: int | None = None
    element_margin: int | None = None
    background_kind: BackgroundKind | None = None
    background_color: str | None = None
    background_gradient: dict[str, object] | None = None
    background_asset_ref: str | None = None
    elements: list["SkeletonElementCreateRequest"] = Field(default_factory=list)


class SkeletonGradientStop(BaseModel):
    """One stop in ``skeletons.background_gradient``.

    ``offset`` is 0 through 1. ``color`` is ``#`` plus six hex digits.
    """

    offset: float
    color: str


class SkeletonGradient(BaseModel):
    """Locked shape for ``skeletons.background_gradient``.

    ``{"angle_deg": <0–360>, "stops": [{"offset": <0–1>, "color": "#rrggbb"}, ...]}``
    with at least two stops. Hex colors are ``#`` plus six hex digits.
    """

    angle_deg: float
    stops: list[SkeletonGradientStop]


class SkeletonPatchRequest(BaseModel):
    """Body for `PATCH /api/v1/skeletons/{id}`.

    Partial. Only fields present in the body are written. Omitted fields
    leave the row unchanged. Null ``status``, kind, or spacing is rejected
    by the handler. Spacing integers must be zero or greater. Background
    color is ``#`` plus six hex digits, or blank to clear it. Gradient
    uses the locked ``SkeletonGradient`` shape. ``background_asset_ref`` is
    a relative path with no ``..`` and no scheme, ending in ``.svg``,
    ``.png``, ``.jpg``, or ``.jpeg``. Draft may leave the payload for the
    chosen kind empty. Live requires that payload.
    """

    status: SkeletonStatus | None = None
    page_margin: int | None = None
    element_gap: int | None = None
    element_margin: int | None = None
    background_kind: BackgroundKind | None = None
    background_color: str | None = None
    background_gradient: dict[str, object] | None = None
    background_asset_ref: str | None = None


SKELETON_ELEMENT_NAME_REQUIRED_DETAIL: str = "Name is required."


def stripped_skeleton_element_name(name: str | None) -> str:
    """Return a trimmed element name. Blank and null are rejected."""

    if name is None:
        raise ValueError(SKELETON_ELEMENT_NAME_REQUIRED_DETAIL)

    stripped_name: str = name.strip()

    if stripped_name == "":
        raise ValueError(SKELETON_ELEMENT_NAME_REQUIRED_DETAIL)

    return stripped_name


class SkeletonElementCreateRequest(BaseModel):
    """Body for `POST /api/v1/skeletons/{skeleton_id}/elements`.

    ``name``, ``band``, and ``content_kind`` are required. ``name`` is
    the label operators see when they edit a slide. Blank and
    whitespace-only names are rejected. ``sort_order`` is optional
    and 0-based within the band; omitted means append. ``rectangle_color``
    null means the rectangle is clear. Text requires a family, a
    positive size, a color, and alignment. ``text_source`` may be null.
    Image requires ``image_asset_ref`` and forbids ``text_source``. ``x``,
    ``y``, and ``width`` are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    band: SkeletonElementBand
    content_kind: SkeletonElementContentKind
    sort_order: int | None = None
    rectangle_color: str | None = None
    rectangle_opacity: int | None = 100
    rectangle_radius: int | None = 0
    text_source: SkeletonElementTextSource | None = None
    font_family: str | None = None
    font_size: int | None = None
    font_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikethrough: bool | None = None
    font_weight: int | None = None
    alignment: SkeletonElementAlignment | None = None
    image_asset_ref: str | None = None

    @field_validator("name")
    @classmethod
    def name_is_non_blank(cls, name: str) -> str:
        """Reject a blank name and store the trimmed text."""

        stripped_name: str = stripped_skeleton_element_name(name)

        return stripped_name


SkeletonCreateRequest.model_rebuild()


class SkeletonElementPatchRequest(BaseModel):
    """Body for `PATCH /api/v1/skeletons/{skeleton_id}/elements/{element_id}`.

    Partial. Only fields present in the body are written. Omitted
    ``name`` leaves the stored label. A present name must be non-blank
    after trimming; null and whitespace are rejected. Omitted
    ``sort_order`` leaves the index unless ``band`` changes, in which
    case the element is appended on the new band. The server compacts
    the band afterward. ``x``, ``y``, and ``width`` are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    band: SkeletonElementBand | None = None
    content_kind: SkeletonElementContentKind | None = None
    sort_order: int | None = None
    rectangle_color: str | None = None
    rectangle_opacity: int | None = None
    rectangle_radius: int | None = None
    text_source: SkeletonElementTextSource | None = None
    font_family: str | None = None
    font_size: int | None = None
    font_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikethrough: bool | None = None
    font_weight: int | None = None
    alignment: SkeletonElementAlignment | None = None
    image_asset_ref: str | None = None

    @field_validator("name")
    @classmethod
    def name_is_non_blank(cls, name: str | None) -> str:
        """Reject a blank or null name when the client sent one."""

        stripped_name: str = stripped_skeleton_element_name(name)

        return stripped_name


class SkeletonElementReadResponse(BaseModel):
    """Serialized skeleton element. No coordinates."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    skeleton_id: uuid.UUID
    band: SkeletonElementBand
    sort_order: int
    content_kind: SkeletonElementContentKind
    name: str
    rectangle_color: str | None
    rectangle_opacity: int
    rectangle_radius: int
    text_source: SkeletonElementTextSource | None
    font_family: str | None
    font_size: int | None
    font_color: str | None
    bold: bool
    italic: bool
    underline: bool
    strikethrough: bool
    font_weight: int | None
    alignment: SkeletonElementAlignment | None
    image_asset_ref: str | None
    created_at: datetime
    updated_at: datetime


class SkeletonReadResponse(BaseModel):
    """Serialized Skeleton row.

    ``elements`` are ordered by band (``top``, ``middle``, ``bottom``)
    and then by ``sort_order`` within the band.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    advertisement_type: AdvertisementType
    template_key: str | None
    status: SkeletonStatus
    page_margin: int
    element_gap: int
    element_margin: int
    background_kind: BackgroundKind
    background_color: str | None
    background_gradient: SkeletonGradient | None
    background_asset_ref: str | None
    elements: list[SkeletonElementReadResponse]
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None


class SkeletonSampleRequest(BaseModel):
    """Body for `POST /api/v1/skeletons/{id}/samples`.

    One source item, one frame. The handler does not create an artifact
    or a post job.
    """

    source_item_id: uuid.UUID


class SkeletonSampleOverlapResponse(BaseModel):
    """One pair of elements from different bands whose areas intersect."""

    band_a: SkeletonElementBand
    band_b: SkeletonElementBand
    element_ids: list[uuid.UUID]


class SkeletonSampleResponse(BaseModel):
    """One rendered preview. ``blocked`` is true when it must not ship.

    ``block_reason`` is null, ``overlap``, ``missing_asset``, or
    ``measure_error``. The PNG is still written when the frame is blocked.
    ``overlaps`` is present even when another reason wins.
    """

    preview_id: uuid.UUID
    blocked: bool
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None
    detail: str | None
    overlaps: list[SkeletonSampleOverlapResponse]


class SkeletonImageAlbumResponse(BaseModel):
    """One album of concrete image paths. More albums can be added later."""

    album_id: str
    name: str
    asset_refs: list[str]


class SkeletonDefaultImagesResponse(BaseModel):
    """Albums the skeleton editor can offer for picture and image fields."""

    albums: list[SkeletonImageAlbumResponse]


class SkeletonFontFamilyResponse(BaseModel):
    """One family the font dropdown can offer."""

    family_id: str
    name: str
    category: str


class SkeletonFontFamiliesResponse(BaseModel):
    """Bundled families plus the name used when a stored family is unknown."""

    families: list[SkeletonFontFamilyResponse]
    fallback_name: str


class SkeletonPreviewElementRequest(SkeletonElementCreateRequest):
    """One element on a stateless preview.

    ``preview_text`` is drawn for a text element and is not stored.
    Image elements ignore it. Create and patch bodies do not accept
    this field.
    """

    preview_text: str | None = None


class SkeletonPreviewRequest(BaseModel):
    """Body for `POST /api/v1/skeletons/preview`.

    Frame fields and elements are the form as it stands, including a
    skeleton that has not been saved. Omitted frame fields use the create
    defaults. Text uses ``preview_text`` on each element. The handler
    does not insert a skeleton, an artifact, or a post job, and it does
    not read a source item.
    """

    status: SkeletonStatus = SkeletonStatus.DRAFT
    page_margin: int = DEFAULT_PAGE_MARGIN
    element_gap: int = DEFAULT_ELEMENT_GAP
    element_margin: int = DEFAULT_ELEMENT_MARGIN
    background_kind: BackgroundKind = BackgroundKind.COLOR
    background_color: str | None = DEFAULT_BACKGROUND_COLOR
    background_gradient: SkeletonGradient | None = None
    background_asset_ref: str | None = None
    elements: list[SkeletonPreviewElementRequest] = Field(default_factory=list)

    @field_validator("elements", mode="before")
    @classmethod
    def coerce_preview_elements(cls, elements: object) -> object:
        """Accept a stored element body as well as a preview element.

        Callers that already built ``SkeletonElementCreateRequest`` do not
        carry ``preview_text``. Dump those models so validation can add
        the default. A preview element and a raw dict pass through.
        """

        if not isinstance(elements, list):

            return elements

        normalized_elements: list[object] = []

        for element in elements:

            if isinstance(element, SkeletonPreviewElementRequest):
                normalized_elements.append(element)

                continue

            if isinstance(element, BaseModel):
                normalized_elements.append(element.model_dump())

                continue

            normalized_elements.append(element)

        return normalized_elements


class SkeletonPreviewResponse(BaseModel):
    """One stateless frame. The PNG is inline. Nothing is stored.

    ``block_reason`` matches the saved-skeleton sample response. A missing
    font file uses the same Pillow fallback as that renderer and is not
    an error by itself.
    """

    blocked: bool
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None
    detail: str | None
    overlaps: list[SkeletonSampleOverlapResponse]
    image_png_base64: str


class SpotmuInterestSearchHitResponse(BaseModel):
    """One mapped hit from the Spotmu live search proxy."""

    slug: str
    title: str
    spotmu_interest_id: str | None = None
    interest_heading: str | None = None


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
    template_id: str | None = None


class CarouselTemplateReadResponse(BaseModel):
    """One restricted Spotmu template from `GET /api/v1/generate/templates`."""

    template_id: str
    name: str
    description: str
    is_default: bool


class ArtifactRegenerateRequest(BaseModel):
    """Body for `POST /api/v1/artifacts/{id}/regenerate`.

    Creates a **new** draft from the same `source_item_id` (history kept).
    `template_id` optional: falls back to the original artifact, then paper.
    """

    template_id: str | None = None


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
    template_id: str | None = None
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
    template_id: str | None = None
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
    role: OpsUserRole
    created_at: datetime
    updated_at: datetime


class OpsLogoutResponse(BaseModel):
    """Body for `POST /api/v1/auth/logout`."""

    status: str


class OpsChangePasswordRequest(BaseModel):
    """Body for `POST /api/v1/auth/change-password` (self only)."""

    current_password: str
    new_password: str = Field(min_length=8)


class OpsChangePasswordResponse(BaseModel):
    """Body after a successful self password change."""

    status: str


class OpsUserCreateRequest(BaseModel):
    """Body for `POST /api/v1/auth/users` (admin only)."""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8)
    role: OpsUserRole


class OpsUserRolePatchRequest(BaseModel):
    """Body for `PATCH /api/v1/auth/users/{id}` (admin only)."""

    role: OpsUserRole


class OpsUserResetPasswordRequest(BaseModel):
    """Body for `POST /api/v1/auth/users/{id}/reset-password` (admin only)."""

    new_password: str = Field(min_length=8)


class SlideElementTextReadResponse(BaseModel):
    """Text stored on a slide for one skeleton text element."""

    skeleton_element_id: uuid.UUID
    value: str


class SlideImageReadResponse(BaseModel):
    """One image on a slide, including license and the stored path."""

    id: uuid.UUID
    position: int
    relative_path: str
    media_type: SlideImageMediaType
    byte_size: int
    width: int | None
    height: int | None
    alt_text: str | None
    license: SlideImageLicense
    source: str
    license_note: str
    intake: SlideImageIntake
    thumbnail_path: str | None


class SlideReadResponse(BaseModel):
    """One slide: name, skeleton text, exclusions, and at most one image.

    ``texts`` is the approved copy. ``draft_texts`` is empty unless
    ``text_status`` is ``draft``. A draft slide is not live.
    """

    id: uuid.UUID
    position: int
    name: str
    text_status: SlideTextStatus
    texts: list[SlideElementTextReadResponse]
    draft_texts: list[SlideElementTextReadResponse]
    excluded_slide_ids: list[uuid.UUID]
    images: list[SlideImageReadResponse]


class CarouselResearchReadResponse(BaseModel):
    """One research document attached to a carousel, in position order.

    ``id`` is the research item. ``position`` is the link order, starting
    at zero. The body stays on the research item.
    """

    id: uuid.UUID
    title: str
    slug: str
    position: int


class CarouselStepsResponse(BaseModel):
    """Derived step state. Not stored on the carousel.

    ``basic`` is done. ``instructions`` and ``final`` are locked.
    ``content`` and ``slides`` follow the album rule and the slide count.
    """

    basic: CarouselStepState
    instructions: CarouselStepState
    content: CarouselStepState
    slides: CarouselStepState
    final: CarouselStepState


class CarouselListItemResponse(BaseModel):
    """One carousel on `GET /api/v1/carousels`. Slides are on the detail route.

    ``generation_number`` and ``editor_step`` are the stored values.
    Research and derived step state are on the detail route.
    """

    id: uuid.UUID
    skeleton_id: uuid.UUID
    name: str
    slug: str
    album_id: uuid.UUID | None = None
    generation_number: int
    editor_step: int
    slide_count: int
    created_at: datetime
    updated_at: datetime


class CarouselReadResponse(BaseModel):
    """One carousel, its research, derived step state, and slides.

    ``editor_step`` is the stored open step. ``steps`` is derived and
    does not change that stored value. ``research`` is the attached
    documents in position order.
    """

    id: uuid.UUID
    skeleton_id: uuid.UUID
    name: str
    slug: str
    album_id: uuid.UUID | None = None
    generation_number: int
    editor_step: int
    inspiration: str
    rules: str
    live_slide_count: int
    created_at: datetime
    updated_at: datetime
    research: list[CarouselResearchReadResponse]
    steps: CarouselStepsResponse
    slides: list[SlideReadResponse]


class CarouselGuidancePatchRequest(BaseModel):
    """Inspiration and rules for drafted slide text."""

    model_config = ConfigDict(extra="forbid")

    inspiration: str = ""
    rules: str = ""


class TextGenerationStatusResponse(BaseModel):
    """Whether Generate can run. The API key is not included."""

    available: bool
    detail: str


class CarouselCreateRequest(BaseModel):
    """JSON body for `POST /api/v1/carousels`. Name and skeleton are required."""

    model_config = ConfigDict(extra="forbid")

    name: str
    skeleton_id: uuid.UUID


class CarouselPatchRequest(BaseModel):
    """Rename a carousel. The skeleton stays the one chosen at create.

    Extra fields are rejected, including ``skeleton_id``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str


class CarouselStepPatchRequest(BaseModel):
    """JSON body for `PATCH /api/v1/carousels/{carousel_id}/step`.

    Stored values are 0 Basic, 2 Content, and 3 Slides. The handler
    refuses a locked step. The rename route stays
    `PATCH /carousels/{carousel_id}`.
    """

    model_config = ConfigDict(extra="forbid")

    editor_step: int


class CarouselAlbumAttachRequest(BaseModel):
    """JSON body for `PUT /api/v1/carousels/{carousel_id}/album`.

    ``album_id`` must already exist. This does not create an album.
    """

    model_config = ConfigDict(extra="forbid")

    album_id: uuid.UUID


class CarouselAlbumCreateRequest(BaseModel):
    """JSON body for `POST /api/v1/carousels/{carousel_id}/album`.

    The name follows the same rules as `POST /api/v1/albums`.
    """

    model_config = ConfigDict(extra="forbid")

    name: str


class CarouselResearchAttachRequest(BaseModel):
    """JSON body for `POST /api/v1/carousels/{carousel_id}/research`.

    ``research_item_id`` must already exist. The document is appended.
    This does not create a research item.
    """

    model_config = ConfigDict(extra="forbid")

    research_item_id: uuid.UUID


class CarouselResearchOrderRequest(BaseModel):
    """JSON body for `PUT /api/v1/carousels/{carousel_id}/research`.

    ``research_item_ids`` replaces the attached list and its order.
    An empty list clears every link. The same id twice is rejected.
    Omitting the field does not clear the list.
    """

    model_config = ConfigDict(extra="forbid")

    research_item_ids: list[uuid.UUID]


class SlideElementTextWrite(BaseModel):
    """One skeleton text element and the value to store on the slide."""

    model_config = ConfigDict(extra="forbid")

    skeleton_element_id: uuid.UUID
    value: str = ""


class SlideWriteRequest(BaseModel):
    """Name, skeleton text, and the other slides this one cannot be shown with."""

    model_config = ConfigDict(extra="forbid")

    name: str
    texts: list[SlideElementTextWrite] = Field(default_factory=list)
    excluded_slide_ids: list[uuid.UUID] = Field(default_factory=list)


class SlideAcceptTextRequest(BaseModel):
    """The text to store as live. This is the operator's accept action."""

    model_config = ConfigDict(extra="forbid")

    texts: list[SlideElementTextWrite] = Field(default_factory=list)


class SlidePreviewRequest(BaseModel):
    """Unsaved text, and an optional saved slide, for one frame.

    The handler renders the carousel's skeleton. It does not write a slide,
    an artifact, or a preview file.
    """

    model_config = ConfigDict(extra="forbid")

    texts: list[SlideElementTextWrite] = Field(default_factory=list)
    slide_id: uuid.UUID | None = None


class SlideImageMetadataPatch(BaseModel):
    """License and source on an image that already exists. Not the bytes."""

    model_config = ConfigDict(extra="forbid")

    alt_text: str | None = None
    license: SlideImageLicense
    source: str
    license_note: str = ""


class SlideImageImportRequest(BaseModel):
    """One URL to download, plus the same license fields as an upload."""

    model_config = ConfigDict(extra="forbid")

    url: str
    alt_text: str | None = None
    license: SlideImageLicense
    source: str
    license_note: str = ""


class SlideImageCreateItem(BaseModel):
    """One image on a new slide. A file uses ``file_index`` into the upload."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file", "url"]
    file_index: int | None = None
    url: str | None = None
    alt_text: str | None = None
    license: SlideImageLicense
    source: str
    license_note: str = ""


class SlideWithImagesCreateRequest(BaseModel):
    """Name, skeleton text, exclusions, and the one image when the skeleton needs one."""

    model_config = ConfigDict(extra="forbid")

    name: str
    texts: list[SlideElementTextWrite] = Field(default_factory=list)
    excluded_slide_ids: list[uuid.UUID] = Field(default_factory=list)
    images: list[SlideImageCreateItem] = Field(default_factory=list)


class AlbumImageReadResponse(BaseModel):
    """One image in an album. The path is the file that was already stored."""

    id: uuid.UUID
    position: int
    relative_path: str
    media_type: SlideImageMediaType
    byte_size: int
    width: int | None
    height: int | None
    alt_text: str | None
    license: SlideImageLicense
    source: str
    license_note: str
    intake: SlideImageIntake
    thumbnail_path: str | None


class AlbumListItemResponse(BaseModel):
    """One album on the list. Images are on the detail route."""

    id: uuid.UUID
    name: str
    slug: str
    image_count: int
    created_at: datetime
    updated_at: datetime


class AlbumReadResponse(BaseModel):
    """One album and its images, in position order."""

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime
    images: list[AlbumImageReadResponse]


class AlbumCreateRequest(BaseModel):
    """JSON body for `POST /api/v1/albums`. The name is required."""

    model_config = ConfigDict(extra="forbid")

    name: str


class AlbumImageWrite(BaseModel):
    """License fields for an image that is already in the album.

    The order of these rows in the patch is the album order.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    alt_text: str | None = None
    license: SlideImageLicense
    source: str
    license_note: str = ""


class AlbumPatchRequest(BaseModel):
    """Rename an album and save image order, alt, license, and source.

    Every current image id must be present. Removing an image is a
    separate request, so a stale edit cannot drop a row.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    images: list[AlbumImageWrite] = Field(default_factory=list)


class ResearchListItemResponse(BaseModel):
    """One research document on the list. The body is on the detail route."""

    id: uuid.UUID
    title: str
    slug: str
    word_count: int
    character_count: int
    created_at: datetime
    updated_at: datetime


class ResearchReadResponse(BaseModel):
    """One research document, including the body."""

    id: uuid.UUID
    title: str
    slug: str
    body: str
    word_count: int
    character_count: int
    created_at: datetime
    updated_at: datetime


class ResearchCreateRequest(BaseModel):
    """JSON body for `POST /api/v1/research`. The title is required."""

    model_config = ConfigDict(extra="forbid")

    title: str


class ResearchPatchRequest(BaseModel):
    """Save the title and the body. The slug is not in this request."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
