"""Pydantic create/read schemas for the Phase 1 persist-proof API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
    ThemeStatus,
    UnitImageIntake,
    UnitImageLicense,
    UnitImageMediaType,
    UnitTextStatus,
)
from app.models.theme import (
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
    ``other`` still parses.
    """

    name: str = Field(min_length=1)
    campaign_type: CampaignType
    advertisement_type: AdvertisementType = AdvertisementType.CAROUSEL
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
    account_count: int
    interest_count: int
    accounts: list[CampaignAccountReadResponse] = Field(default_factory=list)
    interests: list[CampaignInterestReadResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None


class ThemeCreateRequest(BaseModel):
    """Body for `POST /api/v1/themes`.

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
    status: ThemeStatus | None = None
    page_margin: int | None = None
    element_gap: int | None = None
    element_margin: int | None = None
    background_kind: BackgroundKind | None = None
    background_color: str | None = None
    background_gradient: dict[str, object] | None = None
    background_asset_ref: str | None = None
    elements: list["ThemeElementCreateRequest"] = Field(default_factory=list)


class ThemeGradientStop(BaseModel):
    """One stop in ``themes.background_gradient``.

    ``offset`` is 0 through 1. ``color`` is ``#`` plus six hex digits.
    """

    offset: float
    color: str


class ThemeGradient(BaseModel):
    """Locked shape for ``themes.background_gradient``.

    ``{"angle_deg": <0–360>, "stops": [{"offset": <0–1>, "color": "#rrggbb"}, ...]}``
    with at least two stops. Hex colors are ``#`` plus six hex digits.
    """

    angle_deg: float
    stops: list[ThemeGradientStop]


class ThemePatchRequest(BaseModel):
    """Body for `PATCH /api/v1/themes/{id}`.

    Partial. Only fields present in the body are written. Omitted fields
    leave the row unchanged. Null ``status``, kind, or spacing is rejected
    by the handler. Spacing integers must be zero or greater. Background
    color is ``#`` plus six hex digits, or blank to clear it. Gradient
    uses the locked ``ThemeGradient`` shape. ``background_asset_ref`` is
    a relative path with no ``..`` and no scheme, ending in ``.svg``,
    ``.png``, ``.jpg``, or ``.jpeg``. Draft may leave the payload for the
    chosen kind empty. Live requires that payload.
    """

    status: ThemeStatus | None = None
    page_margin: int | None = None
    element_gap: int | None = None
    element_margin: int | None = None
    background_kind: BackgroundKind | None = None
    background_color: str | None = None
    background_gradient: dict[str, object] | None = None
    background_asset_ref: str | None = None


class ThemeElementCreateRequest(BaseModel):
    """Body for `POST /api/v1/themes/{theme_id}/elements`.

    ``band`` and ``content_kind`` are required. ``sort_order`` is optional
    and 0-based within the band; omitted means append. ``rectangle_color``
    null means the rectangle is clear. Text requires a Spotmu
    ``text_source``, family, positive size, color, and alignment. Image
    requires ``image_asset_ref`` and forbids ``text_source``. ``x``,
    ``y``, and ``width`` are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    band: ThemeElementBand
    content_kind: ThemeElementContentKind
    sort_order: int | None = None
    rectangle_color: str | None = None
    rectangle_opacity: int | None = 100
    rectangle_radius: int | None = 0
    text_source: ThemeElementTextSource | None = None
    font_family: str | None = None
    font_size: int | None = None
    font_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikethrough: bool | None = None
    font_weight: int | None = None
    alignment: ThemeElementAlignment | None = None
    image_asset_ref: str | None = None


ThemeCreateRequest.model_rebuild()


class ThemeElementPatchRequest(BaseModel):
    """Body for `PATCH /api/v1/themes/{theme_id}/elements/{element_id}`.

    Partial. Only fields present in the body are written. Omitted
    ``sort_order`` leaves the index unless ``band`` changes, in which
    case the element is appended on the new band. The server compacts
    the band afterward. ``x``, ``y``, and ``width`` are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    band: ThemeElementBand | None = None
    content_kind: ThemeElementContentKind | None = None
    sort_order: int | None = None
    rectangle_color: str | None = None
    rectangle_opacity: int | None = None
    rectangle_radius: int | None = None
    text_source: ThemeElementTextSource | None = None
    font_family: str | None = None
    font_size: int | None = None
    font_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikethrough: bool | None = None
    font_weight: int | None = None
    alignment: ThemeElementAlignment | None = None
    image_asset_ref: str | None = None


class ThemeElementReadResponse(BaseModel):
    """Serialized theme element. No coordinates."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    theme_id: uuid.UUID
    band: ThemeElementBand
    sort_order: int
    content_kind: ThemeElementContentKind
    rectangle_color: str | None
    rectangle_opacity: int
    rectangle_radius: int
    text_source: ThemeElementTextSource | None
    font_family: str | None
    font_size: int | None
    font_color: str | None
    bold: bool
    italic: bool
    underline: bool
    strikethrough: bool
    font_weight: int | None
    alignment: ThemeElementAlignment | None
    image_asset_ref: str | None
    created_at: datetime
    updated_at: datetime


class ThemeReadResponse(BaseModel):
    """Serialized Theme row.

    ``elements`` are ordered by band (``top``, ``middle``, ``bottom``)
    and then by ``sort_order`` within the band.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    advertisement_type: AdvertisementType
    template_key: str | None
    status: ThemeStatus
    page_margin: int
    element_gap: int
    element_margin: int
    background_kind: BackgroundKind
    background_color: str | None
    background_gradient: ThemeGradient | None
    background_asset_ref: str | None
    elements: list[ThemeElementReadResponse]
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None


class ThemeSampleRequest(BaseModel):
    """Body for `POST /api/v1/themes/{id}/samples`.

    One source item, one frame. The handler does not create an artifact
    or a post job.
    """

    source_item_id: uuid.UUID


class ThemeSampleOverlapResponse(BaseModel):
    """One pair of elements from different bands whose areas intersect."""

    band_a: ThemeElementBand
    band_b: ThemeElementBand
    element_ids: list[uuid.UUID]


class ThemeSampleResponse(BaseModel):
    """One rendered preview. ``blocked`` is true when it must not ship.

    ``block_reason`` is null, ``overlap``, ``missing_asset``, or
    ``measure_error``. The PNG is still written when the frame is blocked.
    ``overlaps`` is present even when another reason wins.
    """

    preview_id: uuid.UUID
    blocked: bool
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None
    detail: str | None
    overlaps: list[ThemeSampleOverlapResponse]


class ThemeImageAlbumResponse(BaseModel):
    """One album of concrete image paths. More albums can be added later."""

    album_id: str
    name: str
    asset_refs: list[str]


class ThemeDefaultImagesResponse(BaseModel):
    """Albums the theme editor can offer for picture and image fields."""

    albums: list[ThemeImageAlbumResponse]


class ThemeFontFamilyResponse(BaseModel):
    """One family the font dropdown can offer."""

    family_id: str
    name: str
    category: str


class ThemeFontFamiliesResponse(BaseModel):
    """Bundled families plus the name used when a stored family is unknown."""

    families: list[ThemeFontFamilyResponse]
    fallback_name: str


class ThemePreviewRequest(BaseModel):
    """Body for `POST /api/v1/themes/preview`.

    Frame fields and elements are the form as it stands, including a
    theme that has not been saved. Omitted frame fields use the create
    defaults. The handler does not insert a theme, an artifact, or a
    post job.
    """

    source_item_id: uuid.UUID
    status: ThemeStatus = ThemeStatus.DRAFT
    page_margin: int = DEFAULT_PAGE_MARGIN
    element_gap: int = DEFAULT_ELEMENT_GAP
    element_margin: int = DEFAULT_ELEMENT_MARGIN
    background_kind: BackgroundKind = BackgroundKind.COLOR
    background_color: str | None = DEFAULT_BACKGROUND_COLOR
    background_gradient: ThemeGradient | None = None
    background_asset_ref: str | None = None
    elements: list[ThemeElementCreateRequest] = Field(default_factory=list)


class ThemePreviewResponse(BaseModel):
    """One stateless frame. The PNG is inline. Nothing is stored.

    ``block_reason`` matches the saved-theme sample response. A missing
    font file uses the same Pillow fallback as that renderer and is not
    an error by itself.
    """

    blocked: bool
    block_reason: Literal["overlap", "missing_asset", "measure_error"] | None
    detail: str | None
    overlaps: list[ThemeSampleOverlapResponse]
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


class UnitElementTextReadResponse(BaseModel):
    """Text stored on a unit for one theme text element."""

    theme_element_id: uuid.UUID
    value: str


class UnitImageReadResponse(BaseModel):
    """One image on a unit, including license and the stored path."""

    id: uuid.UUID
    position: int
    relative_path: str
    media_type: UnitImageMediaType
    byte_size: int
    width: int | None
    height: int | None
    alt_text: str | None
    license: UnitImageLicense
    source: str
    license_note: str
    intake: UnitImageIntake
    thumbnail_path: str | None


class UnitReadResponse(BaseModel):
    """One unit: name, theme text, exclusions, and at most one image.

    ``texts`` is the approved copy. ``draft_texts`` is empty unless
    ``text_status`` is ``draft``. A draft unit is not live.
    """

    id: uuid.UUID
    position: int
    name: str
    text_status: UnitTextStatus
    texts: list[UnitElementTextReadResponse]
    draft_texts: list[UnitElementTextReadResponse]
    excluded_unit_ids: list[uuid.UUID]
    images: list[UnitImageReadResponse]


class SourceListItemResponse(BaseModel):
    """One source on `GET /api/v1/sources`. Units are on the detail route."""

    id: uuid.UUID
    theme_id: uuid.UUID
    name: str
    slug: str
    unit_count: int
    created_at: datetime
    updated_at: datetime


class SourceReadResponse(BaseModel):
    """One source and its units."""

    id: uuid.UUID
    theme_id: uuid.UUID
    name: str
    slug: str
    inspiration: str
    rules: str
    live_unit_count: int
    created_at: datetime
    updated_at: datetime
    units: list[UnitReadResponse]


class SourceGuidancePatchRequest(BaseModel):
    """Inspiration and rules for drafted unit text."""

    model_config = ConfigDict(extra="forbid")

    inspiration: str = ""
    rules: str = ""


class TextGenerationStatusResponse(BaseModel):
    """Whether Generate can run. The API key is not included."""

    available: bool
    detail: str


class SourceCreateRequest(BaseModel):
    """JSON body for `POST /api/v1/sources`. Name and theme are required."""

    model_config = ConfigDict(extra="forbid")

    name: str
    theme_id: uuid.UUID


class SourcePatchRequest(BaseModel):
    """Rename a source."""

    model_config = ConfigDict(extra="forbid")

    name: str


class UnitElementTextWrite(BaseModel):
    """One theme text element and the value to store on the unit."""

    model_config = ConfigDict(extra="forbid")

    theme_element_id: uuid.UUID
    value: str = ""


class UnitWriteRequest(BaseModel):
    """Name, theme text, and the other units this one cannot be shown with."""

    model_config = ConfigDict(extra="forbid")

    name: str
    texts: list[UnitElementTextWrite] = Field(default_factory=list)
    excluded_unit_ids: list[uuid.UUID] = Field(default_factory=list)


class UnitAcceptTextRequest(BaseModel):
    """The text to store as live. This is the operator's accept action."""

    model_config = ConfigDict(extra="forbid")

    texts: list[UnitElementTextWrite] = Field(default_factory=list)


class UnitPreviewRequest(BaseModel):
    """Unsaved text, and an optional saved unit, for one frame.

    The handler renders the source's theme. It does not write a unit,
    an artifact, or a preview file.
    """

    model_config = ConfigDict(extra="forbid")

    texts: list[UnitElementTextWrite] = Field(default_factory=list)
    unit_id: uuid.UUID | None = None


class UnitImageMetadataPatch(BaseModel):
    """License and source on an image that already exists. Not the bytes."""

    model_config = ConfigDict(extra="forbid")

    alt_text: str | None = None
    license: UnitImageLicense
    source: str
    license_note: str = ""


class UnitImageImportRequest(BaseModel):
    """One URL to download, plus the same license fields as an upload."""

    model_config = ConfigDict(extra="forbid")

    url: str
    alt_text: str | None = None
    license: UnitImageLicense
    source: str
    license_note: str = ""


class UnitImageCreateItem(BaseModel):
    """One image on a new unit. A file uses ``file_index`` into the upload."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file", "url"]
    file_index: int | None = None
    url: str | None = None
    alt_text: str | None = None
    license: UnitImageLicense
    source: str
    license_note: str = ""


class UnitWithImagesCreateRequest(BaseModel):
    """Name, theme text, exclusions, and the one image when the theme needs one."""

    model_config = ConfigDict(extra="forbid")

    name: str
    texts: list[UnitElementTextWrite] = Field(default_factory=list)
    excluded_unit_ids: list[uuid.UUID] = Field(default_factory=list)
    images: list[UnitImageCreateItem] = Field(default_factory=list)
